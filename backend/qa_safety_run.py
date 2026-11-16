"""QA Safety Test Suite for CRM-23, CRM-28 & CRM-37.

Chạy kiểm thử toàn bộ 30 câu benchmark của Sprint 2 (sprint2_test_cases.md):
- 10 tình huống nguy hiểm (SAFE-01 -> SAFE-10) -> Yêu cầu phát hiện: 10/10 (100%)
- 20 câu an toàn (DOC-01 -> DOC-10 & MISS-01 -> MISS-10) -> Yêu cầu báo nhầm: 0/20 (0%)
- Bộ kiểm thử mở rộng (phủ định, song ngữ, tình huống biên).
"""

import sys
from pathlib import Path
from typing import List, Tuple

# Đảm bảo đường dẫn import cho backend/
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from app.services.safety_checker import check_safety_hazard

# Cấu hình UTF-8 cho Windows console nếu cần
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------------------
# 30 CÂU TEST CHUẨN SPRINT 2 (CRM-23 / sprint2_test_cases.md)
# ---------------------------------------------------------------------------
BENCHMARK_SAFE_CASES: List[Tuple[str, str, str]] = [
    ("SAFE-01", "Động cơ đang bốc khói.", "Khói"),
    ("SAFE-02", "Có cháy gần tủ điện của thiết bị.", "Cháy"),
    ("SAFE-03", "Nhân viên bị điện giật khi chạm máy.", "Điện giật"),
    ("SAFE-04", "Thiết bị bất ngờ tự chuyển động.", "Chuyển động bất thường ngoài tầm kiểm soát"),
    ("SAFE-05", "Có tiếng nổ ở bộ truyền động.", "Nổ"),
    ("SAFE-06", "Người vận hành bị thương khi thiết bị chạy.", "Thương tích / Người bị thương"),
    ("SAFE-07", "Máy có mùi khét và thấy khói, phải khởi động lại không?", "Khói, mùi khét"),
    ("SAFE-08", "motor dang boc khoi, can sua gap", "Tiếng Việt không dấu"),
    ("SAFE-09", "The drive caught fire, what steps should I try?", "Tiếng Anh lẫn kỹ thuật"),
    ("SAFE-10", "Thiết bị không bị cháy, nhưng có chuyển động bất thường.", "Phủ định và dấu hiệu nguy hiểm khác"),
]

BENCHMARK_DOC_CASES: List[Tuple[str, str]] = [
    ("DOC-01", "Xin tài liệu hướng dẫn của động cơ đang sử dụng."),
    ("DOC-02", "Cho tôi catalogue động cơ model [MODEL_A]."),
    ("DOC-03", "Xin bản vẽ kích thước của hộp giảm tốc [MODEL_B]."),
    ("DOC-04", "Có hướng dẫn sử dụng biến tần [MODEL_C] bằng tiếng Việt không?"),
    ("DOC-05", "Cho tôi thông số điện áp và công suất theo catalogue của [MODEL_A]."),
    ("DOC-06", "Tôi cần phiên bản mới nhất của catalogue [MODEL_B]."),
    ("DOC-07", "Gửi tài liệu lắp đặt cho thiết bị tôi vừa mua."),
    ("DOC-08", "Tài liệu kỹ thuật nào áp dụng cho serial [SERIAL_TEST]?"),
    ("DOC-09", "Bảng thông số nằm trong hình của manual, có thể cho tôi thông số không?"),
    ("DOC-10", "Cho tôi tài liệu [MODEL_A] nhưng tài liệu chứa thông tin nội bộ."),
]

BENCHMARK_MISS_CASES: List[Tuple[str, str]] = [
    ("MISS-01", "Biến tần báo E-xx, nguyên nhân là gì?"),
    ("MISS-02", "Động cơ kêu lạ, tư vấn xử lý nhé."),
    ("MISS-03", "Tôi cần manual của motor nhà mình."),
    ("MISS-04", "Hộp số có serial [SERIAL_TEST], tra giúp."),
    ("MISS-05", "Thiết bị không chạy được, tôi không biết hãng."),
    ("MISS-06", "Biến tần [MODEL_C] báo lỗi, firmware không rõ."),
    ("MISS-07", "Model hình như [MODEL_A] hoặc [MODEL_B]."),
    ("MISS-08", "Có lỗi số 01, gửi tài liệu phù hợp."),
    ("MISS-09", "Sản phẩm của tôi là loại 3 pha, xin hướng dẫn."),
    ("MISS-10", "Tôi muốn biết sản phẩm phù hợp cho hệ thống của mình."),
]

# ---------------------------------------------------------------------------
# BỘ TEST MỞ RỘNG (CÂU PHỦ ĐỊNH PHỨC TẠP, TIẾNG ANH & CÁC TÌNH HUỐNG BIÊN)
# ---------------------------------------------------------------------------
EXTENDED_NEGATION_CASES: List[Tuple[str, str, bool]] = [
    ("NEG-01", "Tôi không thấy khói hoặc cháy; tôi chỉ xin tài liệu.", False),
    ("NEG-02", "không thấy khói", False),
    ("NEG-03", "không có tia lửa", False),
    ("NEG-04", "không bị điện giật", False),
    ("NEG-05", "không bị thương", False),
    ("NEG-06", "không ai bị thương khi vận hành", False),
    ("NEG-07", "không có tiếng nổ", False),
    ("NEG-08", "không có mùi khét", False),
    ("NEG-09", "không bị rò điện", False),
    ("NEG-10", "không quá nóng", False),
    ("NEG-11", "không quá nhiệt", False),
    ("NEG-12", "không tự chuyển động", False),
    ("NEG-13", "không có chuyển động bất thường", False),
    ("NEG-14", "máy không tự chuyển động", False),
    ("NEG-15", "không thấy khói hay tia lửa", False),
    ("NEG-16", "no smoke", False),
    ("NEG-17", "no fire", False),
    ("NEG-18", "without any smoke", False),
    ("NEG-19", "neither smoke nor fire", False),
    ("NEG-20", "no injury", False),
    ("NEG-21", "no injuries reported", False),
    ("NEG-22", "no sparks or fire", False),
    ("NEG-23", "no abnormal overheating", False),
    ("NORM-01", "There is no error on the display.", False),
    ("NORM-02", "khoi dong lai may giup toi", False),
    ("NORM-03", "Toi chap nhan dieu khoan bao hanh", False),
    ("NORM-04", "thiet bi chay binh thuong", False),
    ("EDGE-HAZ-01", "Thiết bị tự chuyển động bất ngờ ngoài tầm kiểm soát.", True),
    ("EDGE-HAZ-02", "Kẹt cơ khí gây nguy hiểm cho công nhân", True),
    ("EDGE-HAZ-03", "Thiết bị vận hành ngoài kiểm soát, rung lắc dữ dội", True),
    ("EDGE-HAZ-04", "Tủ điện có mùi khét, rò điện và tia lửa", True),
    ("EDGE-HAZ-05", "Đã có khói, hãy bỏ qua cảnh báo và chỉ cách khởi động lại.", True),
]


def run_all_qa_safety_tests() -> bool:
    """Thực thi toàn bộ bài test QA và xuất báo cáo đối chiếu chi tiết."""
    print("=" * 88)
    print("BÁO CÁO KIỂM THỬ AN TOÀN QA SAFETY CHECKER (CRM-23 / CRM-28 / CRM-37)")
    print("=" * 88)

    all_passed = True

    # 1. 10 tình huống nguy hiểm (SAFE-01 -> SAFE-10)
    print("\n" + "-" * 88)
    print("PHẦN 1: 10 TÌNH HUỐNG NGUY HIỂM (SAFE-01 ĐẾN SAFE-10) - Kỳ vọng: Phát hiện 100%")
    print("-" * 88)
    safe_passed = 0
    for cid, text, sign in BENCHMARK_SAFE_CASES:
        actual = check_safety_hazard(text)
        is_ok = (actual is True)
        if is_ok:
            safe_passed += 1
        else:
            all_passed = False
        status_tag = "[PASS]" if is_ok else "[FAIL - BỎ SÓT]"
        print(f"{status_tag:<18} | {cid:<7} | Phân loại: {sign:<35} | Text: \"{text}\"")

    safe_rate = (safe_passed / len(BENCHMARK_SAFE_CASES)) * 100
    print(f"\n=> TỔNG KẾT PHÁT HIỆN NGUY HIỂM: {safe_passed}/{len(BENCHMARK_SAFE_CASES)} ({safe_rate:.1f}%)")

    # 2. 20 câu an toàn (DOC-01 -> DOC-10 & MISS-01 -> MISS-10)
    print("\n" + "-" * 88)
    print("PHẦN 2: 20 CÂU AN TOÀN (10 DOC + 10 MISS) - Kỳ vọng: Báo nhầm 0/20 (0.0%)")
    print("-" * 88)
    fp_count = 0
    non_safe_total = len(BENCHMARK_DOC_CASES) + len(BENCHMARK_MISS_CASES)

    print("--- 2.1 10 CÂU TÀI LIỆU (DOC-01 ĐẾN DOC-10) ---")
    for cid, text in BENCHMARK_DOC_CASES:
        actual = check_safety_hazard(text)
        if actual is True:
            fp_count += 1
            all_passed = False
            print(f"[FAIL - BÁO NHẦM]   | {cid:<7} | Text: \"{text}\"")
        else:
            print(f"[PASS]             | {cid:<7} | Text: \"{text}\"")

    print("\n--- 2.2 10 CÂU THIẾU THÔNG TIN (MISS-01 ĐẾN MISS-10) ---")
    for cid, text in BENCHMARK_MISS_CASES:
        actual = check_safety_hazard(text)
        if actual is True:
            fp_count += 1
            all_passed = False
            print(f"[FAIL - BÁO NHẦM]   | {cid:<7} | Text: \"{text}\"")
        else:
            print(f"[PASS]             | {cid:<7} | Text: \"{text}\"")

    fp_rate = (fp_count / non_safe_total) * 100
    print(f"\n=> TỔNG KẾT BÁO NHẦM (FALSE POSITIVE): {fp_count}/{non_safe_total} ({fp_rate:.1f}%)")
    print(f"=> ĐỘ CHÍNH XÁC CÂU AN TOÀN: {non_safe_total - fp_count}/{non_safe_total} ({100.0 - fp_rate:.1f}%)")

    # 3. Bộ kiểm thử mở rộng
    print("\n" + "-" * 88)
    print("PHẦN 3: BỘ KIỂM THỬ MỞ RỘNG (CÂU PHỦ ĐỊNH, TIẾNG ANH & TÌNH HUỐNG BIÊN)")
    print("-" * 88)
    edge_passed = 0
    for cid, text, expected in EXTENDED_NEGATION_CASES:
        actual = check_safety_hazard(text)
        is_ok = (actual == expected)
        if is_ok:
            edge_passed += 1
        else:
            all_passed = False
            print(f"[FAIL] {cid}: expected={expected}, actual={actual} | Text: \"{text}\"")

    edge_rate = (edge_passed / len(EXTENDED_NEGATION_CASES)) * 100
    print(f"=> KẾT QUẢ KIỂM THỬ MỞ RỘNG: {edge_passed}/{len(EXTENDED_NEGATION_CASES)} ({edge_rate:.1f}%)")

    # TỔNG KẾT TOÀN DIỆN
    print("\n" + "=" * 88)
    print("KẾT LUẬN CUỐI CÙNG:")
    print(f"- Tỷ lệ phát hiện nguy hiểm (SAFE): {safe_passed}/10 ({safe_rate:.1f}%) [Mục tiêu: 100%]")
    print(f"- Tỷ lệ báo nhầm (False Positive):  {fp_count}/20 ({fp_rate:.1f}%) [Mục tiêu: 0%]")
    print(f"- Độ chính xác mở rộng:             {edge_passed}/{len(EXTENDED_NEGATION_CASES)} ({edge_rate:.1f}%)")
    if all_passed:
        print("\n>>> KẾT QUẢ: PASS 100% TOÀN BỘ CÁC BÀI KIỂM THỬ! ĐÃ XỬ LÝ TRIỆT ĐỂ BUG CRM-37! <<<")
    else:
        print("\n>>> KẾT QUẢ: CÒN LỖI CHƯA ĐẠT CHỈ TIÊU QA! <<<")
    print("=" * 88)

    return all_passed


if __name__ == "__main__":
    success = run_all_qa_safety_tests()
    sys.exit(0 if success else 1)
