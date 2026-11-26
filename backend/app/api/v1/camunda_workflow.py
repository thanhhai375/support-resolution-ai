"""FastAPI router for Camunda 7 BPMN Ticket Triage, Approval APIs & PDF Export (CRM-44, CRM-58, CRM-59, CRM-69).

Exposes:
  - `POST  /api/copilot/analyze`
  - `GET   /api/copilot/process/{ticket_id}/status`
  - `GET   /api/v1/copilot/{ticket_id}/approval`
  - `PATCH /api/v1/copilot/{ticket_id}/approve`
  - `PATCH /api/v1/copilot/{ticket_id}/reject`
  - `GET   /api/v1/copilot/{ticket_id}/export`
"""
import asyncio
import io
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/copilot", tags=["Camunda BPMN & Copilot Workflow"])
approval_router = APIRouter(prefix="/api/v1/copilot", tags=["Copilot Approval"])

from app.api.deps import get_current_user, require_role, require_role as _require_role  # noqa: E402
from app.main import get_db  # noqa: E402  (imported after routers exist to prevent circular ImportError)
from app.repositories import user_repository  # noqa: E402

from app.camunda.worker import (  # noqa: E402
    ProcessAlreadyReviewedError,
    complete_human_approval,
    get_process_status,
    start_ticket_triage_process,
)
from app.services.copilot_engine import run_copilot_pipeline  # noqa: E402

# In-memory fallback cache for approval packages when running without DB (e.g. standalone unit tests)
_APPROVAL_CACHE: dict[str, dict[str, Any]] = {}


def reset_approval_cache() -> None:
    """Clear in-memory approval cache (used in unit tests)."""
    _APPROVAL_CACHE.clear()


def cache_copilot_package(ticket_id: str, package_dict: dict[str, Any]) -> None:
    """Record a newly generated Copilot Support Package as PENDING in the fallback cache."""
    key = str(ticket_id)
    draft_text = package_dict.get("draft") or package_dict.get("draft_response") or ""
    _APPROVAL_CACHE[key] = {
        "ticket_id": key,
        "intent": package_dict.get("intent") or "TECHNICAL_ESCALATION",
        "draft": draft_text,
        "draft_response": draft_text,
        "citations": list(package_dict.get("citations") or []),
        "missing_facts": list(package_dict.get("missing_facts") or []),
        "next_step": package_dict.get("next_step"),
        "is_hazard_escalated": bool(package_dict.get("is_hazard_escalated", False)),
        "approval_status": "PENDING",
        "rejection_reason": None,
        "approved_by": None,
        "approved_at": None,
        "rejected_by": None,
        "rejected_at": None,
    }


class CamundaAnalyzeRequest(BaseModel):
    ticket_description: str = Field(..., min_length=1)
    ticket_id: Optional[str] = Field(default=None)


@router.post("/analyze")
async def analyze_with_camunda_workflow(
    payload: CamundaAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Run Copilot analysis and start a Camunda BPMN process instance when `CAMUNDA_URL` is set.

    This is the single `POST /api/copilot/analyze` handler: it uses the shared DB session
    (real retriever + saved `copilot_packages`) exactly like the legacy copilot router.
    """
    package = await run_copilot_pipeline(
        ticket_description=payload.ticket_description,
        ticket_id=payload.ticket_id,
        db=db,
    )
    result = package.model_dump(mode="json")

    if payload.ticket_id:
        cache_copilot_package(str(payload.ticket_id), result)

    effective_ticket_id = str(payload.ticket_id) if payload.ticket_id else "latest"
    proc = await start_ticket_triage_process(
        ticket_id=effective_ticket_id,
        ticket_description=payload.ticket_description,
        intent=result["intent"],
        is_hazard_escalated=bool(result.get("is_hazard_escalated", False)),
    )
    if proc is not None:
        result["process_instance_id"] = proc.get("process_instance_id")
        result["camunda_topic"] = proc.get("routed_topic")
    else:
        result["process_instance_id"] = None
        result["camunda_topic"] = None

    return result


@router.get("/process/{ticket_id}/status")
async def get_copilot_process_status(ticket_id: str) -> dict[str, Any]:
    """Return the Camunda BPMN process status for `ticket_id` (CRM-44)."""
    record = await get_process_status(ticket_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Camunda BPMN process instance found for ticket '{ticket_id}'",
        )
    return record


# --- Approval API (CRM-41 / CRM-44 / CRM-58 / CRM-69) --------------------------------------
_CRM40_ROLE_TO_LEGACY = {
    "STAFF": "support_agent",
    "ENGINEER": "technical_approver",
    "MANAGER": "knowledge_steward",
    "ADMIN": "administrator",
}
_viewer_access = _require_role(
    "support_agent", "technical_approver", "knowledge_steward", "administrator"
)
_approver_access = _require_role("technical_approver", "knowledge_steward")


def _normalize_user_for_legacy_guard(current_user: dict) -> dict:
    normalized_user = dict(current_user)
    raw_role = getattr(normalized_user.get("role"), "value", normalized_user.get("role"))
    role_str = str(raw_role).strip() if raw_role is not None else ""
    normalized_user["role"] = _CRM40_ROLE_TO_LEGACY.get(role_str.upper(), role_str.lower())
    return normalized_user


def require_viewer_role(current_user: dict = Depends(get_current_user)) -> dict:
    """Require any authenticated SongNhat user (STAFF, ENGINEER, MANAGER, ADMIN) to view approval state."""
    return _viewer_access(_normalize_user_for_legacy_guard(current_user))


def require_approver_role(current_user: dict = Depends(get_current_user)) -> dict:
    """Require ENGINEER or MANAGER (legacy: technical_approver / knowledge_steward) to approve/reject."""
    return _approver_access(_normalize_user_for_legacy_guard(current_user))


class ApproveRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    approved_by: Optional[str] = Field(
        default=None,
        min_length=1,
        validation_alias=AliasChoices("approved_by", "approvedBy", "approver_id", "approverId"),
    )
    draft: Optional[str] = Field(
        default=None,
        min_length=1,
        validation_alias=AliasChoices("draft", "approved_text", "approvedText"),
    )

    @model_validator(mode="after")
    def _validate_non_empty_approve(self) -> "ApproveRequest":
        if not self.approved_by and not self.draft:
            raise ValueError("Either 'approved_by' or 'draft' must be provided")
        return self


class RejectRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    rejection_reason: str = Field(
        ..., min_length=1, validation_alias=AliasChoices("rejection_reason", "rejectionReason", "reason")
    )
    rejected_by: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("rejected_by", "rejectedBy", "reviewer")
    )
    draft: Optional[str] = Field(default=None)


def _to_uuid(ticket_id: str) -> uuid.UUID:
    """Same ticket-id -> UUID mapping used by `copilot_engine` when saving packages."""
    try:
        return uuid.UUID(str(ticket_id))
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(ticket_id))


def _normalize_approval_status(raw_status: Optional[str]) -> str:
    upper = (raw_status or "PENDING").strip().upper()
    if upper in {"PENDING", "APPROVED", "REJECTED"}:
        return upper
    return "PENDING"


DB_PERSIST_TIMEOUT_SECONDS = 5.0


async def _load_approval_from_db(
    ticket_id: str, db: Optional[AsyncSession] = None
) -> Optional[dict[str, Any]]:
    """Fetch the latest `CopilotPackage` row for `ticket_id` if available."""
    try:
        from models import CopilotPackage

        pkg_id = _to_uuid(ticket_id)

        async def _query(session: AsyncSession) -> Optional[CopilotPackage]:
            stmt = (
                select(CopilotPackage)
                .where(CopilotPackage.ticket_id == pkg_id)
                .order_by(CopilotPackage.updated_at.desc(), CopilotPackage.created_at.desc())
            )
            return (await session.execute(stmt)).scalars().first()

        if db is not None:
            pkg = await _query(db)
        else:
            import app.main as app_main

            await app_main.ensure_db_initialized()
            async with app_main.AsyncSessionLocal() as session:
                pkg = await _query(session)

        if pkg is None:
            return None

        status_upper = _normalize_approval_status(pkg.approval_status)
        reviewed_iso = pkg.reviewed_at.isoformat() if pkg.reviewed_at else None
        draft_text = pkg.draft or pkg.draft_response or ""
        return {
            "ticket_id": str(ticket_id),
            "intent": pkg.intent or "TECHNICAL_ESCALATION",
            "case_summary": pkg.case_summary,
            "draft": draft_text,
            "draft_response": pkg.draft_response or draft_text,
            "citations": list(pkg.citations or []),
            "missing_facts": list(pkg.missing_facts or []),
            "next_step": pkg.next_step,
            "approval_status": status_upper,
            "rejection_reason": pkg.review_note if status_upper == "REJECTED" else None,
            "approved_by": pkg.reviewed_by if status_upper == "APPROVED" else None,
            "approved_at": reviewed_iso if status_upper == "APPROVED" else None,
            "rejected_by": pkg.reviewed_by if status_upper == "REJECTED" else None,
            "rejected_at": reviewed_iso if status_upper == "REJECTED" else None,
        }
    except Exception as exc:
        logger.debug("Could not load copilot_packages for %s: %s", ticket_id, exc)
        return None


async def _persist_decision(
    ticket_id: str,
    *,
    approved: bool,
    reviewer: str,
    reason: Optional[str],
    reviewed_at: Optional[datetime] = None,
    draft: Optional[str] = None,
    db: Optional[AsyncSession] = None,
) -> bool:
    """Best-effort DB update; never blocks the API longer than DB_PERSIST_TIMEOUT_SECONDS."""
    try:
        return await asyncio.wait_for(
            _persist_decision_inner(
                ticket_id,
                approved=approved,
                reviewer=reviewer,
                reason=reason,
                reviewed_at=reviewed_at,
                draft=draft,
                db=db,
            ),
            timeout=DB_PERSIST_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning("Persisting approval decision for %s timed out (DB unreachable?)", ticket_id)
        return False


async def _persist_decision_inner(
    ticket_id: str,
    *,
    approved: bool,
    reviewer: str,
    reason: Optional[str],
    reviewed_at: Optional[datetime] = None,
    draft: Optional[str] = None,
    db: Optional[AsyncSession] = None,
) -> bool:
    """Best-effort DB update of `copilot_packages` (+ ticket status). Returns True if saved."""
    try:
        from models import CopilotPackage, Ticket

        ts = reviewed_at or datetime.now(timezone.utc)
        pkg_id = _to_uuid(ticket_id)

        async def _apply(session: AsyncSession) -> bool:
            pkg = (
                await session.execute(
                    select(CopilotPackage)
                    .where(CopilotPackage.ticket_id == pkg_id)
                    .order_by(CopilotPackage.updated_at.desc(), CopilotPackage.created_at.desc())
                )
            ).scalars().first()
            if pkg is None:
                return False
            pkg.approval_status = "APPROVED" if approved else "REJECTED"
            pkg.reviewed_by = reviewer
            pkg.reviewed_at = ts
            pkg.review_note = None if approved else reason
            if draft:
                pkg.draft = draft
                pkg.draft_response = draft
            ticket = (await session.execute(select(Ticket).where(Ticket.id == pkg_id))).scalars().first()
            if ticket is not None:
                ticket.status = "RESOLVED" if approved else "IN_PROGRESS"
                if approved:
                    ticket.assigned_to = reviewer
                ticket.updated_at = ts
            await session.commit()
            return True

        if db is not None:
            return await _apply(db)

        import app.main as app_main

        await app_main.ensure_db_initialized()
        async with app_main.AsyncSessionLocal() as session:
            return await _apply(session)
    except Exception as exc:  # DB not available (e.g. CRM-44 standalone run)
        logger.warning("Could not persist approval decision for %s: %s", ticket_id, exc)
        return False


async def get_approval_state(
    ticket_id: str, db: Optional[AsyncSession] = None
) -> dict[str, Any]:
    """Return Copilot draft, citations, approval_status, rejection_reason, and BPMN status (CRM-58)."""
    record = await _load_approval_from_db(ticket_id, db=db)
    if record is None:
        cached = _APPROVAL_CACHE.get(str(ticket_id))
        if cached is not None:
            record = dict(cached)

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Copilot approval package found for ticket '{ticket_id}'",
        )

    proc = await get_process_status(str(ticket_id))
    record["process_status"] = proc["status"] if proc else None
    record["process_instance_id"] = proc.get("process_instance_id") if proc else None
    return record


async def _review(
    ticket_id: str,
    *,
    approved: bool,
    reviewer: str,
    reason: Optional[str],
    draft: Optional[str] = None,
    db: Optional[AsyncSession] = None,
) -> dict[str, Any]:
    reviewed_dt = datetime.now(timezone.utc)
    reviewed_iso = reviewed_dt.isoformat()

    try:
        process = await complete_human_approval(
            ticket_id,
            approved=approved,
            reviewer=reviewer,
            reason=reason,
            approved_at=reviewed_iso,
        )
    except ProcessAlreadyReviewedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    persisted = await _persist_decision(
        ticket_id,
        approved=approved,
        reviewer=reviewer,
        reason=reason,
        reviewed_at=reviewed_dt,
        draft=draft,
        db=db,
    )
    decision = "APPROVED" if approved else "REJECTED"

    key = str(ticket_id)
    if key in _APPROVAL_CACHE or process is not None:
        entry = _APPROVAL_CACHE.setdefault(
            key,
            {
                "ticket_id": key,
                "intent": (process or {}).get("intent", "TECHNICAL_ESCALATION"),
                "draft": draft or "",
                "draft_response": draft or "",
                "citations": [],
                "missing_facts": [],
                "next_step": None,
            },
        )
        if draft:
            entry["draft"] = draft
            entry["draft_response"] = draft
        entry["approval_status"] = decision
        if approved:
            entry["approved_by"] = reviewer
            entry["approved_at"] = reviewed_iso
            entry["rejection_reason"] = None
        else:
            entry["rejected_by"] = reviewer
            entry["rejected_at"] = reviewed_iso
            entry["rejection_reason"] = reason

    body: dict[str, Any] = {
        "ticket_id": ticket_id,
        "status": decision,
        "approval_status": decision,
        "persisted": persisted,
        "process_status": process["status"] if process else None,
        "process_instance_id": process.get("process_instance_id") if process else None,
    }
    if approved:
        body["approved_by"] = reviewer
        body["approved_at"] = reviewed_iso
        body["rejection_reason"] = None
    else:
        body["rejected_by"] = reviewer
        body["rejected_at"] = reviewed_iso
        body["rejection_reason"] = reason
    return body


@approval_router.get("/{ticket_id}/approval")
async def get_copilot_approval(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_viewer_role),
) -> dict[str, Any]:
    """Return draft, citations, approval_status, and rejection_reason for `ticket_id` (CRM-58)."""
    return await get_approval_state(ticket_id, db=db)


@approval_router.patch("/{ticket_id}/approve")
async def approve_copilot_draft(
    ticket_id: str,
    payload: ApproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_approver_role),
) -> dict[str, Any]:
    """APPROVED + `approved_by` + `approved_at`; transitions Camunda User Task to `RESOLVED`."""
    reviewer = payload.approved_by or current_user.get("email") or "unknown"
    return await _review(
        ticket_id,
        approved=True,
        reviewer=reviewer,
        reason=None,
        draft=payload.draft,
        db=db,
    )


@approval_router.patch("/{ticket_id}/reject")
async def reject_copilot_draft(
    ticket_id: str,
    payload: RejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_approver_role),
) -> dict[str, Any]:
    """REJECTED + `rejection_reason`; transitions Camunda User Task to `REJECTED`."""
    reviewer = payload.rejected_by or current_user.get("email") or "unknown"
    return await _review(
        ticket_id,
        approved=False,
        reviewer=reviewer,
        reason=payload.rejection_reason,
        draft=payload.draft,
        db=db,
    )


# --- Official customer response export (CRM-59 / CRM-60) ------------------------------
_export_access = require_role("support_agent", "technical_approver", "administrator")


def _export_user(current_user: dict = Depends(get_current_user)) -> dict:
    return _export_access(_normalize_user_for_legacy_guard(current_user))


def _public_text(value: Any) -> str:
    """Remove internal identifiers and control characters before customer export."""
    text_value = str(value or "")
    text_value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[đã ẩn]", text_value)
    text_value = re.sub(
        r"(?im)^.*(?:system\s*prompt|internal\s*notes?|ghi chú nội bộ|prompt hệ thống).*$",
        "[đã ẩn]",
        text_value,
    )
    text_value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text_value)
    return text_value.strip()


def _citation_public_fields(citation: Any) -> dict[str, str]:
    """Whitelist customer-safe evidence fields; never serialize arbitrary metadata."""
    if not isinstance(citation, dict):
        return {}
    aliases = {
        "document": ("document_name", "document_title", "title"),
        "document_code": ("document_code", "code"),
        "section": ("section", "section_name", "section_number"),
        "version": ("version",),
        "status": ("status",),
        "page": ("page_number", "page"),
        "evidence": ("excerpt", "snippet", "content_snippet", "passage_content", "content"),
        "url": ("url", "source_url"),
    }
    result: dict[str, str] = {}
    for output_key, keys in aliases.items():
        for key in keys:
            value = citation.get(key)
            if value not in (None, ""):
                if output_key == "url" and not str(value).lower().startswith(("https://", "http://")):
                    continue
                result[output_key] = _public_text(value)
                break
    return result


def _build_customer_pdf(ticket: Any, package: Any, engineer_name: str) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise HTTPException(status_code=503, detail="PDF export dependency is not installed") from exc

    # Register a Unicode font when available so Vietnamese text renders correctly.
    font_name = "Helvetica"
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for font_path in font_candidates:
        try:
            pdfmetrics.registerFont(TTFont("SongNhatUnicode", font_path))
            font_name = "SongNhatUnicode"
            break
        except Exception:
            continue

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="SNBody",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=9,
            leading=14,
            alignment=TA_LEFT,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SNTitle",
            parent=styles["Title"],
            fontName=font_name,
            fontSize=17,
            leading=22,
            textColor=colors.HexColor("#17365D"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="SNHeading",
            parent=styles["Heading2"],
            fontName=font_name,
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#17365D"),
            spaceBefore=9,
        )
    )
    story = [
        Paragraph("SONGNHAT", styles["SNTitle"]),
        Paragraph("PHẢN HỒI HỖ TRỢ KỸ THUẬT CHÍNH THỨC", styles["SNHeading"]),
        Spacer(1, 5 * mm),
    ]
    ticket_number = _public_text(getattr(ticket, "ticket_number", "")) or str(ticket.id)
    story.append(Paragraph(f"<b>Mã Ticket:</b> {escape(ticket_number)}", styles["SNBody"]))
    story.append(Paragraph("<b>Tiêu đề:</b> " + escape(_public_text(ticket.subject)), styles["SNBody"]))
    story.append(Paragraph("<b>Nội dung hướng dẫn kỹ thuật</b>", styles["SNHeading"]))
    response_text = _public_text(package.draft_response or package.draft)
    if not response_text:
        raise HTTPException(status_code=409, detail="Approved customer response is empty")
    for paragraph in response_text.splitlines() or [response_text]:
        if paragraph.strip():
            story.append(Paragraph(escape(paragraph), styles["SNBody"]))

    story.append(Paragraph("Trích dẫn chứng cứ công khai", styles["SNHeading"]))
    citations = package.citations if isinstance(package.citations, list) else []
    safe_citations = [_citation_public_fields(item) for item in citations]
    safe_citations = [item for item in safe_citations if item]
    if safe_citations:
        for index, item in enumerate(safe_citations, 1):
            bits = []
            for label in ("document", "document_code", "section", "page", "version", "status", "evidence", "url"):
                if item.get(label):
                    bits.append(f"{label}: {item[label]}")
            story.append(Paragraph(escape(f"{index}. " + " | ".join(bits)), styles["SNBody"]))
    else:
        story.append(Paragraph("Không có trích dẫn chứng cứ công khai được lưu cho phản hồi này.", styles["SNBody"]))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("<b>Kỹ sư phê duyệt:</b> " + escape(_public_text(engineer_name)), styles["SNBody"]))
    story.append(
        Paragraph("Tài liệu được tạo tự động từ phản hồi đã được phê duyệt trên hệ thống SongNhat.", styles["SNBody"])
    )
    doc.build(story)
    return buffer.getvalue()


@approval_router.get("/{ticket_id}/export")
async def export_approved_response(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(_export_user),
) -> StreamingResponse:
    """Export the approved customer-facing response as a sanitized PDF (CRM-59 / CRM-60)."""
    from models import CopilotPackage, Ticket

    try:
        parsed_id = uuid.UUID(ticket_id)
    except ValueError:
        parsed_id = _to_uuid(ticket_id)

    ticket = (await db.execute(select(Ticket).where(Ticket.id == parsed_id))).scalars().first()
    package = (await db.execute(select(CopilotPackage).where(CopilotPackage.ticket_id == parsed_id))).scalars().first()
    if ticket is None or package is None:
        raise HTTPException(status_code=404, detail="Ticket or Copilot response not found")
    if str(package.approval_status).upper() != "APPROVED":
        raise HTTPException(status_code=409, detail="Only approved responses can be exported")
    if not package.reviewed_by:
        raise HTTPException(status_code=409, detail="Approval reviewer is missing")

    reviewer = user_repository.get_user_by_email(package.reviewed_by)
    reviewer_role = (reviewer or {}).get("role", "")
    if reviewer_role not in {"technical_approver", "ENGINEER", "engineer"}:
        raise HTTPException(status_code=403, detail="Response must be approved by an ENGINEER")
    engineer_name = (reviewer or {}).get("full_name") or "Kỹ sư phê duyệt"
    pdf_bytes = _build_customer_pdf(ticket, package, engineer_name)
    filename = f"SongNhat_Response_{_public_text(ticket.ticket_number or str(ticket.id))}.pdf"
    safe_filename = re.sub(r"[^A-Za-z0-9_.-]", "_", filename)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"', "Cache-Control": "no-store"},
    )


# If `camunda_workflow` was imported before `app.main`, `register_backend_components()` ran
# before routes were attached to `router` / `approval_router`; mount them now.
import app.main as _app_main  # noqa: E402

if _app_main._backend_components_registered and "/api/v1/copilot/{ticket_id}/approve" not in {
    getattr(r, "path", "") for r in _app_main.app.routes
}:
    _app_main.app.include_router(router, dependencies=[Depends(_app_main._copilot_role_guard)])
    _app_main.app.include_router(approval_router)
