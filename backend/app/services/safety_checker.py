"""Mandatory Safety Checker service using deterministic Regex (Task CRM-24)."""

import re
from typing import Pattern

# Biểu thức chính quy quét các từ khóa nguy hiểm (có dấu, không dấu và tiếng Anh)
# Sử dụng ranh giới từ (\b) để tránh bắt nhầm từ ghép không liên quan (VD: "chạy", "nội", "nhớ")
HAZARD_KEYWORDS_PATTERN: Pattern[str] = re.compile(
    r"\b("
    r"cháy|lửa|nổ|bốc\s*khói|khói|điện\s*giật|giật\s*điện|chập\s*điện|chập\s*cháy|chập|"
    r"tia\s*lửa|chuyển\s*động\s*bất\s*thường|"
    r"chay\s*no|boc\s*khoi|dien\s*giat|giat\s*dien|chap\s*dien|chap\s*chay|"
    r"chay|no|khoi|giat|"
    r"smoke|fire|electric\s*shock|explosion|spark|unexpected\s*motion"
    r")\b",
    re.IGNORECASE | re.UNICODE,
)


def check_safety_hazard(text: str) -> bool:
    """Kiểm tra văn bản có chứa dấu hiệu nguy hiểm (cháy, nổ, khói, điện giật) hay không.

    Hàm này thực thi bằng mã xác định (deterministic regex) và bắt buộc chạy
    trước khi gọi bất kỳ mô hình AI nào.

    Args:
        text: Nội dung tiêu đề hoặc mô tả sự cố của ticket.

    Returns:
        True nếu phát hiện từ khóa nguy hiểm, ngược lại trả về False.
    """
    if not text or not text.strip():
        return False

    normalized_text = " ".join(text.strip().split())
    return bool(HAZARD_KEYWORDS_PATTERN.search(normalized_text))
