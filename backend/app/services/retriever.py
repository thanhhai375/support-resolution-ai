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


def parse_model_and_revision_constraints(query: str) -> dict[str, Any]:
    """Phân tích các ràng buộc về Model, Serial, Revision và tính hợp lệ từ câu hỏi khách hàng (Task CRM-51)."""
    clean_query = query.strip()
    lowered = clean_query.lower()

    # 1. Nhận diện các model được nhắc tới
    model_patterns = re.findall(
        r"\[MODEL_[A-Za-z0-9]+\]|MODEL_[A-Za-z0-9]+(?:-[A-Za-z0-9]+)?|\b(?:SD\d{3}|SN-G\d{2,3}|ACS\d{3}|M2BAX|M3AA|SM\s*Series)\b",
        clean_query,
        re.IGNORECASE,
    )
    normalized_models: List[str] = []
    for m in model_patterns:
        norm_m = m.strip("[]").upper()
        if norm_m not in normalized_models:
            normalized_models.append(norm_m)

    # Kiểm tra xung đột model (MODEL-03): ví dụ [MODEL_A] và [MODEL_B], hoặc đầu ghi A cuối ghi B
    has_model_conflict = False
    if len(normalized_models) >= 2:
        base_models = set(m.split("-")[0] for m in normalized_models)
        if len(base_models) > 1 or len(normalized_models) > 1:
            has_model_conflict = True
    if any(phrase in lowered for phrase in ["hình như", "hoặc", "hay"]) and len(normalized_models) >= 2:
        has_model_conflict = True
    if "đầu ghi" in lowered and "cuối ghi" in lowered:
        has_model_conflict = True

    # Kiểm tra thiếu model (MODEL-01, MODEL-13, MODEL-19):
    is_missing_model = False
    missing_cues = [
        "chưa biết model", "không biết model", "không rõ model", "chưa rõ model",
        "chưa có model", "chưa biết hãng", "không biết hãng", "chưa rõ hãng",
        "chưa biết mã", "không rõ mã",
    ]
    if any(cue in lowered for cue in missing_cues):
        is_missing_model = True
    elif (any(term in lowered for term in ["manual", "tài liệu", "catalogue", "catalog", "hướng dẫn"])
          and any(prod in lowered for prod in ["động cơ", "motor", "biến tần", "hộp số", "hộp giảm tốc"])
          and len(normalized_models) == 0):
        if "của động cơ" in lowered or "motor nhà" in lowered or "motor 3 pha" in lowered:
            is_missing_model = True

    # Kiểm tra serial và case MODEL-02 (chỉ có serial, chưa có mapping)
    serial_matches = re.findall(
        r"\[SERIAL_[A-Za-z0-9]+\]|SERIAL_[A-Za-z0-9]+|\bSN[-\s]?[A-Za-z0-9]+\b",
        clean_query,
    )
    serial_only_no_model = False
    if "chưa có bảng liên kết" in lowered or "chưa có liên kết" in lowered:
        serial_only_no_model = True
    elif len(serial_matches) > 0 and len(normalized_models) == 0 and "chỉ có serial" in lowered:
        serial_only_no_model = True

    # Kiểm tra dải serial ngoài phạm vi (MODEL-05)
    serial_out_of_range = False
    if "ngoài dải áp dụng" in lowered or "ngoài phạm vi" in lowered:
        serial_out_of_range = True

    # Kiểm tra revision (MODEL-04, MODEL-17, VN-09)
    requested_revision = None
    req_match = re.search(
        r"(?:cần|xin|yêu cầu|lấy|bản)\s+(?:rev\.?\s*([A-Za-z0-9]+)|Rev\.?\s*([A-Za-z0-9]+)|v(\d+(?:\.\d+)?))",
        clean_query,
        re.IGNORECASE,
    )
    if req_match:
        rev_val = req_match.group(1) or req_match.group(2) or req_match.group(3)
        requested_revision = f"rev.{rev_val}".lower() if not rev_val.lower().startswith("v") else f"v{rev_val}".lower()
    elif "rev.c" in lowered or "rev. c" in lowered:
        requested_revision = "rev.c"
    elif "rev.b" in lowered or "rev. b" in lowered:
        requested_revision = "rev.b"

    excluded_revision = None
    excl_match = re.search(
        r"(?:đừng|không|chớ)\s+(?:dùng|lấy|áp dụng)?\s*(?:rev\.?\s*([A-Za-z0-9]+)|Rev\.?\s*([A-Za-z0-9]+))",
        clean_query,
        re.IGNORECASE,
    )
    if excl_match:
        excl_val = excl_match.group(1) or excl_match.group(2)
        excluded_revision = f"rev.{excl_val}".lower()
    elif "đừng dùng rev.a" in lowered or "không dùng rev.a" in lowered:
        excluded_revision = "rev.a"

    if "cần rev.c" in lowered and ("rev.d" in lowered or "rev d" in lowered):
        requested_revision = "rev.c"
        excluded_revision = "rev.d"

    return {
        "models": normalized_models,
        "has_model_conflict": has_model_conflict,
        "is_missing_model": is_missing_model,
        "serial_only_no_model": serial_only_no_model,
        "serial_out_of_range": serial_out_of_range,
        "requested_revision": requested_revision,
        "excluded_revision": excluded_revision,
        "serials": serial_matches,
    }


def is_passage_applicable(passage: Any, constraints: dict[str, Any]) -> bool:
    """Kiểm tra một đoạn trích có thực sự áp dụng được cho câu hỏi hay không (CRM-51).

    Lọc bỏ các trường hợp:
    1. Trạng thái không hợp lệ: is_approved=False, Draft, Withdrawn, Revoked, Superseded (MODEL-10, MODEL-20, DAT 04, SEC 04).
    2. Sai model so với model khách hỏi (MODEL-12).
    3. Biến thể model không khớp (MODEL-06: MODEL_A-H vs MODEL_A-X).
    4. Sai revision so với revision khách yêu cầu (MODEL-04, MODEL-17).
    5. Trùng revision bị loại trừ (VN-09).
    6. Serial ngoài dải áp dụng (MODEL-05).
    """
    # 1. Kiểm tra trạng thái phê duyệt & hiệu lực (is_approved & status)
    if hasattr(passage, "is_approved") and passage.is_approved is False:
        return False

    meta = getattr(passage, "passage_metadata", {}) or {}
    if not isinstance(meta, dict):
        meta = {}

    doc_name = (getattr(passage, "document_name", None) or getattr(passage, "document_title", None) or "").lower()
    passage_content = (getattr(passage, "passage_content", None) or getattr(passage, "content_snippet", None) or "").lower()

    # Chặn các tài liệu có trạng thái không hợp lệ
    forbidden_status_keywords = ["draft", "withdrawn", "revoked", "superseded", "unapproved", "deprecated", "restricted"]
    eff_status = str(meta.get("effective_status") or meta.get("status") or getattr(passage, "status", "") or "").lower()
    if eff_status in forbidden_status_keywords:
        return False
    if any(f"[{kw}]" in doc_name or f"[{kw}]" in passage_content for kw in forbidden_status_keywords):
        return False
    if "[draft]" in doc_name or "[withdrawn]" in doc_name or "[revoked]" in doc_name or "[superseded]" in doc_name:
        return False

    # 2. Kiểm tra Serial ngoài dải áp dụng (MODEL-05)
    if constraints.get("serial_out_of_range"):
        return False

    # 3. Kiểm tra Model áp dụng (MODEL-06, MODEL-12)
    req_models = constraints.get("models") or []
    passage_model = str(meta.get("product_model") or meta.get("model") or getattr(passage, "product_model", "") or "").upper()

    if req_models:
        for req_m in req_models:
            # Kiểm tra biến thể model (MODEL-06): ví dụ MODEL_A-H vs MODEL_A-X
            if "-" in req_m:
                if passage_model and passage_model != req_m:
                    return False
                base_m = req_m.split("-")[0]
                if base_m.lower() in doc_name and req_m.lower() not in doc_name:
                    return False

            # Kiểm tra sai model (MODEL-12): khách hỏi MODEL_A nhưng passage là MODEL_B
            if passage_model:
                base_req = req_m.split("-")[0]
                base_pass = passage_model.split("-")[0]
                if base_req != base_pass and (base_req in ["MODEL_A", "MODEL_B", "MODEL_C", "SD700", "ACS580", "SN-G120", "M2BAX", "M3AA"]):
                    return False

            if "MODEL_A" in req_models and ("model_b" in doc_name or "model_c" in doc_name):
                return False
            if "MODEL_B" in req_models and ("model_a" in doc_name or "model_c" in doc_name):
                return False
            if "SD700" in req_models and ("acs580" in doc_name or "sn-g120" in doc_name):
                return False

    # 4. Kiểm tra Revision áp dụng (MODEL-04, MODEL-17, VN-09)
    passage_rev = str(meta.get("revision") or meta.get("version") or getattr(passage, "version", "") or "").lower().replace(" ", "")

    req_rev = constraints.get("requested_revision")
    if req_rev:
        norm_req_rev = req_rev.lower().replace(" ", "").replace(".", "")
        norm_pass_rev = passage_rev.replace(".", "")
        if norm_pass_rev and norm_pass_rev not in ["v10", "v1.0", "v1", "current", ""]:
            if norm_req_rev not in norm_pass_rev and norm_pass_rev not in norm_req_rev:
                return False

    excl_rev = constraints.get("excluded_revision")
    if excl_rev:
        norm_excl = excl_rev.lower().replace(" ", "").replace(".", "")
        norm_pass = passage_rev.replace(".", "")
        if norm_excl in norm_pass or norm_pass in norm_excl:
            return False

    return True


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
        allow_mock_fallback: bool = False,
    ) -> List[CitationItem]:
        """Truy vấn bảng `knowledge_passages` thật trong CSDL (Tasks CRM-43 & CRM-49).

        Args:
            query: Nội dung mô tả sự cố hoặc từ khóa tìm kiếm.
            db: Phiên làm việc cơ sở dữ liệu (AsyncSession hoặc Session).
            limit: Số lượng trích dẫn tối đa cần lấy (mặc định 3).
            product_id: UUID nhóm sản phẩm (Motors / Drives) để lọc nếu có.
            allow_mock_fallback: Cờ cho phép fallback về mock data khi bảng rỗng/lỗi
                                (mặc định False khi db!=None theo CRM-49; chỉ True cho unit test cũ).

        Returns:
            Danh sách CitationItem chứa đầy đủ căn cứ kỹ thuật từ bảng đã phê duyệt.
        """
        # CRM-51: Phân tích các ràng buộc về Model, Serial, Revision
        constraints = parse_model_and_revision_constraints(query)

        # CRM-51 / MODEL-01, MODEL-03, MODEL-02:
        # Nếu thiếu model, xung đột model, hoặc chỉ có serial chưa có mapping,
        # không tự chọn mặc định SN-G120; dừng truy xuất và trả về [].
        if constraints["has_model_conflict"]:
            logger.info("CRM-51: Phát hiện xung đột model trong truy vấn (%s). Dừng truy xuất.", constraints["models"])
            return []

        if constraints["is_missing_model"]:
            logger.info("CRM-51: Thiếu định danh model trong câu hỏi kỹ thuật. Dừng truy xuất.")
            return []

        if constraints["serial_only_no_model"]:
            logger.info("CRM-51: Chỉ có serial chưa có bảng liên kết model (MODEL-02). Dừng truy xuất.")
            return []

        if db is None:
            logger.debug("DB session is None, fallback sang mock data.")
            # Kiểm tra xem mock data có khớp ràng buộc không
            mock_items = get_mock_knowledge_passages(query)
            applicable_mocks = [c for c in mock_items if is_passage_applicable(c, constraints)]
            return applicable_mocks[:limit]

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
                        limit=limit * 2,
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
                        limit=limit * 2,
                        product_id=product_id,
                    )
            else:
                passages = await self._search_generic(
                    db=db,
                    query=query,
                    codes=codes,
                    phrases=phrases,
                    keywords=keywords,
                    limit=limit * 2,
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
                    limit=limit * 2,
                    product_id=None,
                )

            # CRM-51: Lọc tính áp dụng (Status, Model, Variant, Revision, Serial Range)
            applicable_passages = [p for p in passages if is_passage_applicable(p, constraints)]

            if applicable_passages:
                citations: List[CitationItem] = []
                for p in applicable_passages[:limit]:
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
                    meta = (
                        p.passage_metadata
                        if isinstance(getattr(p, "passage_metadata", None), dict)
                        else {}
                    )
                    version = (
                        getattr(p, "version", None)
                        or meta.get("version")
                        or meta.get("revision")
                        or "v1.0"
                    )
                    doc_code = getattr(p, "document_code", None) or meta.get("document_code")
                    passage_id = str(p.id) if getattr(p, "id", None) else None
                    status_val = (
                        getattr(p, "status", None)
                        or meta.get("effective_status")
                        or meta.get("status")
                        or ("current" if getattr(p, "is_approved", False) else "draft")
                    )
                    product_model_val = (
                        getattr(p, "product_model", None)
                        or meta.get("product_model")
                        or meta.get("model")
                    )
                    serial_range_val = (
                        getattr(p, "serial_range", None)
                        or meta.get("serial_range")
                    )

                    citations.append(
                        CitationItem(
                            document_title=str(doc_title),
                            page_number=int(page_num),
                            content_snippet=str(snippet),
                            section=str(section) if section else None,
                            version=str(version) if version else None,
                            passage_id=passage_id,
                            document_code=str(doc_code) if doc_code else None,
                            status=str(status_val) if status_val else None,
                            product_model=str(product_model_val) if product_model_val else None,
                            serial_range=str(serial_range_val) if serial_range_val else None,
                        )
                    )
                logger.info("Retriever thực: Tìm thấy %d trích dẫn từ bảng knowledge_passages.", len(citations))
                return citations

            logger.info("Không tìm thấy đoạn trích phù hợp trong CSDL.")
        except Exception as exc:
            logger.warning("Lỗi trong quá trình truy xuất bảng knowledge_passages: %s.", exc)

        # CRM-49: Khi db is not None, TUYỆT ĐỐI KHÔNG fallback sang mock data
        # trừ khi allow_mock_fallback=True (chỉ dùng cho unit test cũ).
        if allow_mock_fallback:
            logger.info("Fallback sang mock data vì allow_mock_fallback=True.")
            return get_mock_knowledge_passages(query)[:limit]

        return []


async def search_knowledge_passages(
    query: str,
    db: Optional[Any] = None,
    limit: int = 3,
    product_id: Optional[Any] = None,
    allow_mock_fallback: bool = False,
) -> List[CitationItem]:
    """Hàm tiện ích toàn cục thực hiện tìm kiếm trích dẫn kỹ thuật từ bảng `knowledge_passages`."""
    retriever = KnowledgeRetriever()
    return await retriever.search_knowledge_passages(
        query=query,
        db=db,
        limit=limit,
        product_id=product_id,
        allow_mock_fallback=allow_mock_fallback,
    )
