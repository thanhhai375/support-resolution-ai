from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.api.deps import get_current_user as _get_current_user
from app.api.deps import require_role as _require_role
from pydantic import BaseModel, Field

try:
    from main import get_db
except ImportError:
    from backend.main import get_db

try:
    from models import KnowledgePassage, Product, UserRole
except ImportError:
    from backend.models import KnowledgePassage, Product, UserRole

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge & Citations"])

# CRM-40 role names map onto the legacy authentication repository vocabulary.
# This keeps the task scoped to the approved router files while auth storage is migrated.
_ROLE_TO_LEGACY = {
    UserRole.STAFF: "support_agent",
    UserRole.ENGINEER: "technical_approver",
    UserRole.MANAGER: "knowledge_steward",
    UserRole.ADMIN: "administrator",
}
_LEGACY_TO_ROLE = {
    legacy_role: crm_role.value
    for crm_role, legacy_role in _ROLE_TO_LEGACY.items()
}


def normalize_role(role: Any) -> str:
    """Chuẩn hóa role cũ/mới về tên role CRM-40 (STAFF/ENGINEER/MANAGER/ADMIN)."""
    raw_role = getattr(role, "value", role)
    if raw_role is None:
        return ""
    raw_role = str(raw_role)
    if raw_role in _LEGACY_TO_ROLE:
        return _LEGACY_TO_ROLE[raw_role]
    # Hỗ trợ cả enum UserRole và chuỗi CRM-40.
    try:
        return UserRole(raw_role).value
    except ValueError:
        return raw_role.upper()


def require_role(*roles):
    """CRM-40 adapter: kiểm tra bằng role legacy, trả current_user với role CRM-40."""
    crm_roles = tuple(normalize_role(role) for role in roles)
    legacy_roles = tuple(
        _ROLE_TO_LEGACY.get(UserRole(role), role)
        for role in crm_roles
    )
    base_checker = _require_role(*legacy_roles)

    def checker(current_user=Depends(_get_current_user)):
        # Chấp nhận role CRM-40 và role legacy từ hệ thống xác thực hiện tại.
        normalized_user = dict(current_user)
        crm_role = normalize_role(normalized_user.get("role"))
        legacy_role = _ROLE_TO_LEGACY.get(
            UserRole(crm_role) if crm_role in {r.value for r in UserRole} else None,
            crm_role,
        )
        normalized_user["role"] = legacy_role

        try:
            authorized_user = base_checker(normalized_user)
            # Quan trọng: không để role legacy lọt ra ngoài dependency.
            result_user = dict(authorized_user or normalized_user)
            result_user["role"] = crm_role
            return result_user
        except HTTPException as exc:
            if exc.status_code == status.HTTP_403_FORBIDDEN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions",
                ) from exc
            raise

    return checker



class KnowledgePassageCreate(BaseModel):
    product_id: UUID
    document_name: str
    document_code: Optional[str] = None
    section_name: Optional[str] = None
    section_number: Optional[str] = None
    page_number: int = 1
    passage_content: str
    is_approved: bool = False
    passage_metadata: Optional[dict[str, Any]] = Field(default_factory=dict)


def _map_citation(passage: KnowledgePassage) -> dict[str, Any]:
    """Ánh xạ Citation chuẩn theo RFP Section 3 (DAT 08)."""
    meta = passage.passage_metadata if isinstance(passage.passage_metadata, dict) else {}
    version = str(meta.get("version") or meta.get("doc_version") or "v1.0")
    section_parts = [p for p in [passage.section_number, passage.section_name] if p]
    section_label = " - ".join(section_parts) if section_parts else "General"

    return {
        "document_title": passage.document_name,
        "document_code": passage.document_code,
        "version": version,
        "section": section_label,
        "section_number": passage.section_number,
        "section_name": passage.section_name,
        "page_number": passage.page_number,
    }


def _serialize_passage(passage: KnowledgePassage, product: Optional[Product] = None) -> dict[str, Any]:
    citation = _map_citation(passage)
    return {
        "id": str(passage.id),
        "product_id": str(passage.product_id),
        "product_code": product.code if product else None,
        "product_name": product.name if product else None,
        "content": passage.passage_content,
        "passage_content": passage.passage_content,
        "is_approved": passage.is_approved,
        "approved_by": passage.approved_by,
        "approved_at": passage.approved_at.isoformat() if passage.approved_at else None,
        # Citation Mapping (DAT 08)
        "citation": citation,
        # Các trường phẳng hỗ trợ client đọc trực tiếp
        "document_title": citation["document_title"],
        "version": citation["version"],
        "section": citation["section"],
        "page_number": citation["page_number"],
        "metadata": passage.passage_metadata or {},
    }


async def _ensure_seed_knowledge(db: AsyncSession) -> None:
    """Tự động seed dữ liệu kỹ thuật Motors & Drives (DAT 04, DAT 05) nếu bảng đang trống."""
    count_res = await db.execute(select(func.count(KnowledgePassage.id)))
    if (count_res.scalar() or 0) > 0:
        return

    # Đảm bảo 2 nhóm sản phẩm MOTORS và DRIVES tồn tại
    prod_map: dict[str, Product] = {}
    defaults = [
        ("MOTORS", "Động cơ (Motors)", "Động cơ điện hạ thế và trung thế ABB."),
        ("DRIVES", "Biến tần (Drives)", "Biến tần công nghiệp và bộ điều khiển truyền động ABB."),
    ]
    for code, name, desc in defaults:
        res = await db.execute(select(Product).where(func.upper(Product.code) == code))
        prod = res.scalars().first()
        if not prod:
            prod = Product(code=code, name=name, description=desc)
            db.add(prod)
            await db.flush()
        prod_map[code] = prod

    now = datetime.now(timezone.utc)
    seed_passages = [
        KnowledgePassage(
            product_id=prod_map["MOTORS"].id,
            document_name="ABB M2BAX Low Voltage Cast Iron Motors Manual",
            document_code="3GZF500730-87",
            section_number="4.2",
            section_name="Electrical Connection & Starting Troubleshooting",
            page_number=28,
            passage_content=(
                "If an ABB M2BAX 3-phase motor fails to start after 380V power is applied, "
                "verify phase-to-phase voltage balance (tolerance ±5%), inspect thermal overload "
                "relay trip state, and confirm star/delta terminal link configuration."
            ),
            is_approved=True,
            approved_at=now,
            approved_by="technical-lead@songnhat.vn",
            passage_metadata={"version": "Rev. G (2025)", "language": "EN"},
        ),
        KnowledgePassage(
            product_id=prod_map["MOTORS"].id,
            document_name="ABB M2BAX Bearing Lubrication & Maintenance Guide",
            document_code="3GZF500730-92",
            section_number="6.1",
            section_name="Bearing Temperature & Vibration Limits",
            page_number=41,
            passage_content=(
                "Maximum continuous bearing housing temperature for M2BAX 90L frame motors "
                "must not exceed 95°C under rated load. Abnormal noise or vibration above 2.8 mm/s "
                "requires immediate shaft alignment and grease interval verification."
            ),
            is_approved=True,
            approved_at=now,
            approved_by="technical-lead@songnhat.vn",
            passage_metadata={"version": "Rev. E (2024)", "language": "EN"},
        ),
        KnowledgePassage(
            product_id=prod_map["DRIVES"].id,
            document_name="ABB ACS580 General Purpose Drives Firmware Manual",
            document_code="3AXD50000016097",
            section_number="7.3",
            section_name="Fault Tracing — Overcurrent (2310) & Overvoltage (3210)",
            page_number=312,
            passage_content=(
                "Fault 2310 (Overcurrent): Output current exceeds internal trip limit. "
                "Check motor load, acceleration ramp time (parameter 23.12), motor cable insulation, "
                "and verify motor nameplate data in group 99."
            ),
            is_approved=True,
            approved_at=now,
            approved_by="drives-specialist@songnhat.vn",
            passage_metadata={"version": "FW v2.14", "language": "EN"},
        ),
        KnowledgePassage(
            product_id=prod_map["DRIVES"].id,
            document_name="ABB ACS580 Hardware & Safety Installation Manual",
            document_code="3AXD50000018826",
            section_number="2.1",
            section_name="Electrical Safety & Enclosure Fire Hazard Prevention",
            page_number=19,
            passage_content=(
                "WARNING: Isolate main power and wait 5 minutes for DC link capacitors to discharge "
                "before opening the drive cabinet. Smoke or burning odor indicates immediate power "
                "disconnect and hazard escalation."
            ),
            is_approved=True,
            approved_at=now,
            approved_by="safety-officer@songnhat.vn",
            passage_metadata={"version": "Rev. K (2025)", "language": "EN"},
        ),
        # 1 bản ghi chưa duyệt để kiểm chứng bộ lọc is_approved=TRUE
        KnowledgePassage(
            product_id=prod_map["DRIVES"].id,
            document_name="Internal Draft Field Notes — ACS580 Beta Firmware",
            document_code="DRAFT-ACS-001",
            section_number="1.0",
            section_name="Unverified Field Workaround",
            page_number=3,
            passage_content="Unapproved internal test note — must NOT appear when is_approved=true.",
            is_approved=False,
            passage_metadata={"version": "v0.1-draft"},
        ),
    ]
    db.add_all(seed_passages)
    await db.commit()


# 1. GET /api/knowledge/passages: Truy xuất đoạn trích kỹ thuật & Citations (STAFF trở lên)
@router.get("/passages", status_code=200)
async def get_knowledge_passages(
    product: Optional[str] = Query(
        None,
        description="Lọc theo nhóm sản phẩm: 'Motors' hoặc 'Drives' (hỗ trợ cả MOTORS / DRIVES)",
    ),
    product_id: Optional[UUID] = Query(None, description="Lọc theo UUID của sản phẩm"),
    is_approved: bool = Query(True, description="Chỉ lấy đoạn trích đã phê duyệt (mặc định TRUE)"),
    q: Optional[str] = Query(None, description="Từ khóa tìm kiếm trong nội dung hoặc tên tài liệu"),
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(UserRole.STAFF, UserRole.ENGINEER, UserRole.MANAGER, UserRole.ADMIN)),
):
    await _ensure_seed_knowledge(db)

    stmt = (
        select(KnowledgePassage, Product)
        .join(Product, KnowledgePassage.product_id == Product.id)
        .where(KnowledgePassage.is_approved == is_approved)
    )

    if product_id:
        stmt = stmt.where(KnowledgePassage.product_id == product_id)

    if product and product.strip():
        clean_prod = product.strip().lower()
        if clean_prod in {"motor", "motors"}:
            stmt = stmt.where(
                or_(
                    func.lower(Product.code) == "motors",
                    func.lower(Product.name).contains("motor"),
                )
            )
        elif clean_prod in {"drive", "drives"}:
            stmt = stmt.where(
                or_(
                    func.lower(Product.code) == "drives",
                    func.lower(Product.name).contains("drive"),
                )
            )
        else:
            stmt = stmt.where(
                or_(
                    func.lower(Product.code) == clean_prod,
                    func.lower(Product.name).contains(clean_prod),
                )
            )

    if q and q.strip():
        kw = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                KnowledgePassage.passage_content.ilike(kw),
                KnowledgePassage.document_name.ilike(kw),
                KnowledgePassage.section_name.ilike(kw),
            )
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(KnowledgePassage.created_at.desc()).offset(page * size).limit(size)
    rows = (await db.execute(stmt)).all()
    items = [_serialize_passage(passage, prod) for passage, prod in rows]

    return {
        "page": page,
        "size": size,
        "total": total,
        "items": items,
    }


# 2. POST /api/knowledge/passages: Thêm đoạn trích kiến thức mới (Chỉ MANAGER, ADMIN)
@router.post("/passages", status_code=status.HTTP_201_CREATED)
async def create_knowledge_passage(
    data: KnowledgePassageCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(UserRole.MANAGER, UserRole.ADMIN)),
):
    # Kiểm tra product tồn tại
    prod_res = await db.execute(select(Product).where(Product.id == data.product_id))
    prod = prod_res.scalars().first()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")

    new_passage = KnowledgePassage(
        product_id=data.product_id,
        document_name=data.document_name,
        document_code=data.document_code,
        section_name=data.section_name,
        section_number=data.section_number,
        page_number=data.page_number,
        passage_content=data.passage_content,
        is_approved=data.is_approved,
        passage_metadata=data.passage_metadata,
        approved_by=current_user["email"] if data.is_approved else None,
        approved_at=datetime.now(timezone.utc) if data.is_approved else None,
    )
    db.add(new_passage)
    await db.commit()
    await db.refresh(new_passage)

    return _serialize_passage(new_passage, prod)


# 3. GET /api/knowledge/passages/{passage_id}: Lấy chi tiết 1 đoạn trích kèm Citation (STAFF trở lên)
@router.get("/passages/{passage_id}", status_code=200)
async def get_knowledge_passage_detail(
    passage_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(UserRole.STAFF, UserRole.ENGINEER, UserRole.MANAGER, UserRole.ADMIN)),
):
    await _ensure_seed_knowledge(db)

    stmt = (
        select(KnowledgePassage, Product)
        .join(Product, KnowledgePassage.product_id == Product.id)
        .where(KnowledgePassage.id == passage_id)
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge passage not found")

    passage, prod = row
    return _serialize_passage(passage, prod)