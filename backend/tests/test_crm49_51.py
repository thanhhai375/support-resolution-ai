"""Unit tests cho CRM-49 (Disable mock citation fallback) và CRM-51 (Model/Serial/Revision/Status filters & Abstention)."""

import asyncio
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.copilot import CitationItem, IntentEnum
from app.services.copilot_engine import (
    _classify_intent_from_text,
    _compose_neutral_draft,
    _detect_missing_facts,
    run_copilot_pipeline,
)
from app.services.retriever import (
    KnowledgeRetriever,
    get_mock_knowledge_passages,
    search_knowledge_passages,
)
from models import Base, KnowledgePassage, Product


# =============================================================================
# FIXTURE: CSDL SQLite in-memory cho test suite CRM-49 & CRM-51
# =============================================================================

@pytest.fixture(scope="module")
def memory_db():
    """Tạo CSDL SQLite in-memory với bảng đầy đủ và dữ liệu kiểm thử chuẩn."""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()

    # Tạo products
    prod_drives = Product(id=uuid.uuid4(), code="DRIVES", name="Biến tần")
    prod_motors = Product(id=uuid.uuid4(), code="MOTORS", name="Động cơ")
    session.add_all([prod_drives, prod_motors])
    session.flush()

    # Dữ liệu phục vụ kiểm thử CRM-49 & CRM-51 (Model, Revision, Status, Serial)
    test_passages = [
        # 1. SD700 Rev.A — current, approved
        KnowledgePassage(
            id=uuid.uuid4(),
            document_name="Hướng dẫn vận hành SD700",
            section_name="Cài đặt thông số",
            section_number="2.1",
            page_number=15,
            passage_content="Biến tần SD700: Cài đặt thông số điều khiển V/f và vector.",
            passage_metadata={"version": "rev.A", "revision": "rev.A", "effective_status": "current", "product_model": "SD700", "serial_range": "SN1000-SN5000"},
            is_approved=True,
            product_id=prod_drives.id,
        ),
        # 2. SD700 Rev.C — current, approved
        KnowledgePassage(
            id=uuid.uuid4(),
            document_name="Hướng dẫn vận hành SD700 bản cập nhật",
            section_name="Mã lỗi và xử lý",
            section_number="5.1",
            page_number=42,
            passage_content="Biến tần SD700 rev.C: Khắc phục lỗi quá dòng E001 bằng cách tăng ramp time.",
            passage_metadata={"version": "rev.C", "revision": "rev.C", "effective_status": "current", "product_model": "SD700", "serial_range": "SN1000-SN5000"},
            is_approved=True,
            product_id=prod_drives.id,
        ),
        # 3. ACS580 — current, approved (Model khác)
        KnowledgePassage(
            id=uuid.uuid4(),
            document_name="Hướng dẫn vận hành ABB ACS580",
            section_name="Troubleshooting",
            section_number="8.1",
            page_number=88,
            passage_content="Biến tần ABB ACS580: Báo lỗi 2310 quá dòng phần cứng.",
            passage_metadata={"version": "v1.0", "revision": "v1.0", "effective_status": "current", "product_model": "ACS580"},
            is_approved=True,
            product_id=prod_drives.id,
        ),
        # 4. [MODEL_A] — Draft, unapproved (MODEL-10)
        KnowledgePassage(
            id=uuid.uuid4(),
            document_name="Tài liệu thiết kế MODEL_A [DRAFT]",
            section_name="Nháp",
            section_number="1.0",
            page_number=1,
            passage_content="Tài liệu nháp MODEL_A chưa được duyệt. Không được dùng.",
            passage_metadata={"version": "draft", "effective_status": "draft", "product_model": "MODEL_A"},
            is_approved=False,
            product_id=prod_drives.id,
        ),
        # 5. [MODEL_A] — Revoked / Withdrawn (MODEL-20)
        KnowledgePassage(
            id=uuid.uuid4(),
            document_name="Tài liệu MODEL_A cũ đã thu hồi",
            section_name="Lưu trữ",
            section_number="9.0",
            page_number=99,
            passage_content="Tài liệu MODEL_A đã bị thu hồi quyền truy cập và sử dụng.",
            passage_metadata={"version": "v1.0", "effective_status": "withdrawn", "product_model": "MODEL_A"},
            is_approved=True,
            product_id=prod_drives.id,
        ),
        # 6. MODEL_A-H (Biến thể H — MODEL-06)
        KnowledgePassage(
            id=uuid.uuid4(),
            document_name="Manual MODEL_A-H Heavy Duty",
            section_name="Thông số",
            section_number="3.0",
            page_number=20,
            passage_content="Model MODEL_A-H: Tải nặng công nghiệp, yêu cầu tản nhiệt cưỡng bức.",
            passage_metadata={"version": "rev.1", "effective_status": "current", "product_model": "MODEL_A-H"},
            is_approved=True,
            product_id=prod_drives.id,
        ),
    ]
    session.add_all(test_passages)
    session.commit()

    yield session
    session.close()


# =============================================================================
# PHẦN 1: UNIT TESTS CRM-49 (LOẠI BỎ FALLBACK MOCK TRÊN LUỒNG TRUY VẤN THẬT)
# =============================================================================

class TestCRM49DisableMockFallback:
    """CRM-49: Không fallback về mock data khi truy vấn CSDL thật."""

    def test_empty_db_returns_empty_list(self):
        """Khi DB rỗng và db!=None, trả về [] tuyệt đối không có mock citations."""
        empty_engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)
        Base.metadata.create_all(empty_engine)
        EmptySession = sessionmaker(bind=empty_engine, expire_on_commit=False)
        empty_session = EmptySession()

        try:
            citations = asyncio.run(search_knowledge_passages(
                query="Biến tần báo lỗi F0022 khi tăng tốc",
                db=empty_session,
                limit=3,
                allow_mock_fallback=False,
            ))
            # CRM-49: Phải trả về [] rỗng, KHÔNG được có mock citation F0022/SN-G120
            assert citations == [], f"Kỳ vọng [] nhưng nhận được: {citations}"
        finally:
            empty_session.close()

    def test_db_exception_returns_empty_list(self):
        """Khi truy vấn DB gặp ngoại lệ, ghi log và trả về [], không crash và không fallback mock."""
        mock_db = MagicMock()
        mock_db.execute.side_effect = RuntimeError("Mất kết nối database mô phỏng")

        citations = asyncio.run(search_knowledge_passages(
            query="Biến tần báo lỗi F0022",
            db=mock_db,
            limit=3,
            allow_mock_fallback=False,
        ))
        assert citations == [], f"Kỳ vọng [] khi lỗi DB nhưng nhận được: {citations}"

    def test_mock_allowed_when_db_is_none(self):
        """Khi db is None (unit test thuần), vẫn trả về mock citations để tương thích ngược."""
        citations = asyncio.run(search_knowledge_passages(
            query="Biến tần báo lỗi F0022",
            db=None,
            limit=3,
        ))
        assert len(citations) >= 1
        assert any("F0022" in c.content_snippet for c in citations)

    def test_allow_mock_fallback_flag_explicit(self):
        """Khi tham số allow_mock_fallback=True được bật tường minh, cho phép fallback."""
        empty_engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)
        Base.metadata.create_all(empty_engine)
        EmptySession = sessionmaker(bind=empty_engine, expire_on_commit=False)
        empty_session = EmptySession()

        try:
            citations = asyncio.run(search_knowledge_passages(
                query="Biến tần báo lỗi F0022",
                db=empty_session,
                limit=3,
                allow_mock_fallback=True,
            ))
            assert len(citations) >= 1
        finally:
            empty_session.close()

    def test_real_db_returns_complete_metadata(self, memory_db):
        """Khi DB có dữ liệu, trả về đầy đủ metadata (status, product_model, serial_range)."""
        citations = asyncio.run(search_knowledge_passages(
            query="SD700 V/f",
            db=memory_db,
            limit=3,
            allow_mock_fallback=False,
        ))
        assert len(citations) >= 1
        c = citations[0]
        assert c.document_title
        assert c.page_number > 0
        assert c.content_snippet
        assert c.section
        assert c.version
        assert c.status is not None
        assert c.passage_id is not None


# =============================================================================
# PHẦN 2: UNIT TESTS CRM-51 (MODEL / SERIAL / REVISION / STATUS & ABSTENTION)
# =============================================================================

class TestCRM51ModelApplicability:
    """Kiểm tra nhận diện và ràng buộc Model (MODEL-01, MODEL-02, MODEL-03, MODEL-05, MODEL-06, MODEL-12)."""

    def test_model_01_missing_model(self, memory_db):
        """MODEL-01: 'Xin manual của động cơ, chưa biết model' -> không tự chọn default, trả về []."""
        q = "Xin manual của động cơ, chưa biết model"
        citations = asyncio.run(search_knowledge_passages(query=q, db=memory_db, limit=3))
        assert citations == [], f"Kỳ vọng [] khi thiếu model nhưng nhận được: {citations}"

        # Kiểm tra missing facts yêu cầu model
        facts = _detect_missing_facts(q, IntentEnum.DOCUMENT_REQUEST)
        assert any("model" in f.lower() or "mã hiệu" in f.lower() for f in facts)

    def test_model_03_conflicting_models(self, memory_db):
        """MODEL-03: 'Mô tả đầu ghi MODEL_A, cuối ghi MODEL_B' -> xung đột model, dừng truy xuất."""
        q = "Mô tả đầu ghi MODEL_A, cuối ghi MODEL_B"
        citations = asyncio.run(search_knowledge_passages(query=q, db=memory_db, limit=3))
        assert citations == [], f"Kỳ vọng [] khi xung đột model nhưng nhận được: {citations}"

        facts = _detect_missing_facts(q, IntentEnum.DOCUMENT_REQUEST)
        assert any("mâu thuẫn" in f.lower() or "xác nhận" in f.lower() or "model" in f.lower() for f in facts)

    def test_model_02_serial_without_model_mapping(self, memory_db):
        """MODEL-02: 'Chỉ có serial [SERIAL_A], chưa có bảng liên kết model' -> không suy luận model."""
        q = "Chỉ có serial [SERIAL_A], chưa có bảng liên kết model"
        citations = asyncio.run(search_knowledge_passages(query=q, db=memory_db, limit=3))
        assert citations == [], f"Kỳ vọng [] khi chỉ có serial chưa có mapping nhưng nhận được: {citations}"

    def test_model_05_serial_out_of_range(self, memory_db):
        """MODEL-05: 'Serial [SERIAL_B] ngoài dải áp dụng của manual MODEL_A' -> từ chối nguồn."""
        q = "Serial [SERIAL_B] ngoài dải áp dụng của manual MODEL_A"
        citations = asyncio.run(search_knowledge_passages(query=q, db=memory_db, limit=3))
        assert citations == [], f"Kỳ vọng [] khi serial ngoài dải áp dụng nhưng nhận được: {citations}"

    def test_model_06_model_variant_mismatch(self, memory_db):
        """MODEL-06: Khách hỏi biến thể MODEL_A-X trong khi DB chỉ có MODEL_A-H -> loại bỏ biến thể không khớp."""
        q = "Xin manual cho biến thể MODEL_A-X"
        citations = asyncio.run(search_knowledge_passages(query=q, db=memory_db, limit=3))
        # Không được trả về MODEL_A-H
        for c in citations:
            assert "MODEL_A-H" not in (c.product_model or "")
            assert "MODEL_A-H" not in c.document_title

    def test_model_12_wrong_model_rejected(self, memory_db):
        """MODEL-12: Ticket hỏi ACS580 nhưng tài liệu là SD700 -> chỉ trả về đúng model ACS580."""
        q = "Biến tần ACS580 báo lỗi 2310"
        citations = asyncio.run(search_knowledge_passages(query=q, db=memory_db, limit=3))
        assert len(citations) >= 1
        for c in citations:
            assert "SD700" not in c.document_title, f"Sai model: nguồn SD700 bị trả về cho câu hỏi ACS580: {c.document_title}"


class TestCRM51RevisionApplicability:
    """Kiểm tra tính áp dụng của phiên bản Revision (MODEL-04, MODEL-17, VN-09)."""

    def test_model_04_revision_mismatch_rejected(self, memory_db):
        """MODEL-04: 'Cần rev.C nhưng hệ thống chỉ có rev.A đã lỗi thời' -> không trả về rev.A."""
        # Chỉ tạo DB có rev.A
        temp_engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)
        Base.metadata.create_all(temp_engine)
        Session = sessionmaker(bind=temp_engine, expire_on_commit=False)
        sess = Session()
        try:
            p = KnowledgePassage(
                id=uuid.uuid4(),
                document_name="SD700 manual",
                passage_content="SD700 nội dung cũ",
                passage_metadata={"version": "rev.A", "revision": "rev.A", "effective_status": "current", "product_model": "SD700"},
                is_approved=True,
            )
            sess.add(p)
            sess.commit()

            q = "Cần rev.C nhưng hệ thống chỉ có rev.A đã lỗi thời"
            citations = asyncio.run(search_knowledge_passages(query=q, db=sess, limit=3))
            # Không được trả về rev.A như bản phù hợp
            for c in citations:
                assert "rev.a" not in (c.version or "").lower(), f"Trả về rev.A đã lỗi thời: {c.version}"
        finally:
            sess.close()

    def test_model_17_revision_conflict_rejected(self, memory_db):
        """MODEL-17: 'Manual rev.D mới hơn nhưng máy cũ cần rev.C' -> không trả về rev.D."""
        temp_engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)
        Base.metadata.create_all(temp_engine)
        Session = sessionmaker(bind=temp_engine, expire_on_commit=False)
        sess = Session()
        try:
            p = KnowledgePassage(
                id=uuid.uuid4(),
                document_name="Manual rev.D mới",
                passage_content="Nội dung rev.D",
                passage_metadata={"version": "rev.D", "revision": "rev.D", "effective_status": "current"},
                is_approved=True,
            )
            sess.add(p)
            sess.commit()

            q = "Manual rev.D mới hơn nhưng máy cũ cần rev.C"
            citations = asyncio.run(search_knowledge_passages(query=q, db=sess, limit=3))
            for c in citations:
                assert "rev.d" not in (c.version or "").lower(), f"Trả về rev.D sai phạm vi cho máy cần rev.C: {c.version}"
        finally:
            sess.close()

    def test_vn_09_exclude_revision(self, memory_db):
        """VN-09: 'Cần tài liệu rev.B, đừng dùng rev.A' -> loại trừ rev.A."""
        q = "Cần tài liệu SD700, đừng dùng rev.A"
        citations = asyncio.run(search_knowledge_passages(query=q, db=memory_db, limit=3))
        for c in citations:
            assert "rev.a" not in (c.version or "").lower(), f"Đã yêu cầu không dùng rev.A nhưng bị trả về: {c.version}"


class TestCRM51StatusApplicability:
    """Kiểm tra lọc bỏ tài liệu Draft, Withdrawn, Revoked, Superseded (MODEL-10, MODEL-20, DAT 04, SEC 04)."""

    def test_model_10_draft_status_rejected(self, memory_db):
        """MODEL-10: Tài liệu đúng model nhưng trạng thái Draft (is_approved=False) -> tuyệt đối không trả về."""
        q = "Tài liệu thiết kế MODEL_A"
        citations = asyncio.run(search_knowledge_passages(query=q, db=memory_db, limit=3))
        for c in citations:
            assert "[DRAFT]" not in c.document_title, f"Tài liệu Draft bị lọt vào citations: {c.document_title}"
            assert c.status != "draft"

    def test_model_20_withdrawn_status_rejected(self, memory_db):
        """MODEL-20: Tài liệu đúng model nhưng đã bị thu hồi quyền (withdrawn) -> không sử dụng hay xuất."""
        q = "Tài liệu MODEL_A cũ đã thu hồi"
        citations = asyncio.run(search_knowledge_passages(query=q, db=memory_db, limit=3))
        for c in citations:
            assert "thu hồi" not in c.document_title.lower(), f"Tài liệu bị thu hồi bị lọt vào citations: {c.document_title}"
            assert c.status != "withdrawn"


class TestCRM51AbstentionAndHonestDraft:
    """Kiểm tra hành vi từ chối trung thực (Abstention) khi citations=[] (SUP 03, SUP 07)."""

    def test_empty_citations_document_request_honest_draft(self):
        """Khi citations=[] trong DOCUMENT_REQUEST: nêu rõ không có nguồn phù hợp, KHÔNG bịa đã trích xuất."""
        draft = _compose_neutral_draft(
            ticket_description="Xin manual của động cơ, chưa biết model",
            intent=IntentEnum.DOCUMENT_REQUEST,
            citations=[],
            missing_facts=["Mã hiệu model chính xác của thiết bị"],
        )
        # SUP 03 / CRM-51: Tuyệt đối KHÔNG có cụm từ khẳng định đã đính kèm tài liệu
        assert "đã trích xuất các phần hướng dẫn" not in draft, f"Tuyên bố trích xuất tài liệu khi citations rỗng: {draft}"
        assert "không có nguồn phù hợp" in draft, f"Thiếu thông báo không có nguồn phù hợp: {draft}"
        # Đề xuất chuyển kỹ sư
        assert "kỹ sư" in draft.lower() or "ky su" in draft.lower()
        # Giới hạn < 180 từ
        assert len(draft.split()) < 180

    def test_empty_citations_technical_escalation_honest_draft(self):
        """Khi citations=[] trong TECHNICAL_ESCALATION: nêu rõ không có nguồn phù hợp, KHÔNG có IGBT template."""
        draft = _compose_neutral_draft(
            ticket_description="Biến tần báo lỗi E-01 khi chạy 7,5 kW",
            intent=IntentEnum.TECHNICAL_ESCALATION,
            citations=[],
            missing_facts=["Mã Serial (S/N) của thiết bị"],
        )
        assert "không có nguồn phù hợp" in draft, f"Thiếu thông báo không có nguồn phù hợp: {draft}"
        assert "IGBT" not in draft, f"Chứa template IGBT cứng: {draft}"
        assert "P1120" not in draft, f"Chứa template P1120 cứng: {draft}"
        # Giữ nguyên thực thể kỹ thuật
        assert "E-01" in draft
        assert "7,5 kW" in draft
        assert len(draft.split()) < 180

    def test_pipeline_with_missing_model_returns_empty_citations_and_honest_draft(self, memory_db):
        """E2E Pipeline: Ticket thiếu model -> citations=[], draft trung thực không bịa nguồn."""
        pkg = asyncio.run(run_copilot_pipeline(
            ticket_description="Xin manual của động cơ, chưa biết model",
            db=memory_db,
        ))
        assert pkg.citations == [], f"Kỳ vọng citations=[] nhưng nhận được: {pkg.citations}"
        assert "không có nguồn phù hợp" in pkg.draft
        assert "đã trích xuất các phần hướng dẫn" not in pkg.draft
        assert pkg.is_hazard_escalated is False
        assert len(pkg.draft.split()) < 180
