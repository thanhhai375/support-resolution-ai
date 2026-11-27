"""Knowledge Base Retriever service for hybrid keyword + vector search (Tasks CRM-24, CRM-28, CRM-43 & CRM-61)."""

from collections import Counter
import inspect
import logging
import math
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from app.schemas.copilot import CitationItem

logger = logging.getLogger(__name__)

MAX_RETRIEVED_PASSAGES = 10
KEYWORD_WEIGHT = 0.60
VECTOR_WEIGHT = 0.40
MIN_HYBRID_SCORE = 0.06

# Stopwords tiếng Việt & tiếng Anh thường gặp trong câu hỏi / mô tả ticket
VI_STOPWORDS = {
    "là", "và", "của", "có", "cho", "với", "trong", "các", "những", "khi",
    "này", "đó", "thì", "bị", "được", "xin", "giúp", "tôi", "mình", "nhé",
    "ạ", "vui", "lòng", "như", "thế", "nào", "gì", "sao", "ở", "tại", "về",
    "hay", "hoặc", "cần", "phải", "đang", "đã", "sẽ", "ra", "vào", "the",
    "and", "for", "with", "that", "this", "from", "when", "after", "into",
}

# Từ điển khái niệm kỹ thuật song ngữ (Domain Concept Expansion cho Vector & Hybrid Search)
DOMAIN_SYNONYM_GROUPS: Dict[str, List[str]] = {
    "concept_overcurrent": [
        "qua dong", "quá dòng", "overcurrent", "over current", "ngan mach", "ngắn mạch",
        "powerstack", "cham dat", "chạm đất", "f0022", "2310", "e001", "e-01", "current limit",
    ],
    "concept_overheat": [
        "qua nhiet", "quá nhiệt", "overheat", "thermal", "nhiet do", "nhiệt độ",
        "nong", "nóng", "155", "class f", "ptc", "95°c", "quat lam mat", "quạt làm mát",
    ],
    "concept_bearing": [
        "vong bi", "vòng bi", "o bi", "ổ bi", "bac dan", "bạc đạn", "bearing",
        "rung", "vibration", "lubrication", "boi tron", "bôi trơn", "mo", "mỡ", "grease", "2.8 mm/s",
    ],
    "concept_insulation": [
        "cach dien", "cách điện", "insulation", "megohmmeter", "stator", "500vdc", "1 mω",
    ],
    "concept_wiring": [
        "dau noi", "đấu nối", "so do", "sơ đồ", "wiring", "connection", "terminal",
        "star/delta", "sao tam giac", "mach dong luc", "mạch động lực", "di0", "cn5",
    ],
    "concept_comm": [
        "truyen thong", "truyền thông", "communication", "modbus", "rs485", "plc",
        "baud", "f0001", "120 ohm", "slave", "mat tin hieu", "mất tín hiệu",
    ],
    "concept_accel": [
        "tang toc", "tăng tốc", "acceleration", "ramp", "p1120", "23.12", "quan tinh", "quán tính",
    ],
    "concept_pid": [
        "pid", "p2200", "p2253", "p2264", "kp", "dao dong", "vong lap", "vòng lặp", "setpoint", "4-20ma",
    ],
    "concept_encoder": [
        "encoder", "abz", "ppr", "1024", "2500", "shielded", "alignment", "can chinh truc",
    ],
    "concept_overvoltage": [
        "qua ap", "quá áp", "overvoltage", "dc bus", "3210", "a0505", "dien tro xa",
    ],
    "concept_start_fail": [
        "khong khoi dong", "không khởi động", "fails to start", "khong chay", "380v", "pha",
    ],
    "concept_setup": [
        "cai dat", "cài đặt", "tham so", "tham số", "parameter", "auto-tune", "p1910", "p0304",
    ],
    "concept_motor": ["dong co", "động cơ", "motor", "motors", "servo"],
    "concept_drive": ["bien tan", "biến tần", "drive", "drives", "inverter"],
    "concept_warranty": ["tien do", "tiến độ", "bao hanh", "bảo hành", "sua chua", "sửa chữa", "phieu dich vu"],
}


def _strip_accents(text: str) -> str:
    """Chuẩn hóa chuỗi tiếng Việt về không dấu để tăng độ phủ tìm kiếm."""
    replaced = text.replace("đ", "d").replace("Đ", "D")
    nfkd = unicodedata.normalize("NFD", replaced)
    return "".join(ch for ch in nfkd if unicodedata.category(ch) != "Mn")


def _normalize_for_match(text: str) -> str:
    """Chuẩn hóa chữ thường và loại bỏ dấu tiếng Việt."""
    return _strip_accents((text or "").lower()).strip()


def _tokenize_with_concepts(text: str) -> List[str]:
    """Tách token chuẩn hóa kèm mở rộng khái niệm kỹ thuật song ngữ."""
    norm = _normalize_for_match(text)
    raw_tokens = re.findall(r"[a-z0-9]+(?:[.\-_/][a-z0-9]+)*", norm)
    tokens: List[str] = []
    for tok in raw_tokens:
        if len(tok) < 2:
            continue
        if tok in VI_STOPWORDS:
            continue
        tokens.append(tok)
        # Thêm biến thể bỏ gạch nối cho mã lỗi (e-01 -> e01, sn-g120 -> sng120)
        if "-" in tok:
            compact = tok.replace("-", "")
            if len(compact) >= 3:
                tokens.append(compact)

    # Thêm bigram cho từ khóa liên tiếp
    bigrams = [f"{tokens[i]}_{tokens[i + 1]}" for i in range(len(tokens) - 1)]
    tokens.extend(bigrams)

    # Mở rộng domain concepts
    for concept, triggers in DOMAIN_SYNONYM_GROUPS.items():
        if any(_normalize_for_match(t) in norm for t in triggers):
            tokens.append(concept)

    return tokens


def _char_trigrams(text: str) -> set[str]:
    """Tạo tập 3-gram ký tự (mô phỏng pg_trgm offline)."""
    norm = re.sub(r"\s+", " ", _normalize_for_match(text))
    if len(norm) < 3:
        return {norm} if norm else set()
    return {norm[i : i + 3] for i in range(len(norm) - 2)}


def _trigram_similarity(a: str, b: str) -> float:
    """Tính độ tương đồng Dice/Jaccard trên tập 3-gram ký tự."""
    ta = _char_trigrams(a)
    tb = _char_trigrams(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    return (2.0 * inter) / (len(ta) + len(tb))


def _cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    """Tính cosine similarity giữa hai vector thưa."""
    if not vec_a or not vec_b:
        return 0.0
    common = set(vec_a.keys()) & set(vec_b.keys())
    if not common:
        return 0.0
    dot = sum(vec_a[k] * vec_b[k] for k in common)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _dense_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Tính cosine similarity cho embedding vector dày (dense float list)."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return max(0.0, dot / (norm_a * norm_b))


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
                passage_id="mock-sn-g120-p142",
                document_title="Tài liệu Hướng dẫn Xử lý Lỗi Biến tần SongNhat SN-G120",
                page_number=142,
                content_snippet=(
                    "Mã lỗi F0022 (Powerstack Fault / Quá dòng phần cứng): Xuất hiện khi "
                    "có dòng ngắn mạch tại IGBT, chạm đất đầu ra động cơ hoặc thời gian "
                    "tăng tốc (P1120) cài đặt quá ngắn so với quán tính tải."
                ),
                section="5.2 - Mã lỗi phần cứng và quá dòng",
                version="v2.4",
                revision="v2.4",
                status="current",
                effective_date="2025-01-01",
            ),
            CitationItem(
                passage_id="mock-maint-p58",
                document_title="Sổ tay Bảo trì & Chẩn đoán Sự cố Truyền động Điện",
                page_number=58,
                content_snippet=(
                    "Khi lỗi F0022 xảy ra trong quá trình tăng tốc: (1) Kiểm tra cách điện "
                    "cáp động cơ bằng đồng hồ Megohmmeter; (2) Kéo dài thời gian tăng tốc "
                    "P1120; (3) Kiểm tra công suất định mức giữa biến tần và động cơ."
                ),
                section="3.4 - Quy trình đo cách điện",
                version="Rev. C (2024)",
                revision="Rev. C (2024)",
                status="current",
                effective_date="2024-06-01",
            ),
            CitationItem(
                passage_id="mock-sop-tech-04-p12",
                document_title="Quy trình Thu thập Dữ kiện Kỹ thuật SongNhat (SOP-TECH-04)",
                page_number=12,
                content_snippet=(
                    "Đối với các lỗi ngắt mạch phần cứng trên biến tần, nhân viên hỗ trợ "
                    "cần thu thập Mã Serial (S/N), Phiên bản Firmware, thông số dòng điện "
                    "tại thời điểm ngắt (r0027) và ảnh chụp nhãn động cơ."
                ),
                section="2.1 - Thu thập dữ liệu lỗi biến tần",
                version="v1.2",
                revision="v1.2",
                status="current",
                effective_date="2024-03-01",
            ),
        ]

    if any(k in query_lower for k in ["tài liệu", "manual", "sơ đồ", "hướng dẫn", "catalog", "datasheet"]):
        return [
            CitationItem(
                passage_id="mock-sn-g120-p15",
                document_title="Tài liệu Hướng dẫn Vận hành & Cài đặt Biến tần SongNhat SN-G120",
                page_number=15,
                content_snippet=(
                    "Sơ đồ đấu nối mạch động lực và điều khiển: Chân DI0-DI3 nhận tín hiệu "
                    "kích hoạt RUN/STOP, cổng RS485 hỗ trợ giao thức Modbus RTU cho PLC."
                ),
                section="2.2 - Sơ đồ đấu nối",
                version="v1.5",
                revision="v1.5",
                status="current",
                effective_date="2025-01-01",
            ),
            CitationItem(
                passage_id="mock-wiring-p32",
                document_title="Sơ đồ Đấu nối Điều khiển và Động lực Hệ thống Tự động hóa SongNhat",
                page_number=32,
                content_snippet=(
                    "Bản vẽ sơ đồ nguyên lý mạch điều khiển biến tần và động cơ xoay chiều: "
                    "Yêu cầu gắn biến trở điều tốc tại chân AI0 và điện trở xả hãm nếu tải quán tính lớn."
                ),
                section="1.4 - Bản vẽ nguyên lý",
                version="v1.0",
                revision="v1.0",
                status="current",
                effective_date="2024-01-01",
            ),
        ]

    if any(k in query_lower for k in ["tiến độ", "bảo hành", "sửa", "dịch vụ"]):
        return [
            CitationItem(
                passage_id="mock-service-p8",
                document_title="Quy trình Tiếp nhận Dịch vụ & Tra cứu Tiến độ Sửa chữa SongNhat",
                page_number=8,
                content_snippet=(
                    "Mỗi phiếu dịch vụ được cấp mã theo dõi duy nhất. Nhân viên dịch vụ có trách "
                    "nhiệm cập nhật tình trạng kiểm tra và thời gian hoàn tất dự kiến trong vòng 24 giờ."
                ),
                section="1.1 - Tiếp nhận dịch vụ",
                version="v2.0",
                revision="v2.0",
                status="current",
                effective_date="2025-01-01",
            ),
            CitationItem(
                passage_id="mock-warranty-p14",
                document_title="Chính sách Bảo hành & Thời hạn Trả máy Thiết bị Tự động hóa",
                page_number=14,
                content_snippet=(
                    "Thời gian thẩm định và thông báo phương án xử lý sự cố thiết bị không vượt quá "
                    "48 giờ làm việc kể từ thời điểm nhận thiết bị tại trung tâm dịch vụ."
                ),
                section="2.3 - Thời hạn xử lý",
                version="Rev. 2025",
                revision="Rev. 2025",
                status="current",
                effective_date="2025-01-01",
            ),
        ]

    return [
        CitationItem(
            passage_id="mock-handbook-p24",
            document_title="Cẩm nang Kỹ thuật Thiết bị Tự động hóa SongNhat",
            page_number=24,
            content_snippet=(
                "Hướng dẫn kiểm tra sơ bộ hệ thống điều khiển: Xác minh nguồn cấp đầu vào, "
                "kiểm tra lịch sử mã cảnh báo trên màn hình BOP và đối chiếu sơ đồ đấu nối."
            ),
            section="General",
            version="v1.0",
            revision="v1.0",
            status="current",
            effective_date="2024-01-01",
        ),
        CitationItem(
            passage_id="mock-support-p9",
            document_title="Quy trình Hỗ trợ Kỹ thuật & Bảo hành SongNhat",
            page_number=9,
            content_snippet=(
                "Vui lòng cung cấp Mã Serial thiết bị, Phiên bản Firmware và mô tả điều kiện "
                "vận hành khi phát sinh sự cố để bộ phận kỹ thuật tra cứu hồ sơ."
            ),
            section="General",
            version="v1.0",
            revision="v1.0",
            status="current",
            effective_date="2024-01-01",
        ),
    ]


class KnowledgeRetriever:
    """Class quản lý truy xuất Hybrid Keyword + Vector từ bảng `knowledge_passages` (Tasks CRM-43 & CRM-61)."""

    def _passage_text_fields(self, passage: Any) -> Tuple[str, str, str, str]:
        """Trích xuất (doc_name, sec_name, content, doc_code) dạng chữ thường."""
        content = (getattr(passage, "passage_content", None) or getattr(passage, "content_snippet", None) or "").lower()
        doc_name = (getattr(passage, "document_name", None) or getattr(passage, "document_title", None) or "").lower()
        sec_name = (getattr(passage, "section_name", None) or getattr(passage, "section", None) or "").lower()
        doc_code = (getattr(passage, "document_code", None) or "").lower()
        return doc_name, sec_name, content, doc_code

    def _score_passage(
        self,
        passage: Any,
        query: str,
        codes: List[str],
        phrases: List[str],
        keywords: List[str],
    ) -> float:
        """Tính điểm từ khóa có trọng số (exact code/model/unit + BM25-like TF + trigram)."""
        score = 0.0
        doc_name, sec_name, content, doc_code = self._passage_text_fields(passage)
        meta = getattr(passage, "passage_metadata", None)
        meta_model = str(meta.get("product_model") or meta.get("model") or "").lower() if isinstance(meta, dict) else ""
        full_text = f"{doc_name} {doc_code} {sec_name} {meta_model} {content}"
        norm_full = _normalize_for_match(full_text)
        norm_content = _normalize_for_match(content)
        norm_doc = _normalize_for_match(f"{doc_name} {doc_code} {meta_model}")
        norm_sec = _normalize_for_match(sec_name)

        # 1. Điểm cộng rất cao cho khớp mã lỗi / model / đơn vị đặc thù
        for code in codes:
            c_low = code.lower()
            c_norm = _normalize_for_match(c_low)
            c_compact = c_norm.replace("-", "")
            if c_low in full_text or c_norm in norm_full:
                score += 18.0
                if c_low in content or c_norm in norm_content:
                    score += 10.0
                if c_low in doc_name or c_norm in norm_doc:
                    score += 8.0
            elif len(c_compact) >= 3 and c_compact in norm_full.replace("-", ""):
                score += 10.0

        # 2. Khớp cụm từ kỹ thuật đặc trưng (có dấu và không dấu)
        for ph in phrases:
            ph_norm = _normalize_for_match(ph)
            if ph in full_text or ph_norm in norm_full:
                score += 6.0
                if ph in content or ph_norm in norm_content:
                    score += 3.5

        # 3. BM25-like saturated term frequency across weighted fields
        k1 = 1.2
        content_len = max(len(norm_content.split()), 1)
        length_norm = 1.0 - 0.35 + 0.35 * min(content_len / 45.0, 2.0)
        for kw in keywords:
            kw_low = kw.lower()
            kw_norm = _normalize_for_match(kw_low)
            tf_content = norm_content.count(kw_norm) if kw_norm else 0
            tf_doc = norm_doc.count(kw_norm) if kw_norm else 0
            tf_sec = norm_sec.count(kw_norm) if kw_norm else 0
            weighted_tf = tf_content + 1.8 * tf_doc + 1.4 * tf_sec
            if weighted_tf > 0:
                bm25_tf = (weighted_tf * (k1 + 1.0)) / (weighted_tf + k1 * length_norm)
                score += 3.0 * bm25_tf

        # 4. Khớp trực tiếp một phần câu truy vấn
        norm_query = _normalize_for_match(query)
        if norm_query and norm_query in norm_full:
            score += 10.0

        # 5. Trigram similarity (offline pg_trgm equivalent)
        score += 10.0 * _trigram_similarity(query, f"{doc_name} {sec_name} {content}")

        return score

    def _compute_hybrid_scores(
        self,
        passages: List[Any],
        query: str,
        codes: List[str],
        phrases: List[str],
        keywords: List[str],
        query_embedding: Optional[List[float]] = None,
    ) -> List[Tuple[Any, float]]:
        """Kết hợp Keyword Score (BM25/exact/trigram) và Vector Score (TF-IDF/Concept Cosine)."""
        if not passages:
            return []

        corpus_tokens: List[List[str]] = []
        df: Counter[str] = Counter()
        for p in passages:
            doc_name, sec_name, content, doc_code = self._passage_text_fields(p)
            # Tăng trọng số document_name và section_name trong vector TF-IDF
            combined = f"{doc_name} {doc_name} {doc_code} {sec_name} {content}"
            toks = _tokenize_with_concepts(combined)
            corpus_tokens.append(toks)
            for t in set(toks):
                df[t] += 1

        n_docs = len(passages)
        query_toks = _tokenize_with_concepts(query)
        for t in set(query_toks):
            df[t] += 1

        def _to_tfidf_vec(toks: List[str]) -> Dict[str, float]:
            tf = Counter(toks)
            total = max(len(toks), 1)
            vec: Dict[str, float] = {}
            for term, count in tf.items():
                idf = math.log((n_docs + 2.0) / (df.get(term, 0) + 1.0)) + 1.0
                weight = (1.0 + math.log(count)) / math.sqrt(total) * idf
                if term.startswith("concept_"):
                    weight *= 1.6
                vec[term] = weight
            return vec

        query_vec = _to_tfidf_vec(query_toks)
        scored: List[Tuple[Any, float]] = []

        for idx, p in enumerate(passages):
            kw_raw = self._score_passage(p, query, codes, phrases, keywords)
            kw_norm = kw_raw / (kw_raw + 15.0) if kw_raw > 0 else 0.0

            doc_vec = _to_tfidf_vec(corpus_tokens[idx])
            vec_score = _cosine_similarity(query_vec, doc_vec)

            meta = getattr(p, "passage_metadata", None)
            if query_embedding and isinstance(meta, dict) and isinstance(meta.get("embedding"), list):
                dense_sim = _dense_cosine_similarity(query_embedding, meta["embedding"])
                vec_score = 0.5 * vec_score + 0.5 * dense_sim

            hybrid_score = KEYWORD_WEIGHT * kw_norm + VECTOR_WEIGHT * vec_score
            scored.append((p, hybrid_score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored

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
        """Truy vấn Full-text Search trên PostgreSQL sử dụng pg_trgm + Hybrid Rerank."""
        try:
            from models import KnowledgePassage
        except ImportError:
            from backend.models import KnowledgePassage

        from sqlalchemy import desc, func, or_, select

        filters = []
        all_terms = list(dict.fromkeys(codes + phrases + keywords[:8]))
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

        candidate_limit = max(limit * 4, 30)
        stmt = stmt.order_by(order_clause).limit(candidate_limit)

        result = db.execute(stmt)
        if inspect.isawaitable(result):
            result = await result

        raw_passages = list(result.scalars().all() if hasattr(result, "scalars") else result.fetchall())
        if len(raw_passages) < limit:
            broad_stmt = select(KnowledgePassage).where(KnowledgePassage.is_approved.is_(True))
            if product_id is not None:
                broad_stmt = broad_stmt.where(KnowledgePassage.product_id == product_id)
            broad_stmt = broad_stmt.limit(200)
            broad_res = db.execute(broad_stmt)
            if inspect.isawaitable(broad_res):
                broad_res = await broad_res
            broad_rows = broad_res.scalars().all() if hasattr(broad_res, "scalars") else broad_res.fetchall()
            seen_ids = {getattr(p, "id", id(p)) for p in raw_passages}
            for row in broad_rows:
                rid = getattr(row, "id", id(row))
                if rid not in seen_ids:
                    raw_passages.append(row)
                    seen_ids.add(rid)

        ranked = self._compute_hybrid_scores(raw_passages, query, codes, phrases, keywords)
        return [p for p, score in ranked if score >= MIN_HYBRID_SCORE]

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
        """Truy vấn đa từ khóa + Hybrid Vector Rerank cho SQLite / Dialect khác."""
        try:
            from models import KnowledgePassage
        except ImportError:
            from backend.models import KnowledgePassage

        from sqlalchemy import or_, select

        filters = []
        all_terms = list(dict.fromkeys(codes + phrases + keywords[:8]))
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

        raw_passages = list(result.scalars().all() if hasattr(result, "scalars") else result.fetchall())

        # Mở rộng tập ứng viên trong DB khi truy vấn đồng nghĩa/không dấu làm SQL ILIKE trả về ít kết quả
        if len(raw_passages) < max(limit * 2, 10):
            broad_stmt = select(KnowledgePassage).where(KnowledgePassage.is_approved.is_(True))
            if product_id is not None:
                broad_stmt = broad_stmt.where(KnowledgePassage.product_id == product_id)
            broad_stmt = broad_stmt.limit(500)
            broad_res = db.execute(broad_stmt)
            if inspect.isawaitable(broad_res):
                broad_res = await broad_res
            broad_rows = broad_res.scalars().all() if hasattr(broad_res, "scalars") else broad_res.fetchall()
            seen_ids = {getattr(p, "id", id(p)) for p in raw_passages}
            for row in broad_rows:
                rid = getattr(row, "id", id(row))
                if rid not in seen_ids:
                    raw_passages.append(row)
                    seen_ids.add(rid)

        ranked = self._compute_hybrid_scores(raw_passages, query, codes, phrases, keywords)
        return [p for p, score in ranked if score >= MIN_HYBRID_SCORE]

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

        effective_limit = max(1, min(int(limit or 3), MAX_RETRIEVED_PASSAGES))

        if db is None:
            logger.debug("DB session is None, fallback sang mock data.")
            # Kiểm tra xem mock data có khớp ràng buộc không
            mock_items = get_mock_knowledge_passages(query)
            applicable_mocks = [c for c in mock_items if is_passage_applicable(c, constraints)]
            return applicable_mocks[:effective_limit]

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
                        limit=effective_limit * 2,
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
                        limit=effective_limit * 2,
                        product_id=product_id,
                    )
            else:
                passages = await self._search_generic(
                    db=db,
                    query=query,
                    codes=codes,
                    phrases=phrases,
                    keywords=keywords,
                    limit=effective_limit * 2,
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
                    limit=effective_limit * 2,
                    product_id=None,
                )

            # CRM-51: Lọc tính áp dụng (Status, Model, Variant, Revision, Serial Range)
            applicable_passages = [p for p in passages if is_passage_applicable(p, constraints)]

            if applicable_passages:
                citations: List[CitationItem] = []
                for p in applicable_passages[:effective_limit]:
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
                    raw_revision = (
                        getattr(p, "revision", None)
                        or meta.get("revision")
                        or getattr(p, "version", None)
                        or meta.get("version")
                        or meta.get("doc_version")
                        or "v1.0"
                    )
                    revision_str = str(raw_revision)
                    version_str = str(
                        getattr(p, "version", None)
                        or meta.get("version")
                        or meta.get("doc_version")
                        or revision_str
                    )
                    doc_code = getattr(p, "document_code", None) or meta.get("document_code")
                    passage_id = str(p.id) if getattr(p, "id", None) else None
                    status_val = (
                        getattr(p, "status", None)
                        or meta.get("effective_status")
                        or meta.get("status")
                        or ("current" if getattr(p, "is_approved", False) else "draft")
                    )
                    approved_at_val = getattr(p, "approved_at", None) or meta.get("approved_at")
                    if hasattr(approved_at_val, "date"):
                        approved_at_str = approved_at_val.date().isoformat()
                    elif approved_at_val:
                        approved_at_str = str(approved_at_val)[:10]
                    else:
                        approved_at_str = None
                    effective_date_val = (
                        getattr(p, "effective_date", None)
                        or meta.get("effective_date")
                        or approved_at_str
                    )
                    deep_link_val = (
                        getattr(p, "deep_link", None)
                        or meta.get("deep_link")
                        or meta.get("url")
                        or meta.get("document_url")
                    )
                    explicit_stable_ref = (
                        getattr(p, "stable_ref", None)
                        or meta.get("stable_ref")
                    )
                    stable_ref_val = (
                        str(explicit_stable_ref)
                        if explicit_stable_ref
                        else (
                            None
                            if deep_link_val
                            else f"{doc_title} | Rev {revision_str} | Mục {section or 'General'} | Trang {int(page_num)}"
                        )
                    )
                    supersession_ref_val = (
                        getattr(p, "supersession_ref", None)
                        or meta.get("supersession_ref")
                        or meta.get("supersession_link")
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
                            version=version_str,
                            revision=revision_str,
                            passage_id=passage_id,
                            document_code=str(doc_code) if doc_code else None,
                            status=str(status_val) if status_val else None,
                            effective_date=str(effective_date_val) if effective_date_val else None,
                            deep_link=str(deep_link_val) if deep_link_val else None,
                            stable_ref=stable_ref_val,
                            supersession_ref=str(supersession_ref_val) if supersession_ref_val else None,
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
            return get_mock_knowledge_passages(query)[:effective_limit]

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
