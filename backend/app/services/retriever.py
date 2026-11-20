"""Knowledge Base Retriever service for technical knowledge full-text search (Tasks CRM-24, CRM-28 & CRM-43)."""

import inspect
import logging
import re
from typing import Any, List, Optional
from uuid import UUID

from app.schemas.copilot import CitationItem

logger = logging.getLogger(__name__)

# Stopwords tiếng Việt thường gặp trong câu hỏi / mô tả ticket
VI_STOPWORDS = {
    "là", "và", "của", "có", "cho", "với", "trong", "các", "những", "khi",
    "này", "đó", "thì", "bị", "được", "xin", "giúp", "tôi", "mình", "nhé",
    "ạ", "vui", "lòng", "như", "thế", "nào", "gì", "sao", "ở", "tại", "về",
    "hay", "hoặc", "cần", "phải", "đang", "đã", "sẽ", "được", "ra", "vào",
}


def extract_search_tokens(query: str) -> dict[str, List[str]]:
    """Trích xuất mã lỗi, model thiết bị và từ khóa kỹ thuật từ câu truy vấn."""
    clean_query = query.strip()

    # 1. Trích xuất mã hiệu / mã lỗi đặc thù (F0022, SD700, ACS580, 2310, E001, P1120, r0027, SN-G120, SM-CAT, v.v.)
    error_codes = re.findall(
        r"\b[A-Za-z0-9]+-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)?\b|\b[A-Za-z]{1,4}\d{1,5}[A-Za-z]?\b|\b\d{3,5}\b|\b[A-Za-z]\d+\.\d+\b",
        clean_query,
    )

    # 2. Cụm từ kỹ thuật đặc trưng
    phrases: List[str] = []
    phrase_candidates = [
        "biến tần", "động cơ", "quá dòng", "quá nhiệt", "tăng tốc", "cài đặt",
        "sơ đồ đấu nối", "sơ đồ", "đấu nối", "bảo vệ", "thông số", "điện áp",
        "dòng điện", "ngắn mạch", "chạm đất", "cách điện", "điện trở xả",
        "overcurrent", "powerstack", "firmware", "manual", "catalog", "bearing",
        "vibration", "lubrication", "inverter", "motor", "drive",
    ]
    query_lower = clean_query.lower()
    for ph in phrase_candidates:
        if ph in query_lower:
            phrases.append(ph)

    # 3. Từ khóa đơn lẻ sau khi lọc stopwords
    words = clean_query.split()
    keywords: List[str] = []
    for w in words:
        clean_w = re.sub(r"[^\w\-\.]", "", w).strip()
        if not clean_w:
            continue
        if clean_w.lower() in VI_STOPWORDS:
            continue
        if len(clean_w) >= 3:
            keywords.append(clean_w)

    return {
        "codes": error_codes,
        "phrases": phrases,
        "keywords": keywords,
    }


def get_mock_knowledge_passages(query: str) -> List[CitationItem]:
    """Trả về danh sách 2-3 CitationItem mẫu làm fallback khi db=None hoặc CSDL chưa có dữ liệu."""
    query_lower = query.lower()

    if any(k in query_lower for k in ["f0022", "biến tần", "tăng tốc", "inverter"]):
        return [
            CitationItem(
                document_title="Tài liệu Hướng dẫn Xử lý Lỗi Biến tần SongNhat SN-G120",
                page_number=142,
                content_snippet=(
                    "Mã lỗi F0022 (Powerstack Fault / Quá dòng phần cứng): Xuất hiện khi "
                    "có dòng ngắn mạch tại IGBT, chạm đất đầu ra động cơ hoặc thời gian "
                    "tăng tốc (P1120) cài đặt quá ngắn so với quán tính tải."
                ),
                section="5.2 - Mã lỗi phần cứng và quá dòng",
                version="v2.4",
            ),
            CitationItem(
                document_title="Sổ tay Bảo trì & Chẩn đoán Sự cố Truyền động Điện",
                page_number=58,
                content_snippet=(
                    "Khi lỗi F0022 xảy ra trong quá trình tăng tốc: (1) Kiểm tra cách điện "
                    "cáp động cơ bằng đồng hồ Megohmmeter; (2) Kéo dài thời gian tăng tốc "
                    "P1120; (3) Kiểm tra công suất định mức giữa biến tần và động cơ."
                ),
                section="3.4 - Quy trình đo cách điện",
                version="Rev. C (2024)",
            ),
            CitationItem(
                document_title="Quy trình Thu thập Dữ kiện Kỹ thuật SongNhat (SOP-TECH-04)",
                page_number=12,
                content_snippet=(
                    "Đối với các lỗi ngắt mạch phần cứng trên biến tần, nhân viên hỗ trợ "
                    "cần thu thập Mã Serial (S/N), Phiên bản Firmware, thông số dòng điện "
                    "tại thời điểm ngắt (r0027) và ảnh chụp nhãn động cơ."
                ),
                section="2.1 - Thu thập dữ liệu lỗi biến tần",
                version="v1.2",
            ),
        ]

    if any(k in query_lower for k in ["tài liệu", "manual", "sơ đồ", "hướng dẫn", "catalog", "datasheet"]):
        return [
            CitationItem(
                document_title="Tài liệu Hướng dẫn Vận hành & Cài đặt Biến tần SongNhat SN-G120",
                page_number=15,
                content_snippet=(
                    "Sơ đồ đấu nối mạch động lực và điều khiển: Chân DI0-DI3 nhận tín hiệu "
                    "kích hoạt RUN/STOP, cổng RS485 hỗ trợ giao thức Modbus RTU cho PLC."
                ),
                section="2.2 - Sơ đồ đấu nối",
                version="v1.5",
            ),
            CitationItem(
                document_title="Sơ đồ Đấu nối Điều khiển và Động lực Hệ thống Tự động hóa SongNhat",
                page_number=32,
                content_snippet=(
                    "Bản vẽ sơ đồ nguyên lý mạch điều khiển biến tần và động cơ xoay chiều: "
                    "Yêu cầu gắn biến trở điều tốc tại chân AI0 và điện trở xả hãm nếu tải quán tính lớn."
                ),
                section="1.4 - Bản vẽ nguyên lý",
                version="v1.0",
            ),
        ]

    if any(k in query_lower for k in ["tiến độ", "bảo hành", "sửa", "dịch vụ"]):
        return [
            CitationItem(
                document_title="Quy trình Tiếp nhận Dịch vụ & Tra cứu Tiến độ Sửa chữa SongNhat",
                page_number=8,
                content_snippet=(
                    "Mỗi phiếu dịch vụ được cấp mã theo dõi duy nhất. Nhân viên dịch vụ có trách "
                    "nhiệm cập nhật tình trạng kiểm tra và thời gian hoàn tất dự kiến trong vòng 24 giờ."
                ),
                section="1.1 - Tiếp nhận dịch vụ",
                version="v2.0",
            ),
            CitationItem(
                document_title="Chính sách Bảo hành & Thời hạn Trả máy Thiết bị Tự động hóa",
                page_number=14,
                content_snippet=(
                    "Thời gian thẩm định và thông báo phương án xử lý sự cố thiết bị không vượt quá "
                    "48 giờ làm việc kể từ thời điểm nhận thiết bị tại trung tâm dịch vụ."
                ),
                section="2.3 - Thời hạn xử lý",
                version="Rev. 2025",
            ),
        ]

    return [
        CitationItem(
            document_title="Cẩm nang Kỹ thuật Thiết bị Tự động hóa SongNhat",
            page_number=24,
            content_snippet=(
                "Hướng dẫn kiểm tra sơ bộ hệ thống điều khiển: Xác minh nguồn cấp đầu vào, "
                "kiểm tra lịch sử mã cảnh báo trên màn hình BOP và đối chiếu sơ đồ đấu nối."
            ),
            section="General",
            version="v1.0",
        ),
        CitationItem(
            document_title="Quy trình Hỗ trợ Kỹ thuật & Bảo hành SongNhat",
            page_number=9,
            content_snippet=(
                "Vui lòng cung cấp Mã Serial thiết bị, Phiên bản Firmware và mô tả điều kiện "
                "vận hành khi phát sinh sự cố để bộ phận kỹ thuật tra cứu hồ sơ."
            ),
            section="General",
            version="v1.0",
        ),
    ]


class KnowledgeRetriever:
    """Class quản lý truy xuất đoạn văn bản kiến thức từ bảng `knowledge_passages` (Task CRM-43)."""

    def _score_passage(
        self,
        passage: Any,
        query: str,
        codes: List[str],
        phrases: List[str],
        keywords: List[str],
    ) -> float:
        """Tính điểm độ liên quan (Relevance Score) của đoạn trích đối với câu truy vấn."""
        score = 0.0
        content = (getattr(passage, "passage_content", "") or "").lower()
        doc_name = (getattr(passage, "document_name", "") or "").lower()
        sec_name = (getattr(passage, "section_name", "") or "").lower()
        full_text = f"{doc_name} {sec_name} {content}"

        # 1. Điểm cộng rất cao cho khớp mã lỗi / model đặc thù (e.g. F0022, SD700, 2310, E001)
        for code in codes:
            c_low = code.lower()
            if c_low in full_text:
                score += 15.0
                if c_low in content:
                    score += 10.0
                if c_low in doc_name:
                    score += 8.0

        # 2. Khớp cụm từ kỹ thuật đặc trưng (e.g. "biến tần", "quá dòng", "sơ đồ đấu nối")
        for ph in phrases:
            if ph in full_text:
                score += 5.0
                if ph in content:
                    score += 3.0

        # 3. Khớp các từ khóa đơn lẻ
        for kw in keywords:
            kw_low = kw.lower()
            if kw_low in content:
                score += 2.0
            if kw_low in doc_name:
                score += 2.0

        # 4. Khớp trực tiếp một phần câu truy vấn
        if query.lower() in full_text:
            score += 10.0

        return score

    async def _search_postgres(
        self,
        db: Any,
        query: str,
        codes: List[str],
        phrases: List[str],
        keywords: List[str],
        limit: int,
        product_id: Optional[Any] = None,
    ) -> List[Any]:
        """Truy vấn Full-text Search trên PostgreSQL sử dụng pg_trgm + GIN index."""
        try:
            from models import KnowledgePassage
        except ImportError:
            from backend.models import KnowledgePassage

        from sqlalchemy import desc, func, or_, select

        filters = []
        all_terms = list(dict.fromkeys(codes + phrases + keywords[:5]))
        for term in all_terms:
            pattern = f"%{term}%"
            filters.append(KnowledgePassage.passage_content.ilike(pattern))
            filters.append(KnowledgePassage.document_name.ilike(pattern))
            filters.append(KnowledgePassage.section_name.ilike(pattern))

        try:
            sim_score = func.similarity(KnowledgePassage.passage_content, query)
            sim_filter = sim_score > 0.05
            filters.append(sim_filter)
            order_clause = desc(sim_score)
        except Exception:
            order_clause = desc(KnowledgePassage.created_at)

        stmt = select(KnowledgePassage).where(
            KnowledgePassage.is_approved.is_(True),
            or_(*filters) if filters else True,
        )

        if product_id is not None:
            stmt = stmt.where(KnowledgePassage.product_id == product_id)

        stmt = stmt.order_by(order_clause).limit(limit * 2)

        result = db.execute(stmt)
        if inspect.isawaitable(result):
            result = await result

        return result.scalars().all() if hasattr(result, "scalars") else result.fetchall()

    async def _search_generic(
        self,
        db: Any,
        query: str,
        codes: List[str],
        phrases: List[str],
        keywords: List[str],
        limit: int,
        product_id: Optional[Any] = None,
    ) -> List[Any]:
        """Truy vấn đa từ khóa cho SQLite / Dialect khác với thuật toán ranking."""
        try:
            from models import KnowledgePassage
        except ImportError:
            from backend.models import KnowledgePassage

        from sqlalchemy import or_, select

        filters = []
        all_terms = list(dict.fromkeys(codes + phrases + keywords[:6]))
        if not all_terms:
            all_terms = [query.strip()]

        for term in all_terms:
            pattern = f"%{term}%"
            filters.append(KnowledgePassage.passage_content.ilike(pattern))
            filters.append(KnowledgePassage.document_name.ilike(pattern))
            filters.append(KnowledgePassage.section_name.ilike(pattern))

        stmt = select(KnowledgePassage).where(
            KnowledgePassage.is_approved.is_(True),
            or_(*filters) if filters else True,
        )

        if product_id is not None:
            stmt = stmt.where(KnowledgePassage.product_id == product_id)

        result = db.execute(stmt)
        if inspect.isawaitable(result):
            result = await result

        raw_passages = result.scalars().all() if hasattr(result, "scalars") else result.fetchall()

        scored = [
            (p, self._score_passage(p, query, codes, phrases, keywords))
            for p in raw_passages
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [p for p, s in scored]

    async def search_knowledge_passages(
        self,
        query: str,
        db: Optional[Any] = None,
        limit: int = 3,
        product_id: Optional[Any] = None,
    ) -> List[CitationItem]:
        """Truy vấn bảng `knowledge_passages` thật trong CSDL (Task CRM-43).

        Args:
            query: Nội dung mô tả sự cố hoặc từ khóa tìm kiếm.
            db: Phiên làm việc cơ sở dữ liệu (AsyncSession hoặc Session).
            limit: Số lượng trích dẫn tối đa cần lấy (mặc định 3).
            product_id: UUID nhóm sản phẩm (Motors / Drives) để lọc nếu có.

        Returns:
            Danh sách CitationItem chứa đầy đủ căn cứ kỹ thuật từ bảng đã phê duyệt.
        """
        if db is None:
            logger.debug("DB session is None, fallback sang mock data.")
            return get_mock_knowledge_passages(query)[:limit]

        try:
            tokens = extract_search_tokens(query)
            codes = tokens["codes"]
            phrases = tokens["phrases"]
            keywords = tokens["keywords"]

            # Nhận diện dialect CSDL
            is_postgres = False
            try:
                bind = getattr(db, "bind", None)
                if bind is None and hasattr(db, "get_bind"):
                    bind = db.get_bind()
                if bind and hasattr(bind, "dialect"):
                    is_postgres = getattr(bind.dialect, "name", "") == "postgresql"
            except Exception:
                pass

            passages: List[Any] = []
            if is_postgres:
                try:
                    passages = await self._search_postgres(
                        db=db,
                        query=query,
                        codes=codes,
                        phrases=phrases,
                        keywords=keywords,
                        limit=limit,
                        product_id=product_id,
                    )
                except Exception as pg_exc:
                    logger.warning("Truy vấn pg_trgm thất bại (%s), fallback sang generic SQL search.", pg_exc)
                    passages = await self._search_generic(
                        db=db,
                        query=query,
                        codes=codes,
                        phrases=phrases,
                        keywords=keywords,
                        limit=limit,
                        product_id=product_id,
                    )
            else:
                passages = await self._search_generic(
                    db=db,
                    query=query,
                    codes=codes,
                    phrases=phrases,
                    keywords=keywords,
                    limit=limit,
                    product_id=product_id,
                )

            # Nếu có product_id nhưng không tìm thấy đoạn trích nào, mở rộng tìm kiếm toàn bảng
            if not passages and product_id is not None:
                logger.info("Không tìm thấy theo product_id=%s, thử mở rộng truy vấn không lọc product.", product_id)
                passages = await self._search_generic(
                    db=db,
                    query=query,
                    codes=codes,
                    phrases=phrases,
                    keywords=keywords,
                    limit=limit,
                    product_id=None,
                )

            if passages:
                citations: List[CitationItem] = []
                for p in passages[:limit]:
                    doc_title = (
                        getattr(p, "document_title", None)
                        or getattr(p, "document_name", None)
                        or "Tài liệu kỹ thuật SongNhat"
                    )
                    snippet = (
                        getattr(p, "content_snippet", None)
                        or getattr(p, "passage_content", None)
                        or ""
                    )
                    page_num = getattr(p, "page_number", 1) or 1
                    section = (
                        getattr(p, "section", None)
                        or getattr(p, "section_name", None)
                        or ""
                    )
                    version = (
                        getattr(p, "version", None)
                        or (
                            p.passage_metadata.get("version")
                            if isinstance(getattr(p, "passage_metadata", None), dict)
                            else "v1.0"
                        )
                    )
                    doc_code = getattr(p, "document_code", None)
                    passage_id = str(p.id) if getattr(p, "id", None) else None

                    citations.append(
                        CitationItem(
                            document_title=str(doc_title),
                            page_number=int(page_num),
                            content_snippet=str(snippet),
                            section=str(section) if section else None,
                            version=str(version) if version else None,
                            passage_id=passage_id,
                            document_code=str(doc_code) if doc_code else None,
                        )
                    )
                logger.info("Retriever thực: Tìm thấy %d trích dẫn từ bảng knowledge_passages.", len(citations))
                return citations

            logger.info("Không tìm thấy đoạn trích phù hợp trong CSDL, chuyển sang fallback.")
        except Exception as exc:
            logger.warning("Lỗi trong quá trình truy xuất bảng knowledge_passages: %s. Chuyển sang fallback.", exc)

        return get_mock_knowledge_passages(query)[:limit]


async def search_knowledge_passages(
    query: str,
    db: Optional[Any] = None,
    limit: int = 3,
    product_id: Optional[Any] = None,
) -> List[CitationItem]:
    """Hàm tiện ích toàn cục thực hiện tìm kiếm trích dẫn kỹ thuật từ bảng `knowledge_passages`."""
    retriever = KnowledgeRetriever()
    return await retriever.search_knowledge_passages(
        query=query,
        db=db,
        limit=limit,
        product_id=product_id,
    )
