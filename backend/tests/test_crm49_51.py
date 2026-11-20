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
