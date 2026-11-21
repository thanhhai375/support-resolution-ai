"""Mandatory Safety Checker service using deterministic Regex (Tasks CRM-24, CRM-28 & CRM-37)."""

import re
from typing import Pattern

# ---------------------------------------------------------------------------
# Danh sách từ khóa và cụm từ chỉ dấu hiệu nguy hiểm (Hazard Terms)
# Bao phủ toàn diện các kịch bản nguy hiểm theo RFP SongNhat (SUP-04) và Sprint 2 (CRM-23 / CRM-37):
# 1. Cháy / Lửa (fire, cháy, bốc cháy, bắt lửa, đám cháy, ngọn lửa, phát hỏa, hỏa hoạn)
# 2. Nổ (explosion, tiếng nổ, phát nổ, nổ tung, nổ vỡ)
# 3. Khói (smoke, khói, bốc khói, toả khói, có khói, xả khói)
# 4. Điện giật (electric shock, điện giật, giật điện, bị giật điện, phóng điện trúng người)
# 5. Rò rỉ điện / Hở điện (electric leak, rò điện, rò rỉ điện, hở điện, truyền điện ra vỏ)
# 6. Tia lửa điện / Hồ quang (spark, arc flash, tia lửa, phóng điện, hồ quang, đánh lửa)
# 7. Mùi khét (burning smell, mùi khét, khét lẹt, mùi cháy khét)
# 8. Chập mạch (short circuit, chập mạch, ngắn mạch, chập điện, đánh chập)
# 9. Quá nhiệt bất thường (overheating, quá nhiệt, quá nóng, nóng bất thường, bỏng tay)
# 10. Chuyển động bất thường / Tự chuyển động (unexpected motion, tự chuyển động, chuyển động bất thường, ngoài tầm kiểm soát, rung lắc dữ dội, kẹt cơ khí)
# 11. Thương tích / Tai nạn (injury, người vận hành bị thương, thương tích, tai nạn lao động)
# ---------------------------------------------------------------------------
HAZARD_TERMS_LIST = [
    # 1. Cháy / Lửa (Fire / Flame)
    r"cháy\s*nổ", r"bốc\s*cháy", r"đám\s*cháy", r"cháy\s*khét", r"bắt\s*lửa", r"chập\s*cháy",
    r"bị\s*cháy", r"ngọn\s*lửa", r"phát\s*hỏa", r"hỏa\s*hoạn", r"bén\s*lửa", r"bốc\s*hỏa",
    r"cháy\s*đen", r"cháy", r"ngọn\s*lửa", r"lửa",
    r"chay\s*no", r"boc\s*chay", r"dam\s*chay", r"chay\s*khet", r"bat\s*lua", r"chap\s*chay",
    r"ngon\s*lua", r"phat\s*hoa", r"hoa\s*hoan", r"ben\s*lua", r"boc\s*hoa", r"chay\s*den",
    r"dang\s*chay", r"lua\s*chay", r"(?<!thiet\s)bi\s*chay(?!\s*(?:cham|nhanh|tot|em|on|lai))",
    r"catch(?:es)?\s*fire", r"caught\s*fire", r"on\s*fire", r"flame[s]?", r"ablaze", r"fire",
    # 2. Nổ (Explosion / Blast)
    r"tiếng\s*nổ(?:\s*lớn)?", r"phát\s*nổ", r"nổ\s*tung", r"bị\s*nổ", r"nổ\s*vỡ", r"chập\s*nổ", r"nổ",
    r"tieng\s*no(?:\s*lon)?", r"phat\s*no", r"no\s*tung", r"bi\s*no", r"no\s*vo", r"chap\s*no",
    r"explosion[s]?", r"explode[s]?", r"exploded", r"exploding", r"blast[s]?",
    # 3. Khói (Smoke)
    r"bốc\s*khói", r"toả\s*khói", r"tỏa\s*khói", r"có\s*khói", r"xả\s*khói", r"phụt\s*khói",
    r"khói\s*đen", r"khói\s*trắng", r"khói\s*bốc", r"khói",
    r"boc\s*khoi", r"toa\s*khoi", r"co\s*khoi", r"xa\s*khoi", r"phut\s*khoi",
    r"khoi\s*den", r"khoi\s*trang", r"khoi\s*boc",
    r"heavy\s*smoke", r"smoke[s]?", r"smoking",
    # 4. Điện giật (Electric shock / Electrocution)
    r"bị\s*điện\s*giật", r"điện\s*giật", r"bị\s*giật\s*điện", r"giật\s*điện", r"bị\s*giật",
    r"giật\s*tê\s*người", r"phóng\s*điện\s*trúng\s*người", r"giật\s*người",
    r"bi\s*dien\s*giat", r"dien\s*giat", r"bi\s*giat\s*dien", r"giat\s*dien", r"bi\s*giat",
    r"electric\s*shock[s]?", r"electrical\s*shock[s]?", r"electrocute[ds]?", r"electrocution",
    # 5. Rò rỉ điện / Hở điện (Electric leakage / Live wire)
    r"rò\s*rỉ\s*điện", r"rò\s*điện", r"hở\s*điện", r"truyền\s*điện\s*ra\s*vỏ", r"nhiễm\s*điện", r"chạm\s*vỏ\s*có\s*điện",
    r"ro\s*ri\s*dien", r"ro\s*dien", r"ho\s*dien", r"truyen\s*dien\s*ra\s*vo", r"nhiem\s*dien",
    r"electric(?:al)?\s*leak(?:age)?", r"leakage\s*current", r"live\s*wire", r"exposed\s*wire",
    # 6. Tia lửa / Hồ quang (Sparks / Arc flash)
    r"tia\s*lửa\s*điện", r"tia\s*lửa", r"phóng\s*điện", r"hồ\s*quang(?:\s*điện)?",
    r"đánh\s*lửa", r"tóe\s*lửa", r"xoẹt\s*lửa", r"phát\s*tia\s*lửa", r"bắn\s*tia\s*lửa",
    r"tia\s*lua\s*dien", r"tia\s*lua", r"phong\s*dien", r"ho\s*quang(?:\s*dien)?",
    r"danh\s*lua", r"toe\s*lua", r"xoet\s*lua", r"phat\s*tia\s*lua", r"ban\s*tia\s*lua",
    r"spark[s]?", r"sparking", r"arc\s*flash", r"electric\s*arc", r"arcing",
    # 7. Mùi khét (Burning smell)
    r"mùi\s*cháy\s*khét", r"mùi\s*khét", r"khét\s*lẹt", r"khét\s*mùi", r"bốc\s*mùi\s*khét", r"có\s*mùi\s*khét", r"khét",
    r"mui\s*chay\s*khet", r"mui\s*khet", r"khet\s*let", r"khet\s*mui", r"boc\s*mui\s*khet", r"co\s*mui\s*khet", r"khet",
    r"burning\s*smell", r"burnt\s*smell", r"smell\s*of\s*burning",
    # 8. Chập mạch (Short circuit)
    r"chập\s*mạch", r"ngắn\s*mạch", r"chập\s*điện", r"chập\s*dây", r"đánh\s*chập", r"chập\s*cháy",
    r"bị\s*chập(?!\s*(?:chờn|chon))", r"chập(?!\s*(?:chờn|chon))",
    r"chap\s*mach", r"ngan\s*mach", r"chap\s*dien", r"chap\s*day", r"danh\s*chap",
    r"short\s*circuit", r"short-circuit", r"shorted\s*out",
    # 9. Quá nhiệt (Overheating)
    r"quá\s*nhiệt\s*bất\s*thường", r"quá\s*nhiệt", r"nóng\s*bất\s*thường", r"quá\s*nóng", r"bỏng\s*tay", r"phỏng\s*tay", r"nóng\s*rực",
    r"qua\s*nhiet\s*bat\s*thuong", r"qua\s*nhiet", r"nong\s*bat\s*thuong", r"qua\s*nong", r"bong\s*tay", r"phong\s*tay", r"nong\s*ruc",
    r"abnormal\s*overheating", r"overheat(?:ing)?", r"overheated", r"excessively\s*hot", r"extremely\s*hot",
    # 10. Chuyển động bất thường / Tự chuyển động (Unexpected motion / Uncontrolled movement)
    r"bất\s*ngờ\s*tự\s*chuyển\s*động", r"tự\s*chuyển\s*động\s*bất\s*thường", r"tự\s*chuyển\s*động\s*bất\s*ngờ",
    r"tự\s*chuyển\s*động", r"tự\s*động\s*chuyển\s*động", r"chuyển\s*động\s*bất\s*thường",
    r"chuyển\s*động\s*ngoài\s*tầm\s*kiểm\s*soát", r"vận\s*hành\s*ngoài\s*kiểm\s*soát",
    r"ngoài\s*tầm\s*kiểm\s*soát", r"mất\s*kiểm\s*soát", r"rung\s*lắc\s*dữ\s*dội", r"rung\s*giật\s*dữ\s*dội",
    r"tự\s*động\s*chạy", r"tự\s*chạy", r"tự\s*kích\s*hoạt", r"tự\s*quay",
    r"kẹt\s*cơ\s*khí(?:\s*gây\s*nguy\s*hiểm)?",
    r"bat\s*ngo\s*tu\s*chuyen\s*dong", r"tu\s*chuyen\s*dong\s*bat\s*thuong", r"tu\s*chuyen\s*dong\s*bat\s*ngo",
    r"tu\s*chuyen\s*dong", r"tu\s*dong\s*chuyen\s*dong", r"chuyen\s*dong\s*bat\s*thuong",
    r"chuyen\s*dong\s*ngoai\s*tam\s*kiem\s*soat", r"van\s*hanh\s*ngoai\s*kiem\s*soat",
    r"ngoai\s*tam\s*kiem\s*soat", r"mat\s*kiem\s*soat", r"rung\s*lac\s*du\s*doi", r"rung\s*giat\s*du\s*doi",
    r"tu\s*dong\s*chay", r"tu\s*chay", r"tu\s*kich\s*hoat", r"tu\s*quay", r"ket\s*co\s*khi",
    r"unexpected\s*motion", r"unexpected\s*movement", r"moves?\s*unexpectedly", r"moving\s*unexpectedly",
    r"uncontrolled\s*movement", r"uncontrolled\s*motion", r"erratic\s*motion",
    r"out\s*of\s*control", r"mechanical\s*jam", r"violent\s*vibration", r"severe\s*vibration",
    # 11. Thương tích / Tai nạn (Injury / Casualties)
    r"người\s*vận\s*hành\s*bị\s*thương", r"nguy\s*cơ\s*thương\s*tích", r"gây\s*thương\s*tích",
    r"thương\s*tích", r"bị\s*thương", r"chấn\s*thương", r"tai\s*nạn\s*lao\s*động", r"tai\s*nạn", r"tử\s*vong",
    r"dập\s*nát\s*tay", r"kẹt\s*tay", r"cuốn\s*người",
    r"nguoi\s*van\s*hanh\s*bi\s*thuong", r"nguy\s*co\s*thuong\s*tich", r"gay\s*thuong\s*tich",
    r"thuong\s*tich", r"bi\s*thuong", r"chan\s*thuong", r"tai\s*nan\s*lao\s*dong", r"tai\s*nan", r"tu\s*vong",
    r"operator\s*injured", r"injur(?:y|ies|ed)", r"casualt(?:y|ies)", r"accident"
]

HAZARD_COMBINED = "|".join(HAZARD_TERMS_LIST)
HAZARD_KEYWORDS_PATTERN: Pattern[str] = re.compile(
    rf"\b(?:{HAZARD_COMBINED})\b",
    re.IGNORECASE | re.UNICODE,
)

# ---------------------------------------------------------------------------
# Mẫu phát hiện các phủ định từ khóa nguy hiểm
# Ngăn chặn việc báo nhầm (False Positive = 0%) khi khách hàng sử dụng các câu phủ định:
# "Tôi không thấy khói hoặc cháy", "không có tia lửa", "không bị điện giật",
# "không ai bị thương", "không tự chuyển động", "neither smoke nor fire", v.v.
# ---------------------------------------------------------------------------
NEG_PREFIX = r"(?:không|chẳng|chưa|ko|k|no|without|neither|never)"
NEG_FILLER = r"(?:thấy|có|bị|phát\s*hiện|ghi\s*nhận|hề|ai|any|dấu\s*hiệu)?"
NEG_INTERVENING = r"(?:(?!\b(?:nhưng|song|tuy\s*nhiên|mà|but|yet|however)\b)[^\w\s]*\s*\w+){0,3}?"

NEGATION_HAZARD_PATTERN: Pattern[str] = re.compile(
    rf"\b{NEG_PREFIX}\s+{NEG_FILLER}\s*{NEG_INTERVENING}\s*(?:{HAZARD_COMBINED})(?:[\s,]*(?:hoặc|hay|or|nor)\s+(?:{HAZARD_COMBINED}))*\b",
    re.IGNORECASE | re.UNICODE,
)

# ---------------------------------------------------------------------------
# CRM-52 / VN-16: Nhận diện ngữ cảnh "hỏi tài liệu / phòng tránh / hướng dẫn
# an toàn" hoặc "không có sự cố thực tế" để tránh báo nhầm nguy hiểm khi
# người dùng chỉ tìm kiếm thông tin phòng ngừa, không phải sự cố thật.
# ---------------------------------------------------------------------------
DOCUMENTATION_SAFETY_CONTEXT_PHRASES = [
    # Tiếng Việt có dấu
    "hỏi tài liệu", "tìm tài liệu", "xin tài liệu", "cần tài liệu", "yêu cầu tài liệu",
    "tài liệu phòng tránh", "tài liệu phòng ngừa", "tài liệu an toàn", "tài liệu hướng dẫn",
    "hướng dẫn phòng tránh", "hướng dẫn phòng ngừa", "hướng dẫn an toàn",
    "phòng tránh", "phòng ngừa", "biện pháp phòng", "quy trình an toàn",
    "không có sự cố thực tế", "không có sự cố thật", "không có sự cố nào",
    "không xảy ra sự cố", "chưa xảy ra sự cố", "chưa có sự cố",
    # Tiếng Việt không dấu
    "hoi tai lieu", "tim tai lieu", "xin tai lieu", "can tai lieu", "yeu cau tai lieu",
    "tai lieu phong tranh", "tai lieu phong ngua", "tai lieu an toan", "tai lieu huong dan",
    "huong dan phong tranh", "huong dan phong ngua", "huong dan an toan",
    "phong tranh", "phong ngua", "bien phap phong", "quy trinh an toan",
    "khong co su co thuc te", "khong co su co that", "khong co su co nao",
    "khong xay ra su co", "chua xay ra su co", "chua co su co",
    # English
    "prevention guide", "safety guideline", "safety manual", "prevention document",
    "no actual incident", "no real incident",
]


def _is_documentation_safety_context(text: str) -> bool:
    """Kiểm tra câu có ngữ cảnh hỏi tài liệu/phòng tránh/không có sự cố thật không."""
    lowered = text.lower()
    return any(phrase in lowered for phrase in DOCUMENTATION_SAFETY_CONTEXT_PHRASES)


def check_safety_hazard(text: str) -> bool:
    """Kiểm tra văn bản có chứa dấu hiệu nguy hiểm (cháy, nổ, khói, điện giật, thương tích, v.v.) hay không.

    Hàm này thực thi bằng mã xác định (deterministic regex) và bắt buộc chạy
    trước khi gọi bất kỳ mô hình AI hoặc retriever nào.

    Args:
        text: Nội dung tiêu đề hoặc mô tả sự cố của ticket.

    Returns:
        True nếu phát hiện tình huống nguy hiểm, ngược lại trả về False.
    """
    if not text or not text.strip():
        return False

    normalized_text = " ".join(text.strip().split())

    # CRM-52 / VN-16: Nếu ngữ cảnh là hỏi tài liệu phòng tránh hoặc không có
    # sự cố thực tế -> an toàn, không kích hoạt ngắt khẩn cấp.
    if _is_documentation_safety_context(normalized_text):
        return False

    # Loại bỏ các biểu thức phủ định an toàn (VD: "không thấy khói hoặc cháy")
    cleaned_text = NEGATION_HAZARD_PATTERN.sub("", normalized_text)

    # Quét các từ khóa nguy hiểm còn lại trong văn bản
    return bool(HAZARD_KEYWORDS_PATTERN.search(cleaned_text))
