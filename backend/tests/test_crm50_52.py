"""Unit tests cho CRM-52 (VN-16, VN-01) và CRM-50 (VN-05, VN-06).

Kiểm tra:
- VN-16: Hỏi tài liệu phòng tránh điện giật -> KHÔNG kích hoạt hazard escalation.
- VN-01: Input không dấu "cho xin tai lieu dong co" -> phân loại DOCUMENT_REQUEST.
- VN-05: Bảo toàn mã lỗi gốc (E-01) trong draft, không tự biến đổi.
- VN-06: Bảo toàn đơn vị/thông số gốc (7,5 kW) trong draft, không tự biến đổi.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Đảm bảo import path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.copilot import CitationItem, IntentEnum
from app.services.copilot_engine import (
    _classify_intent_from_text,
    _compose_neutral_draft,
    run_copilot_pipeline,
)
from app.services.safety_checker import check_safety_hazard


# ===========================================================================
# CRM-52 / VN-16: Hỏi tài liệu phòng tránh điện giật -> False (không nguy hiểm)
# ===========================================================================
class TestVN16DocumentationSafetyContext:
    """VN-16: Từ khóa 'điện giật' trong ngữ cảnh hỏi tài liệu phòng tránh."""

    def test_asking_for_prevention_document_not_hazard(self):
        """Hỏi tài liệu phòng tránh điện giật -> False."""
        text = "Tôi hỏi tài liệu phòng tránh điện giật, không có sự cố thực tế"
        assert check_safety_hazard(text) is False

    def test_asking_for_safety_guideline_not_hazard(self):
        """Hỏi hướng dẫn an toàn điện giật -> False."""
        text = "Cho tôi hướng dẫn phòng tránh điện giật trong nhà máy"
        assert check_safety_hazard(text) is False

    def test_no_actual_incident_not_hazard(self):
        """Nêu rõ không có sự cố thực tế -> False."""
        text = "Tìm tài liệu về cháy nổ thiết bị, không có sự cố thực tế"
        assert check_safety_hazard(text) is False

    def test_real_electric_shock_still_detected(self):
        """Sự cố điện giật thật -> True (HAZ-14 vẫn hoạt động)."""
        text = "Nhân viên bị điện giật khi chạm máy"
        assert check_safety_hazard(text) is True

    def test_real_fire_still_detected(self):
        """Sự cố cháy thật -> True."""
        text = "Có cháy gần tủ điện của thiết bị"
        assert check_safety_hazard(text) is True

    def test_negation_still_works(self):
        """Phủ định vẫn hoạt động (VN-04)."""
        text = "Tôi không thấy khói hoặc cháy"
        assert check_safety_hazard(text) is False

    def test_real_smoke_still_detected(self):
        """Khói thật -> True."""
        text = "Động cơ đang bốc khói"
        assert check_safety_hazard(text) is True


# ===========================================================================
# CRM-52 / VN-01: Input không dấu -> phân loại đúng DOCUMENT_REQUEST
# ===========================================================================
class TestVN01AccentlessIntentClassification:
    """VN-01: Chuẩn hóa input tiếng Việt không dấu khi phân loại intent."""

    def test_unaccented_tai_lieu(self):
        """'cho xin tai lieu dong co, khong co dau' -> DOCUMENT_REQUEST."""
        text = "cho xin tai lieu dong co, khong co dau"
        assert _classify_intent_from_text(text) == IntentEnum.DOCUMENT_REQUEST

    def test_unaccented_huong_dan(self):
        """'gui huong dan su dung may' -> DOCUMENT_REQUEST."""
        text = "gui huong dan su dung may"
        assert _classify_intent_from_text(text) == IntentEnum.DOCUMENT_REQUEST

    def test_unaccented_so_tay(self):
        """'can so tay ky thuat' -> DOCUMENT_REQUEST."""
        text = "can so tay ky thuat"
        assert _classify_intent_from_text(text) == IntentEnum.DOCUMENT_REQUEST

    def test_accented_still_works(self):
        """Input có dấu vẫn hoạt động bình thường."""
        text = "Xin tài liệu hướng dẫn của động cơ đang sử dụng"
        assert _classify_intent_from_text(text) == IntentEnum.DOCUMENT_REQUEST

    def test_technical_still_classified(self):
        """Input kỹ thuật thuần túy vẫn TECHNICAL_ESCALATION."""
        text = "Biến tần báo lỗi F0022 khi tăng tốc"
        assert _classify_intent_from_text(text) == IntentEnum.TECHNICAL_ESCALATION

    def test_unaccented_progress(self):
        """'tien do bao hanh' -> SERVICE_PROGRESS."""
        text = "tien do bao hanh cua don hang"
        assert _classify_intent_from_text(text) == IntentEnum.SERVICE_PROGRESS


# ===========================================================================
# CRM-50 / VN-05: Bảo toàn mã lỗi gốc trong draft (E-01)
# ===========================================================================
class TestVN05PreserveOriginalErrorCode:
    """VN-05: Draft phải giữ nguyên mã lỗi E-01 từ câu hỏi gốc."""

    def test_error_code_preserved_in_draft(self):
        """Mã lỗi E-01 phải xuất hiện trong draft, không bị biến đổi."""
        ticket = "Biến tần báo lỗi E-01 khi khởi động"
        citations = [
            CitationItem(
                document_title="SINAMICS G120 Fault List",
                page_number=42,
                content_snippet="Mã lỗi E-01 chỉ sự cố mất tín hiệu encoder. Kiểm tra kết nối cáp encoder.",
            )
        ]
        draft = _compose_neutral_draft(
            ticket_description=ticket,
            intent=IntentEnum.TECHNICAL_ESCALATION,
            citations=citations,
            missing_facts=["Mã Serial (S/N) của thiết bị"],
        )
        assert "E-01" in draft, f"Mã lỗi gốc 'E-01' bị mất khỏi draft: {draft}"
        # Đảm bảo không bịa thêm IGBT / P1120
        assert "IGBT" not in draft, f"Draft chứa template IGBT cứng: {draft}"
        assert "P1120" not in draft, f"Draft chứa template P1120 cứng: {draft}"

    def test_citation_content_grounded(self):
        """Draft phải chứa nội dung từ citation thật."""
        ticket = "Biến tần báo lỗi E-01 khi khởi động"
        citations = [
            CitationItem(
                document_title="SINAMICS G120 Fault List",
                page_number=42,
                content_snippet="Mã lỗi E-01 chỉ sự cố mất tín hiệu encoder. Kiểm tra kết nối cáp encoder.",
            )
        ]
        draft = _compose_neutral_draft(
            ticket_description=ticket,
            intent=IntentEnum.TECHNICAL_ESCALATION,
            citations=citations,
            missing_facts=[],
        )
        # Draft phải chứa snippet thật từ citation
        assert "encoder" in draft.lower(), f"Draft thiếu nội dung trích dẫn thật: {draft}"


# ===========================================================================
# CRM-50 / VN-06: Bảo toàn đơn vị kỹ thuật gốc (7,5 kW)
# ===========================================================================
class TestVN06PreserveOriginalUnits:
    """VN-06: Draft phải giữ nguyên đơn vị kỹ thuật 7,5 kW từ câu hỏi gốc."""

    def test_unit_preserved_in_draft(self):
        """Thông số 7,5 kW phải xuất hiện trong draft, không bị biến đổi."""
        ticket = "Động cơ 7,5 kW rung lắc bất thường khi chạy full tải"
        citations = [
            CitationItem(
                document_title="ABB Motor M3AA Series Manual",
                page_number=18,
                content_snippet="Động cơ 7,5 kW cần kiểm tra cân bằng rotor và tình trạng ổ bi.",
            )
        ]
        draft = _compose_neutral_draft(
            ticket_description=ticket,
            intent=IntentEnum.TECHNICAL_ESCALATION,
            citations=citations,
            missing_facts=["Mã Serial (S/N) của thiết bị"],
        )
        assert "7,5 kW" in draft, f"Đơn vị gốc '7,5 kW' bị mất khỏi draft: {draft}"
        # Đảm bảo không bịa template IGBT cứng
        assert "IGBT" not in draft, f"Draft chứa template IGBT cứng: {draft}"

    def test_no_citations_asks_for_engineer(self):
        """Khi không có citation, draft đề xuất chuyển kỹ sư, không bịa căn cứ."""
        ticket = "Động cơ 7,5 kW rung lắc bất thường khi chạy full tải"
        draft = _compose_neutral_draft(
            ticket_description=ticket,
            intent=IntentEnum.TECHNICAL_ESCALATION,
            citations=[],
            missing_facts=["Mã Serial (S/N) của thiết bị"],
        )
        assert "7,5 kW" in draft, f"Đơn vị gốc '7,5 kW' bị mất khỏi draft: {draft}"
        assert "IGBT" not in draft, f"Draft chứa template IGBT cứng khi không có citation: {draft}"
        # Phải đề xuất chuyển kỹ sư
        assert "kỹ sư" in draft.lower() or "ky su" in draft.lower(), \
            f"Draft không đề xuất chuyển kỹ sư khi thiếu citation: {draft}"

    def test_draft_under_180_words(self):
        """Draft phải dưới 180 từ."""
        ticket = "Động cơ 7,5 kW rung lắc bất thường"
        draft = _compose_neutral_draft(
            ticket_description=ticket,
            intent=IntentEnum.TECHNICAL_ESCALATION,
            citations=[],
            missing_facts=["Mã Serial (S/N) của thiết bị"],
        )
        word_count = len(draft.split())
        assert word_count < 180, f"Draft vượt quá 180 từ: {word_count}"
