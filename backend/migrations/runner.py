"""Database Migration & Initialization Runner for SongNhat Copilot (Task CRM-43)."""

import inspect
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import uuid

from sqlalchemy import func, select, text

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent


def get_migration_sql(filename: str = "002_enable_pg_trgm_knowledge_passages.sql") -> str:
    """Đọc nội dung file migration SQL."""
    filepath = MIGRATIONS_DIR / filename
    if filepath.exists():
        return filepath.read_text(encoding="utf-8")
    return (
        "CREATE EXTENSION IF NOT EXISTS pg_trgm;\n"
        "CREATE INDEX IF NOT EXISTS idx_knowledge_passages_content_trgm\n"
        "ON knowledge_passages USING gin (passage_content gin_trgm_ops);\n"
    )


async def seed_default_knowledge_data(db: Any) -> None:
    """Tự động nạp bộ dữ liệu kỹ thuật chuẩn (Motors & Drives) nếu bảng knowledge_passages đang trống."""
    try:
        try:
            from models import Category, KnowledgePassage, Product
        except ImportError:
            from backend.models import Category, KnowledgePassage, Product

        # Kiểm tra số lượng bản ghi hiện có
        count_stmt = select(func.count(KnowledgePassage.id))
        count_res = db.execute(count_stmt)
        if inspect.isawaitable(count_res):
            count_res = await count_res
        total_passages = count_res.scalar() or 0
        if total_passages > 0:
            return

        logger.info("Bảng knowledge_passages đang trống. Bắt đầu seed bộ dữ liệu tri thức kỹ thuật chuẩn...")

        # 1. Khởi tạo danh mục sản phẩm (MOTORS và DRIVES)
        prod_map: dict[str, Product] = {}
        defaults = [
            ("MOTORS", "Động cơ (Motors)", "Động cơ điện hạ thế, trung thế và servo SongNhat / ABB."),
            ("DRIVES", "Biến tần (Drives)", "Biến tần công nghiệp và bộ điều khiển truyền động SongNhat / ABB."),
        ]
        for code, name, desc in defaults:
            p_stmt = select(Product).where(func.upper(Product.code) == code)
            p_res = db.execute(p_stmt)
            if inspect.isawaitable(p_res):
                p_res = await p_res
            prod = p_res.scalars().first() if hasattr(p_res, "scalars") else None
            if not prod:
                prod = Product(code=code, name=name, description=desc)
                db.add(prod)
                flush_res = db.flush()
                if inspect.isawaitable(flush_res):
                    await flush_res
            prod_map[code] = prod

        # 2. Khởi tạo danh mục nghiệp vụ
        cat_defaults = [
            ("DOCUMENT_REQUEST", "Yêu cầu tài liệu", "Cung cấp tài liệu, sơ đồ đấu nối và hướng dẫn vận hành."),
            ("SERVICE_PROGRESS", "Tiến độ dịch vụ", "Theo dõi tiến độ sửa chữa, bảo hành thiết bị."),
            ("TECHNICAL_ESCALATION", "Chuyển cấp kỹ thuật", "Xử lý sự cố lỗi kỹ thuật, cảnh báo bất thường."),
        ]
        for cat_code, cat_name, cat_desc in cat_defaults:
            c_stmt = select(Category).where(func.upper(Category.code) == cat_code)
            c_res = db.execute(c_stmt)
            if inspect.isawaitable(c_res):
                c_res = await c_res
            cat = c_res.scalars().first() if hasattr(c_res, "scalars") else None
            if not cat:
                cat = Category(code=cat_code, name=cat_name, description=cat_desc)
                db.add(cat)
                flush_res = db.flush()
                if inspect.isawaitable(flush_res):
                    await flush_res

        now = datetime.now(timezone.utc)
        motors_id = prod_map["MOTORS"].id
        drives_id = prod_map["DRIVES"].id

        # 3. Danh sách các đoạn trích kỹ thuật chuẩn đã phê duyệt
        seed_passages = [
            # --- DRIVES PASSAGES ---
            KnowledgePassage(
                product_id=drives_id,
                document_name="Tài liệu Hướng dẫn Xử lý Lỗi Biến tần SongNhat SN-G120",
                document_code="SN-G120-ERR-01",
                section_number="5.2",
                section_name="Mã lỗi phần cứng và quá dòng",
                page_number=142,
                passage_content=(
                    "Mã lỗi F0022 (Powerstack Fault / Quá dòng phần cứng): Xuất hiện khi "
                    "có dòng ngắn mạch tại IGBT, chạm đất đầu ra động cơ hoặc thời gian "
                    "tăng tốc (P1120) cài đặt quá ngắn so với quán tính tải."
                ),
                is_approved=True,
                approved_at=now,
                approved_by="technical-lead@songnhat.vn",
                passage_metadata={"version": "v2.4", "doc_version": "v2.4", "language": "VI"},
            ),
            KnowledgePassage(
                product_id=drives_id,
                document_name="Sổ tay Bảo trì & Chẩn đoán Sự cố Truyền động Điện",
                document_code="SOP-MAINT-DRV-02",
                section_number="3.4",
                section_name="Quy trình đo cách điện và thông số tăng tốc",
                page_number=58,
                passage_content=(
                    "Khi lỗi F0022 xảy ra trong quá trình tăng tốc: (1) Kiểm tra cách điện "
                    "cáp động cơ bằng đồng hồ Megohmmeter; (2) Kéo dài thời gian tăng tốc "
                    "P1120; (3) Kiểm tra công suất định mức giữa biến tần và động cơ."
                ),
                is_approved=True,
                approved_at=now,
                approved_by="technical-lead@songnhat.vn",
                passage_metadata={"version": "Rev. C (2024)", "language": "VI"},
            ),
            KnowledgePassage(
                product_id=drives_id,
                document_name="Quy trình Thu thập Dữ kiện Kỹ thuật SongNhat (SOP-TECH-04)",
                document_code="SOP-TECH-04",
                section_number="2.1",
                section_name="Thu thập dữ liệu lỗi biến tần ngắt mạch",
                page_number=12,
                passage_content=(
                    "Đối với các lỗi ngắt mạch phần cứng trên biến tần, nhân viên hỗ trợ "
                    "cần thu thập Mã Serial (S/N), Phiên bản Firmware, thông số dòng điện "
                    "tại thời điểm ngắt (r0027) và ảnh chụp nhãn động cơ."
                ),
                is_approved=True,
                approved_at=now,
                approved_by="qa-engineer@songnhat.vn",
                passage_metadata={"version": "v1.2", "language": "VI"},
            ),
            KnowledgePassage(
                product_id=drives_id,
                document_name="Hướng dẫn cài đặt biến tần SD700",
                document_code="SD700-UM-V3",
                section_number="4.2",
                section_name="Cài đặt thông số PID",
                page_number=45,
                passage_content=(
                    "Để cài đặt PID cho ứng dụng bơm: P=2.0, I=0.5, D=0.1. "
                    "Điều chỉnh tăng P nếu hệ thống phản hồi chậm. Giảm I nếu hệ thống dao động."
                ),
                is_approved=True,
                approved_at=now,
                approved_by="drives-specialist@songnhat.vn",
                passage_metadata={"version": "v3.0", "language": "VI"},
            ),
            KnowledgePassage(
                product_id=drives_id,
                document_name="Hướng dẫn cài đặt biến tần SD700",
                document_code="SD700-UM-V3",
                section_number="5.1",
                section_name="Bảo vệ quá dòng",
                page_number=62,
                passage_content=(
                    "Lỗi OC (Over Current) E001: Kiểm tra (1) tải cơ khí có bị kẹt không, "
                    "(2) cáp động lực đủ tiết diện, (3) cài đặt current limit tại P3.05 "
                    "không vượt 150% định mức."
                ),
                is_approved=True,
                approved_at=now,
                approved_by="drives-specialist@songnhat.vn",
                passage_metadata={"version": "v3.0", "language": "VI"},
            ),
            KnowledgePassage(
                product_id=drives_id,
                document_name="Tài liệu Hướng dẫn Vận hành & Cài đặt Biến tần SongNhat SN-G120",
                document_code="SN-G120-MAN-01",
                section_number="2.2",
                section_name="Sơ đồ đấu nối mạch động lực và điều khiển",
                page_number=15,
                passage_content=(
                    "Sơ đồ đấu nối mạch động lực và điều khiển: Chân DI0-DI3 nhận tín hiệu "
                    "kích hoạt RUN/STOP, cổng RS485 hỗ trợ giao thức Modbus RTU cho PLC."
                ),
                is_approved=True,
                approved_at=now,
                approved_by="technical-lead@songnhat.vn",
                passage_metadata={"version": "v1.5", "language": "VI"},
            ),
            KnowledgePassage(
                product_id=drives_id,
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
                product_id=drives_id,
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

            # --- MOTORS PASSAGES ---
            KnowledgePassage(
                product_id=motors_id,
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
                product_id=motors_id,
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
                product_id=motors_id,
                document_name="Catalog động cơ Servo SM Series",
                document_code="SM-CAT-V2",
                section_number="3.1",
                section_name="Thông số vận hành và tần số",
                page_number=18,
                passage_content=(
                    "Dải tần số hoạt động bình thường: 5–60Hz. Tại tần số dưới 5Hz có thể "
                    "xuất hiện rung động do mô-men không ổn định. Tăng ramp time lên tối thiểu "
                    "5 giây để giảm rung."
                ),
                is_approved=True,
                approved_at=now,
                approved_by="knowledge_steward@songnhat.vn",
                passage_metadata={"version": "Rev. 2", "language": "VI"},
            ),
            KnowledgePassage(
                product_id=motors_id,
                document_name="Catalog động cơ Servo SM Series",
                document_code="SM-CAT-V2",
                section_number="6.3",
                section_name="Bảo vệ nhiệt độ",
                page_number=89,
                passage_content=(
                    "Bảo vệ quá nhiệt kích hoạt tại 155°C (Class F). Nhiệt độ môi trường tối đa cho phép: "
                    "40°C. Trên 40°C cần giảm tải 2%/°C. Fault nhấp nháy 3 lần = lỗi thermal overload."
                ),
                is_approved=True,
                approved_at=now,
                approved_by="knowledge_steward@songnhat.vn",
                passage_metadata={"version": "Rev. 2", "language": "VI"},
            ),

            # --- DRAFT RECORD (is_approved=False) để kiểm tra bộ lọc an toàn ---
            KnowledgePassage(
                product_id=drives_id,
                document_name="Bản thảo nội bộ Chưa phê duyệt — SongNhat Testing",
                document_code="DRAFT-TEST-99",
                section_number="9.9",
                section_name="Ghi chú thử nghiệm nội bộ",
                page_number=1,
                passage_content="Ghi chú thử nghiệm nội bộ chưa phê duyệt — Tuyệt đối không được xuất hiện trong citations.",
                is_approved=False,
                passage_metadata={"version": "draft-0.1"},
            ),
        ]

        db.add_all(seed_passages)
        c_res = db.commit()
        if inspect.isawaitable(c_res):
            await c_res
        logger.info("Đã seed thành công %d bản ghi tri thức kỹ thuật vào CSDL.", len(seed_passages))
    except Exception as exc:
        logger.warning("Không thể seed dữ liệu mẫu vào knowledge_passages: %s", exc)
        if hasattr(db, "rollback"):
            rb = db.rollback()
            if inspect.isawaitable(rb):
                await rb


async def run_migrations(engine: Any) -> None:
    """Tự động kiểm tra và thực thi migration pg_trgm + GIN index và cấu trúc bảng lúc khởi động app."""
    try:
        try:
            from models import Base
        except ImportError:
            from backend.models import Base

        dialect_name = getattr(engine.dialect, "name", "")
        logger.info("Kiểm tra migration CSDL cho dialect: %s", dialect_name)

        if dialect_name == "postgresql":
            # Tạo bảng nếu chưa có
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

                # Thực thi migration pg_trgm và GIN index
                logger.info("Thực thi migration pg_trgm & GIN index cho PostgreSQL...")
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
                await conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_knowledge_passages_content_trgm "
                        "ON knowledge_passages USING gin (passage_content gin_trgm_ops);"
                    )
                )
                # CRM-60: normalize approval status constraint and ensure audit table exists.
                await conn.execute(text("ALTER TABLE copilot_packages DROP CONSTRAINT IF EXISTS chk_copilot_approval_status"))
                await conn.execute(text(
                    "ALTER TABLE copilot_packages ADD CONSTRAINT chk_copilot_approval_status "
                    "CHECK (UPPER(approval_status) IN ('PENDING', 'APPROVED', 'REJECTED'))"
                ))
                # CRM-61: add telemetry, grounding, and budget hold columns safely.
                for ddl in (
                    "ALTER TABLE copilot_packages ADD COLUMN IF NOT EXISTS model_version VARCHAR(100)",
                    "ALTER TABLE copilot_packages ADD COLUMN IF NOT EXISTS prompt_version VARCHAR(100)",
                    "ALTER TABLE copilot_packages ADD COLUMN IF NOT EXISTS token_usage JSONB DEFAULT '{}'::jsonb",
                    "ALTER TABLE copilot_packages ADD COLUMN IF NOT EXISTS latency_ms DOUBLE PRECISION",
                    "ALTER TABLE copilot_packages ADD COLUMN IF NOT EXISTS package_status VARCHAR(30) DEFAULT 'COMPLETED'",
                    "ALTER TABLE copilot_packages ADD COLUMN IF NOT EXISTS hold_reason TEXT",
                    "ALTER TABLE copilot_packages ADD COLUMN IF NOT EXISTS grounding_score DOUBLE PRECISION",
                ):
                    await conn.execute(text(ddl))
            logger.info("Hoàn tất migration 002: pg_trgm & idx_knowledge_passages_content_trgm thành công!")
        else:
            # SQLite hoặc cơ sở dữ liệu thử nghiệm khác
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Khởi tạo cấu trúc bảng CSDL (%s) thành công.", dialect_name)

    except Exception as exc:
        logger.warning("Lưu ý khi chạy migration tự động: %s", exc)
