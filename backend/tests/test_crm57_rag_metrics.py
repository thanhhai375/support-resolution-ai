"""Test Suite for Task CRM-61 (CRM-57 RAG Metrics):
- Hybrid Keyword + Vector Retriever (Recall@5 >= 90%) + Full Citation Metadata (CRM-62)
- Grounding Measurement & Verification (>= 95% & Zero Fabricated Citations)
- Token Budget Cap (8,000 input / 1,200 output / max 2 calls / HOLD quarantine)
- Telemetry Persistence in `copilot_packages` (model_version, prompt_version, token_usage, latency_ms)
"""

import asyncio
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Import app.main before models to keep SQLAlchemy Base initialization order safe
from app.main import app, get_db  # noqa: F401
from app.schemas.copilot import CitationItem, IntentEnum
from app.services.copilot_engine import (
    MAX_INPUT_TOKENS,
    MAX_MODEL_CALLS_PER_PACKAGE,
    MAX_OUTPUT_TOKENS,
    MAX_PASSAGE_CHARS,
    _apply_token_budget_to_context,
    _measure_and_verify_grounding,
    estimate_tokens,
    run_copilot_pipeline,
)
from app.services.retriever import search_knowledge_passages
from models import Base, CopilotPackage, KnowledgePassage, Product


CORPUS_PASSAGES = [
    {
        "id": uuid.UUID("10000000-0000-0000-0000-000000000001"),
        "product": "DRIVES",
        "document_name": "Tài liệu Hướng dẫn Xử lý Lỗi Biến tần SongNhat SN-G120",
        "document_code": "SN-G120-ERR",
        "section_number": "5.2",
        "section_name": "Mã lỗi phần cứng và quá dòng",
        "page_number": 142,
        "passage_content": (
            "Mã lỗi F0022 (Powerstack Fault / Quá dòng phần cứng): Xuất hiện khi có dòng "
            "ngắn mạch tại IGBT, chạm đất đầu ra động cơ hoặc thời gian tăng tốc (P1120) "
            "cài đặt quá ngắn so với quán tính tải. Biến tần SN-G120 tự ngắt bảo vệ."
        ),
        "meta": {
            "revision": "Rev. D",
            "version": "v2.4",
            "effective_status": "current",
            "effective_date": "2025-01-10",
            "product_model": "SN-G120",
            "deep_link": "https://kb.songnhat.vn/docs/sn-g120-err#page=142",
        },
    },
    {
        "id": uuid.UUID("10000000-0000-0000-0000-000000000002"),
        "product": "DRIVES",
        "document_name": "Sổ tay Bảo trì & Chẩn đoán Sự cố Truyền động Điện",
        "document_code": "BT-CDSD-01",
        "section_number": "3.4",
        "section_name": "Quy trình đo cách điện và tăng tốc",
        "page_number": 58,
        "passage_content": (
            "Khi lỗi F0022 xảy ra trong quá trình tăng tốc: (1) Kiểm tra cách điện cáp "
            "động cơ bằng đồng hồ Megohmmeter; (2) Kéo dài thời gian tăng tốc P1120; "
            "(3) Kiểm tra công suất định mức giữa biến tần và động cơ."
        ),
        "meta": {
            "revision": "Rev. C",
            "version": "Rev. C (2024)",
            "effective_status": "current",
            "effective_date": "2024-06-15",
        },
    },
    {
        "id": uuid.UUID("10000000-0000-0000-0000-000000000003"),
        "product": "DRIVES",
        "document_name": "Hướng dẫn Vận hành ABB ACS580",
        "document_code": "ACS580-OP",
        "section_number": "10.3",
        "section_name": "Fault Codes Overcurrent",
        "page_number": 312,
        "passage_content": (
            "Fault 2310 Overcurrent: Drive output current has exceeded the internal "
            "fault limit. Check motor cable and motor insulation. Verify that motor "
            "nominal values match drive parameters. Increase ramp times parameter 23.12."
        ),
        "meta": {
            "revision": "Rev. L",
            "version": "3AUA0000074696 Rev L",
            "effective_status": "current",
            "effective_date": "2025-02-01",
            "product_model": "ACS580",
        },
    },
    {
        "id": uuid.UUID("10000000-0000-0000-0000-000000000004"),
        "product": "DRIVES",
        "document_name": "Hướng dẫn cài đặt biến tần SD700",
        "document_code": "SD700-UM-V3",
        "section_number": "4.2",
        "section_name": "Cài đặt thông số PID",
        "page_number": 45,
        "passage_content": (
            "Cài đặt thông số PID cho biến tần SD700 ứng dụng bơm: P2200=1 (kích hoạt PID), "
            "P=2.0, I=0.5, D=0.1, P2253 (setpoint), P2264 (phản hồi 4-20mA). "
            "Giảm I nếu hệ thống dao động."
        ),
        "meta": {
            "revision": "3",
            "version": "v3.0",
            "effective_status": "current",
            "effective_date": "2024-05-01",
            "product_model": "SD700",
        },
    },
    {
        "id": uuid.UUID("10000000-0000-0000-0000-000000000005"),
        "product": "DRIVES",
        "document_name": "Hướng dẫn cài đặt biến tần SD700",
        "document_code": "SD700-UM-V3",
        "section_number": "5.1",
        "section_name": "Bảo vệ quá dòng E001",
        "page_number": 62,
        "passage_content": (
            "Lỗi OC (Over Current) E001 trên biến tần SD700: Kiểm tra (1) tải cơ khí có bị kẹt không, "
            "(2) cáp động lực đủ tiết diện, (3) cài đặt current limit tại P3.05 "
            "không vượt 150% định mức."
        ),
        "meta": {
            "revision": "3",
            "version": "v3.0",
            "effective_status": "current",
            "effective_date": "2024-05-01",
            "product_model": "SD700",
        },
    },
    {
        "id": uuid.UUID("10000000-0000-0000-0000-000000000006"),
        "product": "DRIVES",
        "document_name": "Hướng dẫn cài đặt biến tần SD700",
        "document_code": "SD700-UM-V4",
        "section_number": "7.1",
        "section_name": "Cài đặt encoder CN5",
        "page_number": 105,
        "passage_content": (
            "Encoder ABZ 1024 PPR cho biến tần SD700: kết nối dây A+/A-/B+/B-/Z+/Z- theo cổng CN5. "
            "Điện áp cấp 5V DC ±5%. Kiểm tra tín hiệu bằng oscilloscope tại P7.00=1."
        ),
        "meta": {
            "revision": "4",
            "version": "v4.0",
            "effective_status": "current",
            "effective_date": "2025-01-12",
            "product_model": "SD700",
        },
    },
    {
        "id": uuid.UUID("10000000-0000-0000-0000-000000000007"),
        "product": "DRIVES",
        "document_name": "Hướng dẫn Vận hành ABB ACS580",
        "document_code": "ACS580-OP",
        "section_number": "8.1",
        "section_name": "Communication Faults Modbus RTU",
        "page_number": 287,
        "passage_content": (
            "Fault F0001 (Mất tín hiệu truyền thông Modbus RTU): Kiểm tra kết nối RS485 với PLC, "
            "địa chỉ slave (P2011), tốc độ baud (P2010). Đảm bảo điện trở đầu cuối 120 Ohm "
            "được gắn tại hai đầu đường truyền."
        ),
        "meta": {
            "revision": "Rev. L",
            "version": "3AUA0000074696 Rev L",
            "effective_status": "current",
            "effective_date": "2025-02-01",
            "product_model": "ACS580",
        },
    },
    {
        "id": uuid.UUID("10000000-0000-0000-0000-000000000008"),
        "product": "DRIVES",
        "document_name": "Quy trình Thu thập Dữ kiện Kỹ thuật SongNhat (SOP-TECH-04)",
        "document_code": "SOP-TECH-04",
        "section_number": "2.1",
        "section_name": "Thu thập dữ liệu lỗi biến tần",
        "page_number": 12,
        "passage_content": (
            "Đối với lỗi ngắt mạch phần cứng trên biến tần, nhân viên hỗ trợ cần thu thập: "
            "Mã Serial (S/N), Phiên bản Firmware, thông số dòng điện tại thời điểm ngắt (r0027) "
            "và ảnh chụp nhãn động cơ. Mã lỗi A0505 quá áp cần đo điện áp DC bus."
        ),
        "meta": {
            "revision": "v1.2",
            "version": "v1.2",
            "effective_status": "current",
            "effective_date": "2024-03-01",
        },
    },
    {
        "id": uuid.UUID("10000000-0000-0000-0000-000000000009"),
        "product": "DRIVES",
        "document_name": "Tài liệu Hướng dẫn Vận hành & Cài đặt Biến tần SongNhat SN-G120",
        "document_code": "SN-G120-MAN",
        "section_number": "2.2",
        "section_name": "Sơ đồ đấu nối mạch động lực và điều khiển",
        "page_number": 15,
        "passage_content": (
            "Sơ đồ đấu nối mạch động lực và điều khiển SN-G120: Chân DI0-DI3 nhận tín hiệu "
            "kích hoạt RUN/STOP, cổng RS485 hỗ trợ giao thức Modbus RTU cho PLC."
        ),
        "meta": {
            "revision": "v1.5",
            "version": "v1.5",
            "effective_status": "current",
            "effective_date": "2025-01-05",
            "product_model": "SN-G120",
        },
    },
    {
        "id": uuid.UUID("10000000-0000-0000-0000-000000000010"),
        "product": "DRIVES",
        "document_name": "Hướng dẫn Cài đặt Nhanh Biến tần SN-G120",
        "document_code": "SN-G120-QS",
        "section_number": "2.3",
        "section_name": "Cài đặt tham số động cơ cơ bản",
        "page_number": 28,
        "passage_content": (
            "Cài đặt tham số cơ bản SN-G120: P0304 (điện áp định mức), P0305 (dòng định mức), "
            "P0307 (công suất kW), P0310 (tần số Hz), P0311 (tốc độ RPM). "
            "Thực hiện Auto-Tune P1910=1 sau khi nhập nhãn động cơ."
        ),
        "meta": {
            "revision": "v2.1",
            "version": "v2.1",
            "effective_status": "current",
            "effective_date": "2025-01-05",
            "product_model": "SN-G120",
        },
    },
    {
        "id": uuid.UUID("10000000-0000-0000-0000-000000000011"),
        "product": "MOTORS",
        "document_name": "Catalog Động cơ Servo SM Series — SongNhat",
        "document_code": "SM-CAT-V2",
        "section_number": "6.3",
        "section_name": "Bảo vệ nhiệt Class F",
        "page_number": 89,
        "passage_content": (
            "Động cơ Servo SM Series sử dụng cách điện Class F (155°C). Khi quá nhiệt vượt ngưỡng "
            "bảo vệ, PTC thermistor kích hoạt ngắt tự động. Kiểm tra quạt làm mát và nhiệt độ "
            "môi trường lắp đặt tối đa 40°C."
        ),
        "meta": {
            "revision": "Rev. 2",
            "version": "2023-Edition",
            "effective_status": "current",
            "effective_date": "2024-01-06",
        },
    },
    {
        "id": uuid.UUID("10000000-0000-0000-0000-000000000012"),
        "product": "MOTORS",
        "document_name": "Sổ tay Bảo trì Động cơ ABB M2BAX — Megohmmeter & Bearing",
        "document_code": "M2BAX-MT",
        "section_number": "5.1",
        "section_name": "Đo cách điện stator và vòng bi",
        "page_number": 34,
        "passage_content": (
            "Đo cách điện stator động cơ M2BAX bằng Megohmmeter 500VDC trước khi vận hành lại. "
            "Giá trị tối thiểu 1 MΩ ở 25°C. Thay vòng bi (bearing) định kỳ mỗi 20.000 giờ hoặc "
            "khi độ rung vượt 2.8 mm/s RMS."
        ),
        "meta": {
            "revision": "Rev. E",
            "version": "ABB-M2BAX-2022",
            "effective_status": "current",
            "effective_date": "2024-02-15",
            "product_model": "M2BAX",
        },
    },
    {
        "id": uuid.UUID("10000000-0000-0000-0000-000000000013"),
        "product": "MOTORS",
        "document_name": "ABB M2BAX Low Voltage Cast Iron Motors Manual",
        "document_code": "3GZF500730-87",
        "section_number": "4.2",
        "section_name": "Electrical Connection & Starting Troubleshooting",
        "page_number": 28,
        "passage_content": (
            "If an ABB M2BAX 3-phase motor fails to start after 380V power is applied, "
            "verify phase-to-phase voltage balance (tolerance ±5%), inspect thermal overload "
            "relay trip state, and confirm star/delta terminal link configuration."
        ),
        "meta": {
            "revision": "Rev. G",
            "version": "Rev. G (2025)",
            "effective_status": "current",
            "effective_date": "2025-01-20",
            "product_model": "M2BAX",
        },
    },
    {
        "id": uuid.UUID("10000000-0000-0000-0000-000000000014"),
        "product": "MOTORS",
        "document_name": "Hướng dẫn Lắp đặt Động cơ Servo SM Series",
        "document_code": "SM-INST",
        "section_number": "3.2",
        "section_name": "Encoder và căn chỉnh hệ trục",
        "page_number": 61,
        "passage_content": (
            "Encoder incremental 2500 ppr kết nối qua cáp chống nhiễu (shielded cable). "
            "Căn chỉnh hệ trục (shaft alignment) bằng laser aligner; dung sai song song <= 0.05mm."
        ),
        "meta": {
            "revision": "2023-Edition",
            "version": "2023-Edition",
            "effective_status": "current",
            "effective_date": "2024-01-06",
        },
    },
    # --- Tài liệu đã superseded / withdrawn: KHÔNG được xuất hiện trong kết quả ---
    {
        "id": uuid.UUID("10000000-0000-0000-0000-000000000098"),
        "product": "DRIVES",
        "document_name": "Hướng dẫn cài đặt biến tần SD700 (Bản cũ)",
        "document_code": "SD700-UM-V2",
        "section_number": "7.1",
        "section_name": "Cài đặt encoder cũ",
        "page_number": 102,
        "passage_content": "Encoder ABZ 1024 PPR kết nối theo sơ đồ cũ SD700. Đã được thay thế.",
        "meta": {
            "revision": "2",
            "version": "v2.0",
            "effective_status": "superseded",
            "supersession_link": "SD700-UM-V4",
            "product_model": "SD700",
        },
    },
    {
        "id": uuid.UUID("10000000-0000-0000-0000-000000000099"),
        "product": "DRIVES",
        "document_name": "Tài liệu nội bộ SN-G120 đã thu hồi",
        "document_code": "SN-G120-WD",
        "section_number": "9.9",
        "section_name": "Thu hồi",
        "page_number": 99,
        "passage_content": "Mã lỗi F0022 hướng dẫn cũ đã bị thu hồi không được áp dụng.",
        "meta": {
            "revision": "v1.0",
            "version": "v1.0",
            "effective_status": "withdrawn",
            "product_model": "SN-G120",
        },
    },
]


@pytest.fixture(scope="module")
def rag_db():
    """Khởi tạo SQLite in-memory DB với tập corpus kỹ thuật Motors & Drives."""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()

    prod_drives = Product(id=uuid.uuid4(), code="DRIVES", name="Biến tần (Drives)")
    prod_motors = Product(id=uuid.uuid4(), code="MOTORS", name="Động cơ (Motors)")
    session.add_all([prod_drives, prod_motors])
    session.flush()
    prod_map = {"DRIVES": prod_drives.id, "MOTORS": prod_motors.id}

    now = datetime.now(timezone.utc)
    for item in CORPUS_PASSAGES:
        session.add(
            KnowledgePassage(
                id=item["id"],
                product_id=prod_map[item["product"]],
                document_name=item["document_name"],
                document_code=item["document_code"],
                section_number=item["section_number"],
                section_name=item["section_name"],
                page_number=item["page_number"],
                passage_content=item["passage_content"],
                is_approved=True,
                approved_at=now,
                approved_by="knowledge_steward@songnhat.vn",
                passage_metadata=item["meta"],
            )
        )
    session.commit()
    yield session
    session.close()


# =============================================================================
# 1. RECALL@5 >= 90% & CITATION METADATA CONTRACT (CRM-61 / CRM-62)
# =============================================================================

EVAL_RECALL5_QUERIES = [
    ("Biến tần SN-G120 báo lỗi F0022 khi tăng tốc", "SN-G120-ERR"),
    ("Kiểm tra cách điện cáp động cơ bằng Megohmmeter khi lỗi F0022", "BT-CDSD-01"),
    ("ABB ACS580 báo lỗi 2310 overcurrent", "ACS580-OP"),
    ("Cài đặt vòng lặp PID P2200 cho biến tần SD700", "SD700-UM-V3"),
    ("Biến tần SD700 báo lỗi quá dòng E001", "SD700-UM-V3"),
    ("Đấu nối encoder ABZ 1024 PPR cổng CN5 trên SD700", "SD700-UM-V4"),
    ("Lỗi F0001 mất tín hiệu truyền thông Modbus RTU RS485", "ACS580-OP"),
    ("Mã lỗi A0505 đo điện áp DC bus và thông số dòng r0027", "SOP-TECH-04"),
    ("Sơ đồ đấu nối chân DI0-DI3 và cổng RS485 SN-G120", "SN-G120-MAN"),
    ("Thực hiện Auto-Tune P1910 và cài đặt thông số P0304 SN-G120", "SN-G120-QS"),
    ("Động cơ Servo SM Series bị nóng quá nhiệt vượt 155°C", "SM-CAT-V2"),
    ("Kiểm tra vòng bi bearing bị rung quá 2.8 mm/s trên M2BAX", "M2BAX-MT"),
    ("Đo cách điện stator bằng đồng hồ Megohmmeter 500VDC", "M2BAX-MT"),
    ("Động cơ 3 pha M2BAX cấp nguồn 380V nhưng không khởi động", "3GZF500730-87"),
    ("Căn chỉnh hệ trục laser aligner và encoder 2500 ppr SM Series", "SM-INST"),
    ("bien tan sn-g120 bao loi f0022 qua dong igbt", "SN-G120-ERR"),
    ("mat ket noi plc qua rs485 modbus rtu", "ACS580-OP"),
    ("motor M2BAX fails to start star delta terminal", "3GZF500730-87"),
    ("bo dieu khien pid bom nuoc sd700 bi dao dong", "SD700-UM-V3"),
    ("quat lam mat dong co servo bi nong moi truong 40 do", "SM-CAT-V2"),
]


def test_hybrid_retriever_recall_at_5_ge_90(rag_db):
    """RFP Section 8: Retriever phải đạt Recall@5 >= 90% trên tập đánh giá mẫu."""
    hits = 0
    rows = []
    for idx, (query, expected_doc_code) in enumerate(EVAL_RECALL5_QUERIES, start=1):
        citations = asyncio.run(search_knowledge_passages(query=query, db=rag_db, limit=5))
        assert len(citations) <= 10
        returned_codes = [c.document_code for c in citations[:5]]
        hit = expected_doc_code in returned_codes
        if hit:
            hits += 1
        rows.append((idx, query[:45], expected_doc_code, returned_codes[:3], hit))

    recall_at_5 = hits / len(EVAL_RECALL5_QUERIES)
    print(f"\n[CRM-61] Hybrid Retriever Recall@5 = {hits}/{len(EVAL_RECALL5_QUERIES)} = {recall_at_5:.1%}")
    assert recall_at_5 >= 0.90, f"Recall@5 = {recall_at_5:.1%} < 90%; details={rows}"


def test_citation_metadata_fields_and_status_filtering(rag_db):
    """Kiểm tra CitationItem xuất đủ 10 metadata cho Frontend CRM-62 và lọc bỏ superseded/withdrawn."""
    # 1. Citation có deep_link
    cits_link = asyncio.run(search_knowledge_passages("Biến tần SN-G120 lỗi F0022", db=rag_db, limit=5))
    assert len(cits_link) >= 1
    first = cits_link[0]
    assert first.passage_id == "10000000-0000-0000-0000-000000000001"
    assert first.document_title
    assert first.revision == "Rev. D"
    assert first.section
    assert first.page_number == 142
    assert first.status == "current"
    assert first.effective_date == "2025-01-10"
    assert first.deep_link == "https://kb.songnhat.vn/docs/sn-g120-err#page=142"
    # Đảm bảo bản withdrawn không lọt vào kết quả
    assert all(c.status == "current" for c in cits_link)
    assert all("thu hồi" not in c.document_title.lower() for c in cits_link)

    # 2. Citation không có deep_link -> phải sinh stable_ref theo đúng format chuẩn
    cits_nolink = asyncio.run(search_knowledge_passages("Encoder ABZ 1024 PPR SD700 CN5", db=rag_db, limit=5))
    assert len(cits_nolink) >= 1
    enc_cit = next(c for c in cits_nolink if c.document_code == "SD700-UM-V4")
    assert enc_cit.deep_link is None
    assert enc_cit.stable_ref == (
        f"{enc_cit.document_title} | Rev {enc_cit.revision} | "
        f"Mục {enc_cit.section} | Trang {enc_cit.page_number}"
    )
    # Đảm bảo bản superseded (SD700-UM-V2) bị lọc bỏ hoàn toàn
    assert all(c.document_code != "SD700-UM-V2" for c in cits_nolink)


# =============================================================================
# 2. GROUNDING >= 95% & ZERO FABRICATED CITATIONS
# =============================================================================

def test_pipeline_grounding_score_ge_95_and_no_fabricated_citations(rag_db):
    """Draft và Summary phải có grounding_score >= 0.95 và 100% passage_id có thật."""
    queries = [
        "Biến tần SN-G120 báo lỗi F0022 khi tăng tốc",
        "Biến tần SD700 báo lỗi quá dòng E001",
        "Xin tài liệu hướng dẫn sơ đồ đấu nối SN-G120",
    ]
    for q in queries:
        pkg = asyncio.run(run_copilot_pipeline(ticket_description=q, db=rag_db, limit=5))
        assert pkg.status == "COMPLETED"
        assert pkg.grounding_score >= 0.95, f"Grounding score thấp ({pkg.grounding_score}) cho '{q}': {pkg.draft}"
        assert len(pkg.draft.split()) < 180

        valid_ids = {c.passage_id for c in pkg.citations if c.passage_id}
        assert len(valid_ids) >= 1
        found_ids = re.findall(r"\[passage_id:([^\]]+)\]", pkg.draft)
        assert len(found_ids) >= 1, f"Draft thiếu passage_id đối chứng: {pkg.draft}"
        for fid in found_ids:
            assert fid in valid_ids, f"Phát hiện trích dẫn bịa đặt {fid} không có trong citations!"


def test_measure_and_verify_grounding_strips_fabricated_ids():
    """Hàm _measure_and_verify_grounding() phải xóa 100% passage_id bịa đặt và hạ điểm grounding."""
    real_cit = CitationItem(
        passage_id="real-passage-001",
        document_title="SN-G120 Manual",
        page_number=142,
        content_snippet="Lỗi F0022 do ngắn mạch IGBT hoặc thời gian tăng tốc P1120 quá ngắn.",
        revision="Rev. D",
        status="current",
    )
    tampered_draft = (
        "Theo SN-G120 Manual (trang 142, [passage_id:real-passage-001]): "
        "Lỗi F0022 do ngắn mạch IGBT hoặc thời gian tăng tốc P1120 quá ngắn. "
        "Ngoài ra theo tài liệu giả [passage_id:FAKE-999], cần thay tụ nguồn ngay."
    )
    res = _measure_and_verify_grounding(draft=tampered_draft, citations=[real_cit])
    assert "FAKE-999" not in res["cleaned_draft"]
    assert "FAKE-999" in res["removed_fabricated_ids"]
    assert "real-passage-001" in res["verified_passage_ids"]
    assert res["grounding_score"] < 0.95


# =============================================================================
# 3. TOKEN BUDGET CAP (8K INPUT / 1.2K OUTPUT / MAX 2 CALLS / HOLD)
# =============================================================================

def test_token_budget_constants_and_safe_passage_quarantine():
    """Kiểm tra hằng số 8k/1.2k/2 calls và cơ chế quarantine nguyên passage không cắt ngang."""
    assert MAX_INPUT_TOKENS == 8000
    assert MAX_OUTPUT_TOKENS == 1200
    assert MAX_MODEL_CALLS_PER_PACKAGE == 2
    assert MAX_PASSAGE_CHARS == 8000
    assert estimate_tokens("") == 0
    assert estimate_tokens("Biến tần lỗi F0022") > 0

    normal_cit = CitationItem(
        passage_id="p-ok",
        document_title="SN-G120 Manual",
        page_number=10,
        content_snippet="Kiểm tra thông số P1120 và cách điện cáp động cơ.",
        revision="v1.0",
        status="current",
    )
    oversized_cit = CitationItem(
        passage_id="p-huge",
        document_title="Oversized Dump",
        page_number=1,
        content_snippet="A" * 8500,
        revision="v1.0",
        status="current",
    )
    selected, quarantined, in_toks, hold_reason = _apply_token_budget_to_context(
        ticket_description="Biến tần báo lỗi F0022",
        citations=[normal_cit, oversized_cit],
    )
    assert hold_reason is None
    assert len(selected) == 1 and selected[0].passage_id == "p-ok"
    assert len(quarantined) == 1 and quarantined[0]["passage_id"] == "p-huge"
    assert "8000" in quarantined[0]["reason"] or "cách ly" in quarantined[0]["reason"].lower()


def test_oversized_ticket_triggers_hold_without_hanging(rag_db):
    """Ticket vượt 8,000 input tokens phải kích hoạt HOLD kèm lý do và tra cứu thủ công."""
    huge_ticket = "Biến tần SD700 báo lỗi E001. " + ("chi tiết lỗi kéo dài " * 2000)
    pkg = asyncio.run(run_copilot_pipeline(ticket_description=huge_ticket, db=rag_db))
    assert pkg.status == "HOLD"
    assert pkg.hold_reason is not None and len(pkg.hold_reason) > 0
    assert "HOLD" in pkg.next_step or "thủ công" in pkg.next_step.lower()
    assert len(pkg.draft.split()) < 180


def test_provider_timeout_and_call_cap_enforce_hold(rag_db):
    """Provider timeout, lỗi hoặc vượt quá 2 calls/1200 output tokens phải trả HOLD an toàn."""
    # Case A: Timeout -> HOLD không treo
    async def slow_provider(prompt, max_tokens, attempt):
        assert max_tokens <= 1200
        await asyncio.sleep(0.5)
        return "unreachable"

    pkg_timeout = asyncio.run(
        run_copilot_pipeline(
            ticket_description="Biến tần SN-G120 báo lỗi F0022",
            db=rag_db,
            model_caller=slow_provider,
            provider_timeout_seconds=0.05,
        )
    )
    assert pkg_timeout.status == "HOLD"
    assert "timeout" in (pkg_timeout.hold_reason or "").lower()

    # Case B: Output luôn vượt 1,200 tokens ở cả 2 lần gọi -> dừng sau 2 calls và trả HOLD
    call_counter = {"count": 0}

    def verbose_provider(prompt, max_tokens, attempt):
        call_counter["count"] += 1
        assert max_tokens <= 1200
        return "token " * 1500

    pkg_over = asyncio.run(
        run_copilot_pipeline(
            ticket_description="Biến tần SN-G120 báo lỗi F0022",
            db=rag_db,
            model_caller=verbose_provider,
        )
    )
    assert call_counter["count"] == MAX_MODEL_CALLS_PER_PACKAGE
    assert pkg_over.status == "HOLD"
    assert pkg_over.token_usage["calls_used"] == MAX_MODEL_CALLS_PER_PACKAGE


# =============================================================================
# 4. TELEMETRY IN COPILOT_PACKAGES (model_version, prompt_version, token_usage, latency_ms)
# =============================================================================

def test_telemetry_persisted_in_copilot_packages(rag_db):
    """Lưu đủ 4 trường telemetry vào bảng `copilot_packages` và trả về trong response."""
    tid = uuid.uuid4()
    pkg = asyncio.run(
        run_copilot_pipeline(
            ticket_description="Biến tần SD700 báo lỗi quá dòng E001",
            ticket_id=tid,
            db=rag_db,
            limit=5,
        )
    )
    assert pkg.status == "COMPLETED"
    assert pkg.model_version
    assert pkg.prompt_version
    assert pkg.latency_ms >= 0.0
    assert pkg.token_usage["input_tokens"] > 0
    assert pkg.token_usage["input_tokens"] <= MAX_INPUT_TOKENS
    assert pkg.token_usage["output_tokens"] > 0
    assert pkg.token_usage["output_tokens"] <= MAX_OUTPUT_TOKENS
    assert pkg.token_usage["total_tokens"] == (
        pkg.token_usage["input_tokens"] + pkg.token_usage["output_tokens"]
    )

    saved = rag_db.query(CopilotPackage).filter_by(ticket_id=tid).first()
    assert saved is not None
    assert saved.model_version == pkg.model_version
    assert saved.prompt_version == pkg.prompt_version
    assert saved.token_usage == pkg.token_usage
    assert saved.latency_ms == pkg.latency_ms
    assert saved.package_status == "COMPLETED"
    assert saved.grounding_score == pkg.grounding_score
