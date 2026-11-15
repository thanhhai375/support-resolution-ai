"""Mandatory Safety Checker service using deterministic Regex (Tasks CRM-24 & CRM-28)."""

import re
from typing import Pattern

# Mẫu phát hiện các phủ định từ khóa nguy hiểm (tránh bắt nhầm false-positive như "Tôi không thấy khói hoặc cháy")
NEGATION_HAZARD_PATTERN: Pattern[str] = re.compile(
    r"\b(?:không|chẳng|chưa|ko|k)\s+(?:thấy|có|bị|phát hiện)?\s*(?:dấu hiệu\s+)?[\w\s]{0,25}?(?:khói|cháy|nổ|mùi khét|lửa|chập|điện giật|tia lửa|rò rỉ điện|rò điện|quá nhiệt)\b|"
    r"\b(?:no|without|neither)\s+(?:smoke|fire|spark|explosion|electric shock|burning smell)\b",
    re.IGNORECASE | re.UNICODE,
)

# Biểu thức chính quy phát hiện 100% các kịch bản nguy hiểm (SAFE-01 đến SAFE-06 và SUP-04):
# - Cháy / Lửa (fire, cháy, bốc cháy, bắt lửa, đám cháy)
# - Nổ (explosion, nổ, tiếng nổ, phát nổ)
# - Khói (smoke, khói, bốc khói, toả khói)
# - Điện giật (electric shock, điện giật, giật điện)
# - Rò rỉ điện (electric leak, rò điện, rò rỉ điện, hở điện)
# - Tia lửa điện / Hồ quang (spark, arc flash, tia lửa, tia lửa điện, phóng điện, hồ quang)
# - Mùi khét (burning smell, mùi khét, khét, mùi cháy khét)
# - Chập mạch (short circuit, chập mạch, ngắn mạch, chập điện, chập)
# - Quá nhiệt bất thường (overheating, quá nhiệt, quá nhiệt bất thường, quá nóng, nóng bất thường)
# - Chuyển động bất thường / Thương tích (unexpected motion, tự chuyển động, chuyển động bất thường, rung lắc dữ dội, thương tích, bị thương)
HAZARD_KEYWORDS_PATTERN: Pattern[str] = re.compile(
    r"\b("
    # Cháy / Lửa
    r"cháy|bốc\s*cháy|cháy\s*khét|đám\s*cháy|bắt\s*lửa|chập\s*cháy|bị\s*cháy|lửa|"
    r"chay\s*no|boc\s*chay|dam\s*chay|bat\s*lua|chap\s*chay|bi\s*chay|chay\s*khet|"
    # Nổ
    r"nổ|tiếng\s*nổ|phát\s*nổ|no|tieng\s*no|phat\s*no|"
    # Khói
    r"bốc\s*khói|toả\s*khói|tỏa\s*khói|có\s*khói|khói|boc\s*khoi|toa\s*khoi|co\s*khoi|khoi|"
    # Điện giật
    r"điện\s*giật|giật\s*điện|bị\s*giật|bị\s*điện\s*giật|dien\s*giat|giat\s*dien|bi\s*giat|bi\s*dien\s*giat|"
    # Rò rỉ điện
    r"rò\s*rỉ\s*điện|rò\s*điện|hở\s*điện|ro\s*ri\s*dien|ro\s*dien|ho\s*dien|"
    # Tia lửa điện / Hồ quang
    r"tia\s*lửa\s*điện|tia\s*lửa|phóng\s*điện|hồ\s*quang|tia\s*lua\s*dien|tia\s*lua|phong\s*dien|ho\s*quang|"
    # Mùi khét
    r"mùi\s*khét|mùi\s*cháy\s*khét|mui\s*khet|mui\s*chay\s*khet|khét|khet|"
    # Chập mạch
    r"chập\s*mạch|ngắn\s*mạch|chập\s*điện|chập|chap\s*mach|ngan\s*mach|chap\s*dien|chap|"
    # Quá nhiệt bất thường
    r"quá\s*nhiệt\s*bất\s*thường|quá\s*nhiệt|nóng\s*bất\s*thường|quá\s*nóng|"
    r"qua\s*nhiet\s*bat\s*thuong|qua\s*nhiet|nong\s*bat\s*thuong|qua\s*nong|"
    # Chuyển động bất thường / Thương tích
    r"chuyển\s*động\s*bất\s*thường|tự\s*chuyển\s*động|rung\s*lắc\s*dữ\s*dội|nguy\s*cơ\s*thương\s*tích|thương\s*tích|bị\s*thương|"
    r"chuyen\s*dong\s*bat\s*thuong|tu\s*chuyen\s*dong|rung\s*lac\s*du\s*doi|thuong\s*tich|bi\s*thuong|"
    # Tiếng Anh
    r"smoke|fire|electric\s*shock|explosion|spark|arc\s*flash|unexpected\s*motion|burning\s*smell|"
    r"short\s*circuit|overheat(?:ing)?|abnormal\s*overheating|electric\s*leak(?:age)?|injury|injured"
    r")\b",
    re.IGNORECASE | re.UNICODE,
)


def check_safety_hazard(text: str) -> bool:
    """Kiểm tra văn bản có chứa dấu hiệu nguy hiểm (cháy, nổ, khói, điện giật, v.v.) hay không.

    Hàm này thực thi bằng mã xác định (deterministic regex) và bắt buộc chạy
    trước khi gọi bất kỳ mô hình AI hoặc retriever nào.

    Args:
        text: Nội dung tiêu đề hoặc mô tả sự cố của ticket.

    Returns:
        True nếu phát hiện từ khóa nguy hiểm, ngược lại trả về False.
    """
    if not text or not text.strip():
        return False

    normalized_text = " ".join(text.strip().split())

    # Loại bỏ các mẫu phủ định (VD: "không thấy khói hoặc cháy")
    cleaned_text = NEGATION_HAZARD_PATTERN.sub("", normalized_text)
    cleaned_text = re.sub(
        r"\b(?:hoặc|hay|or)\s+(?:khói|cháy|nổ|lửa|mùi khét)\b",
        "",
        cleaned_text,
        flags=re.IGNORECASE,
    )

    return bool(HAZARD_KEYWORDS_PATTERN.search(cleaned_text))
