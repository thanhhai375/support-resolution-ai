"""Unit & Integration Test Suite for Task CRM-43:

[BE] Retriever thực — Full-text Search knowledge_passages thay thế mock data.

Dữ liệu mẫu được tạo TẠM THỜI bên trong file test này (không seed vào app startup)
để kiểm thử độc lập mà không phụ thuộc CRM-42 (Import CSV).
"""

import asyncio
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.schemas.copilot import CitationItem, IntentEnum
from app.services.copilot_engine import run_copilot_pipeline
from app.services.retriever import (
    KnowledgeRetriever,
    extract_search_tokens,
    get_mock_knowledge_passages,
    search_knowledge_passages,
)
from main import app, get_db
from migrations.runner import get_migration_sql
from models import Base, CopilotPackage, KnowledgePassage, Product

# =============================================================================
# FIXTURE: Tạo DB SQLite in-memory với dữ liệu mẫu TẠM THỜI chỉ dùng trong test
# (KHÔNG gọi seed_default_knowledge_data từ runner.py — tránh xung đột CRM-42)
# =============================================================================

TEST_PASSAGES = [
    # --- DRIVES ---
    {
        "document_name": "Tài liệu Hướng dẫn Xử lý Lỗi Biến tần SongNhat SN-G120",
        "section_name": "5.2 - Mã lỗi phần cứng và quá dòng",
        "page_number": 142,
        "passage_content": (
            "Mã lỗi F0022 (Powerstack Fault / Quá dòng phần cứng): Xuất hiện khi có dòng "
            "ngắn mạch tại IGBT, chạm đất đầu ra động cơ hoặc thời gian tăng tốc (P1120) "
            "cài đặt quá ngắn so với quán tính tải. Biến tần SN-G120 tự ngắt bảo vệ."
        ),
        "passage_metadata": {"version": "v2.4", "document_code": "SN-G120-ERR"},
        "product_code": "DRIVES",
    },
    {
        "document_name": "Sổ tay Bảo trì & Chẩn đoán Sự cố Truyền động Điện",
        "section_name": "3.4 - Quy trình đo cách điện",
        "page_number": 58,
        "passage_content": (
            "Khi lỗi F0022 xảy ra trong quá trình tăng tốc: (1) Kiểm tra cách điện cáp "
            "động cơ bằng đồng hồ Megohmmeter; (2) Kéo dài thời gian tăng tốc P1120; "
            "(3) Kiểm tra công suất định mức giữa biến tần và động cơ."
        ),
        "passage_metadata": {"version": "Rev. C (2024)", "document_code": "BT-CĐSD"},
        "product_code": "DRIVES",
    },
    {
        "document_name": "Hướng dẫn Vận hành ABB ACS580",
        "section_name": "10.3 - Fault Codes",
        "page_number": 312,
        "passage_content": (
            "Fault 2310 Overcurrent: Drive output current has exceeded the internal "
            "fault limit. Check motor cable and motor insulation. Verify that motor "
            "nominal values match drive parameters. Increase ramp times if needed."
        ),
        "passage_metadata": {"version": "3AUA0000074696 Rev L", "document_code": "ACS580-OP"},
        "product_code": "DRIVES",
    },
    {
        "document_name": "Hướng dẫn cài đặt biến tần SD700 — PID & Process Control",
        "section_name": "4.1 - Cài đặt vòng PID",
        "page_number": 45,
        "passage_content": (
            "Cài đặt thông số PID cho biến tần SD700: P2200=1 (kích hoạt PID), "
            "P2253 (setpoint), P2264 (phản hồi từ cảm biến 4-20mA). "
            "Hiệu chỉnh Kp (P2280), Ti (P2285), Td (P2274) để ổn định vòng lặp."
        ),
        "passage_metadata": {"version": "v1.5", "document_code": "SD700-PID"},
        "product_code": "DRIVES",
    },
    {
        "document_name": "Quy trình Thu thập Dữ kiện Kỹ thuật SongNhat (SOP-TECH-04)",
        "section_name": "2.1 - Thu thập dữ liệu lỗi biến tần",
        "page_number": 12,
        "passage_content": (
            "Đối với lỗi ngắt mạch phần cứng trên biến tần, nhân viên hỗ trợ cần thu "
            "thập: Mã Serial (S/N), Phiên bản Firmware, thông số dòng điện tại thời điểm "
            "ngắt (r0027) và ảnh chụp nhãn động cơ. Mã lỗi A0505 cần đo điện áp DC bus."
        ),
        "passage_metadata": {"version": "v1.2", "document_code": "SOP-TECH-04"},
        "product_code": "DRIVES",
    },
    {
        "document_name": "Hướng dẫn Cài đặt Nhanh Biến tần SN-G120",
        "section_name": "2.3 - Cài đặt tham số cơ bản",
        "page_number": 28,
        "passage_content": (
            "Cài đặt tham số cơ bản SN-G120: P0304 (điện áp định mức động cơ), "
            "P0305 (dòng định mức), P0307 (công suất kW), P0310 (tần số định mức Hz), "
            "P0311 (tốc độ định mức RPM). Thực hiện Auto-Tune P1910=1 sau khi cài đặt."
        ),
        "passage_metadata": {"version": "v2.1", "document_code": "SN-G120-QS"},
        "product_code": "DRIVES",
    },
    {
        "document_name": "Hướng dẫn Vận hành ABB ACS580",
        "section_name": "8.1 - Communication Faults",
        "page_number": 287,
        "passage_content": (
            "Fault F0001 (Mất tín hiệu truyền thông Modbus RTU): Kiểm tra kết nối RS485, "
            "địa chỉ slave (P2011), tốc độ baud (P2010). Đảm bảo đầu cuối mạng (120 Ohm "
            "termination resistor) được kết nối tại hai đầu đường truyền."
        ),
        "passage_metadata": {"version": "3AUA0000074696 Rev L", "document_code": "ACS580-OP"},
        "product_code": "DRIVES",
    },
    # --- MOTORS ---
    {
        "document_name": "Catalog Động cơ Servo SM Series — SongNhat",
        "section_name": "6.3 - Bảo vệ nhiệt Class F",
        "page_number": 89,
        "passage_content": (
            "Động cơ SM Series sử dụng cách điện Class F (155°C). Khi quá nhiệt vượt "
            "ngưỡng bảo vệ, PTC thermistor kích hoạt ngắt tự động. Kiểm tra độ thông "
            "thoáng quạt làm mát và nhiệt độ môi trường lắp đặt (tối đa 40°C ambient)."
        ),
        "passage_metadata": {"version": "2023-Edition", "document_code": "SM-CAT"},
        "product_code": "MOTORS",
    },
    {
        "document_name": "Sổ tay Bảo trì Động cơ ABB M2BAX — Megohmmeter & Bearing",
        "section_name": "5.1 - Đo cách điện và vòng bi",
        "page_number": 34,
        "passage_content": (
            "Đo cách điện stator bằng Megohmmeter 500VDC trước khi vận hành lại. "
            "Giá trị tối thiểu: 1 MΩ (ở nhiệt độ 25°C). Thay vòng bi (bearing) định kỳ "
            "mỗi 20.000 giờ hoặc khi phát hiện độ rung vượt 2.8 mm/s RMS."
        ),
        "passage_metadata": {"version": "ABB-M2BAX-2022", "document_code": "M2BAX-MT"},
        "product_code": "MOTORS",
    },
    {
        "document_name": "Hướng dẫn Lắp đặt Động cơ Servo SM Series",
        "section_name": "3.2 - Encoder và hệ trục",
        "page_number": 61,
        "passage_content": (
            "Encoder incremental 2500 ppr kết nối qua cáp chống nhiễu (shielded cable). "
            "Căn chỉnh hệ trục (shaft alignment) giữa động cơ và hộp số bằng laser aligner; "
            "dung sai song song ≤ 0.05mm, góc lệch ≤ 0.05°."
        ),
        "passage_metadata": {"version": "2023-Edition", "document_code": "SM-INST"},
        "product_code": "MOTORS",
    },
    # --- DRAFT (unapproved) --- Không được xuất hiện trong kết quả
    {
        "document_name": "Ghi chú Thử nghiệm Nội bộ [DRAFT]",
        "section_name": "DRAFT",
        "page_number": 1,
        "passage_content": "Tuyệt đối không được xuất hiện trong citations. DRAFT-TEST-99",
        "passage_metadata": {"version": "draft", "document_code": "DRAFT-TEST-99"},
        "product_code": "DRIVES",
        "is_approved": False,
    },
]


@pytest.fixture(scope="module")
def shared_db():
    """Tạo CSDL SQLite in-memory với 10 bản ghi mẫu (11 approved + 1 draft).

    Dữ liệu mẫu hoàn toàn tự chứa trong file test này, không gọi
    seed_default_knowledge_data() từ runner.py để tránh xung đột CRM-42.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()

    # Tạo 2 Product (DRIVES, MOTORS) để test lọc product_id
    prod_drives = Product(
        id=uuid.uuid4(), code="DRIVES", name="Biến tần (Drives)", description="Dòng biến tần SongNhat"
    )
    prod_motors = Product(
        id=uuid.uuid4(), code="MOTORS", name="Động cơ (Motors)", description="Dòng động cơ SongNhat"
    )
    session.add_all([prod_drives, prod_motors])
    session.flush()

    product_map = {"DRIVES": prod_drives, "MOTORS": prod_motors}

    for p in TEST_PASSAGES:
        prod = product_map[p["product_code"]]
        passage = KnowledgePassage(
            id=uuid.uuid4(),
            document_name=p["document_name"],
            section_name=p.get("section_name", ""),
            page_number=p["page_number"],
            passage_content=p["passage_content"],
            passage_metadata=p.get("passage_metadata", {}),
            is_approved=p.get("is_approved", True),
            product_id=prod.id,
        )
        session.add(passage)

    session.commit()
    yield session
    session.close()


# =============================================================================
# 1. KIỂM THỬ MIGRATION FILE & SQL DDL (Acceptance Criteria 1)
# =============================================================================

def test_migration_file_exists_and_content_matches():
    """Xác minh file migration 002 tồn tại và chứa đúng câu lệnh SQL kích hoạt pg_trgm + GIN index."""
    migration_file = (
        Path(__file__).resolve().parent.parent
        / "migrations"
        / "002_enable_pg_trgm_knowledge_passages.sql"
    )
    assert migration_file.exists(), f"Không tìm thấy file: {migration_file}"

    sql_content = migration_file.read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm;" in sql_content
    assert "CREATE INDEX IF NOT EXISTS idx_knowledge_passages_content_trgm" in sql_content
    assert "ON knowledge_passages USING gin (passage_content gin_trgm_ops);" in sql_content


def test_migration_runner_helper():
    """Xác minh hàm helper đọc SQL migration hoạt động chuẩn."""
    sql = get_migration_sql("002_enable_pg_trgm_knowledge_passages.sql")
    assert "pg_trgm" in sql
    assert "gin_trgm_ops" in sql


# =============================================================================
# 2. KIỂM THỬ BỘ TRÍCH XUẤT TỪ KHÓA (Token Extraction)
# =============================================================================

def test_extract_search_tokens_error_codes():
    """Trích xuất chính xác mã lỗi F0022, SD700, 2310, E001 từ chuỗi truy vấn."""
    q = "Biến tần SD700 báo lỗi F0022 và mã 2310 khi tăng tốc"
    tokens = extract_search_tokens(q)
    codes = tokens["codes"]
    assert "SD700" in codes or any("SD700" in c for c in codes)
    assert "F0022" in codes or any("F0022" in c for c in codes)
    assert "2310" in codes or any("2310" in c for c in codes)
    assert "biến tần" in tokens["phrases"]
    assert "tăng tốc" in tokens["phrases"]


# =============================================================================
# 3. KIỂM THỬ TRUY VẤN RETRIEVER THỰC TỪ CSDL (Full-text Search)
# =============================================================================

def test_retriever_real_search_f0022(shared_db):
    """Tìm kiếm 'F0022' phải trả về đúng đoạn trích kỹ thuật từ bảng knowledge_passages."""
    citations = asyncio.run(search_knowledge_passages(
        query="Biến tần báo lỗi F0022 khi tăng tốc",
        db=shared_db,
        limit=3,
    ))
    assert len(citations) >= 1
    assert any("F0022" in c.content_snippet for c in citations)
    assert any("SN-G120" in c.document_title or "Biến tần" in c.document_title for c in citations)
    assert citations[0].page_number > 0
    assert citations[0].passage_id is not None, "Bản ghi từ DB phải có passage_id"
    # Kiểm tra đủ 5 trường bắt buộc
    for c in citations:
        assert c.document_title, "Thiếu document_title"
        assert c.page_number > 0, "Thiếu page_number"
        assert c.section, "Thiếu section"
        assert c.version, "Thiếu version"
        assert c.content_snippet, "Thiếu content_snippet"


def test_retriever_real_search_overcurrent_2310(shared_db):
    """Tìm kiếm '2310 overcurrent' phải trả về tài liệu ABB ACS580 trang 312."""
    citations = asyncio.run(search_knowledge_passages(
        query="Lỗi 2310 Overcurrent trên biến tần",
        db=shared_db,
        limit=2,
    ))
    assert len(citations) >= 1
    first = citations[0]
    assert "2310" in first.content_snippet
    assert "Overcurrent" in first.content_snippet or "overcurrent" in first.content_snippet.lower()
    assert first.page_number == 312


def test_retriever_real_search_pid_sd700(shared_db):
    """Tìm kiếm 'cài đặt PID SD700' phải trả về tài liệu SD700 PID trang 45."""
    citations = asyncio.run(search_knowledge_passages(
        query="Hướng dẫn cài đặt thông số PID cho biến tần SD700",
        db=shared_db,
        limit=3,
    ))
    assert len(citations) >= 1
    matched = [c for c in citations if "SD700" in c.document_title and "PID" in c.content_snippet]
    assert len(matched) >= 1
    assert matched[0].page_number == 45


def test_retriever_real_search_motor_temperature(shared_db):
    """Tìm kiếm 'quá nhiệt động cơ' phải trả về Catalog SM Series trang 89."""
    citations = asyncio.run(search_knowledge_passages(
        query="Động cơ quá nhiệt nhiệt độ bảo vệ Class F",
        db=shared_db,
        limit=3,
    ))
    assert len(citations) >= 1
    matched = [c for c in citations if "quá nhiệt" in c.content_snippet or "155°C" in c.content_snippet]
    assert len(matched) >= 1


# =============================================================================
# 4. KIỂM THỬ BẢO MẬT: Chỉ trả về is_approved=True
# =============================================================================

def test_retriever_filters_out_unapproved_passages(shared_db):
    """Tuyệt đối không được trả về bản ghi có is_approved=False."""
    citations = asyncio.run(search_knowledge_passages(
        query="Tuyệt đối không được xuất hiện DRAFT-TEST-99",
        db=shared_db,
        limit=5,
    ))
    for c in citations:
        assert "Tuyệt đối không được xuất hiện trong citations" not in c.content_snippet
        assert "DRAFT-TEST-99" not in str(c.document_code)


# =============================================================================
# 5. KIỂM THỬ LỌC THEO PRODUCT_ID (Motors vs Drives)
# =============================================================================

def test_retriever_filter_by_product_id(shared_db):
    """Khi chỉ định product_id=MOTORS, kết quả chỉ bao gồm tài liệu về động cơ."""
    motors_prod = shared_db.query(Product).filter_by(code="MOTORS").first()
    assert motors_prod is not None

    citations = asyncio.run(search_knowledge_passages(
        query="Hướng dẫn bảo trì động cơ và đo độ rung",
        db=shared_db,
        limit=3,
        product_id=motors_prod.id,
    ))
    assert len(citations) >= 1
    for c in citations:
        assert (
            "M2BAX" in c.document_title
            or "Servo" in c.document_title
            or "động cơ" in c.document_title.lower()
        )


# =============================================================================
# 6. KIỂM THỬ FALLBACK: DB=None → mock; DB rỗng → mock
# =============================================================================

def test_retriever_fallback_when_db_is_none():
    """Khi db=None, hệ thống tự fallback về mock data mà không ném ngoại lệ."""
    citations = asyncio.run(search_knowledge_passages(
        query="Biến tần báo lỗi F0022 khi tăng tốc",
        db=None,
        limit=2,
    ))
    assert len(citations) == 2
    assert "SN-G120" in citations[0].document_title


def test_retriever_fallback_when_db_empty():
    """Khi DB tồn tại nhưng knowledge_passages rỗng, fallback về mock."""
    empty_engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(empty_engine)
    EmptySession = sessionmaker(bind=empty_engine, expire_on_commit=False)
    empty_session = EmptySession()

    try:
        citations = asyncio.run(search_knowledge_passages(
            query="Biến tần lỗi F0022",
            db=empty_session,
            limit=3,
        ))
        # Khi DB rỗng, phải trả về mock (không rỗng, không lỗi)
        assert len(citations) >= 1, "Phải fallback về mock khi bảng rỗng"
        # Mock data phải có document_title hợp lệ
        assert all(c.document_title for c in citations)
    finally:
        empty_session.close()


# =============================================================================
# 7. KIỂM THỬ ĐIỀU PHỐI PIPELINE (End-to-End với DB Thực)
# =============================================================================

def test_run_copilot_pipeline_with_real_db(shared_db):
    """Pipeline End-to-End tích hợp trích dẫn thực từ DB và tạo SupportPackageOut chuẩn."""
    test_tid = uuid.uuid4()
    pkg = asyncio.run(run_copilot_pipeline(
        ticket_description="Biến tần SD700 báo lỗi OC quá dòng E001",
        ticket_id=test_tid,
        db=shared_db,
    ))
    assert pkg.intent == IntentEnum.TECHNICAL_ESCALATION
    assert pkg.is_hazard_escalated is False
    assert len(pkg.citations) >= 1
    assert any("E001" in c.content_snippet or "SD700" in c.document_title for c in pkg.citations)
    assert pkg.citations[0].passage_id is not None
    assert pkg.summary is not None
    assert len(pkg.draft.split()) < 180

    # Kiểm tra bản ghi đã được lưu vào copilot_packages
    saved = shared_db.query(CopilotPackage).filter_by(ticket_id=test_tid).first()
    assert saved is not None
    assert saved.approval_status == "Pending"
    assert len(saved.citations) >= 1


def test_safety_hazard_overrides_retriever_even_with_db(shared_db):
    """Khi có nguy cơ an toàn (cháy/nổ/khói), citations=[] dù DB có dữ liệu."""
    pkg = asyncio.run(run_copilot_pipeline(
        ticket_description="Tủ điện biến tần có mùi khét, tia lửa và nguy cơ bốc cháy",
        db=shared_db,
    ))
    assert pkg.is_hazard_escalated is True
    assert pkg.citations == [], "Khi có nguy hiểm, citations bắt buộc phải là danh sách rỗng []"
    assert "CẢNH BÁO AN TOÀN" in pkg.draft


# =============================================================================
# 8. KIỂM THỬ API ENDPOINT FASTAPI
# =============================================================================

def test_api_analyze_endpoint_uses_real_retriever(shared_db):
    """Endpoint POST /api/copilot/analyze tích hợp Dependency DB và trả về trích dẫn thực."""
    app.dependency_overrides[get_db] = lambda: shared_db
    client = TestClient(app)

    res = client.post(
        "/api/copilot/analyze",
        json={"ticket_description": "Biến tần báo lỗi F0022 khi tăng tốc"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_hazard_escalated"] is False
    assert len(data["citations"]) >= 1
    assert data["citations"][0]["document_title"]
    assert data["citations"][0]["page_number"] > 0
    assert data["citations"][0]["content_snippet"]
    assert data["citations"][0]["passage_id"] is not None

    app.dependency_overrides.clear()


# =============================================================================
# 9. KIỂM THỬ RECALL@1 — 10 câu query thực tế
#    Mỗi query có 1 expected_doc (tên tài liệu kỳ vọng xuất hiện ở kết quả đầu tiên)
#    Recall@1 = số lần top-1 khớp / tổng số query  → assert >= 0.60
# =============================================================================

RECALL_QUERIES = [
    # (query, expected_keyword_in_doc_title_OR_snippet)
    ("Biến tần báo lỗi F0022 khi tăng tốc nhanh",          "F0022"),
    ("Lỗi 2310 Overcurrent ACS580",                         "2310"),
    ("Cài đặt vòng lặp PID biến tần SD700 P2200",           "SD700"),
    ("Động cơ Servo SM Series quá nhiệt Class F 155°C",     "155°C"),
    ("Đo cách điện stator Megohmmeter M2BAX bearing",       "M2BAX"),
    ("Mã lỗi A0505 thu thập Serial Firmware r0027",         "A0505"),
    ("Lỗi F0001 Modbus RTU mất tín hiệu truyền thông",      "F0001"),
    ("Cài đặt tham số cơ bản SN-G120 P0304 Auto-Tune",     "SN-G120"),
    ("Encoder incremental shaft alignment laser aligner",    "Encoder"),
    ("Tăng tốc P1120 cách điện cáp Megohmmeter",           "Megohmmeter"),
]


def test_recall_at_1_ten_queries(shared_db):
    """Chạy 10 câu query thực tế, tính Recall@1 và in bảng Markdown để copy vào PR.

    Recall@1 = tỷ lệ truy vấn mà kết quả đứng đầu (top-1) chứa từ khoá kỳ vọng.
    Ngưỡng chấp nhận: Recall@1 >= 0.60 (6/10 truy vấn).
    """
    rows = []
    hits = 0

    for idx, (query, expected_kw) in enumerate(RECALL_QUERIES, start=1):
        citations = asyncio.run(search_knowledge_passages(
            query=query,
            db=shared_db,
            limit=3,
        ))

        top1_title = citations[0].document_title if citations else "(no result)"
        top1_snippet = citations[0].content_snippet if citations else ""

        hit = expected_kw.lower() in top1_title.lower() or expected_kw.lower() in top1_snippet.lower()
        if hit:
            hits += 1

        rows.append({
            "no": idx,
            "query": query[:55] + ("…" if len(query) > 55 else ""),
            "expected": expected_kw,
            "top1": top1_title[:50] + ("…" if len(top1_title) > 50 else ""),
            "hit": "✅" if hit else "❌",
        })

    recall_at_1 = hits / len(RECALL_QUERIES)

    # In bảng Markdown ra console để copy vào comment PR
    print("\n")
    print("## CRM-43 Retriever — Recall@1 Evaluation (SQLite in-memory)\n")
    print(f"| # | Query | Expected kw | Top-1 Document | Hit |")
    print(f"|---|-------|-------------|----------------|-----|")
    for r in rows:
        print(f"| {r['no']} | {r['query']} | `{r['expected']}` | {r['top1']} | {r['hit']} |")
    print(f"\n**Recall@1 = {hits}/{len(RECALL_QUERIES)} = {recall_at_1:.0%}** "
          f"(ngưỡng tối thiểu: 60%)\n")

    assert recall_at_1 >= 0.60, (
        f"Recall@1 = {recall_at_1:.0%} < 60% — Retriever cần cải thiện thuật toán scoring."
    )
