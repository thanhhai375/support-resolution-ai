"""Copilot Engine Service for Incident Analysis & Evidence Extraction (Task CRM-24)."""

import json
import logging
import os
from typing import Any, List, Optional

from app.schemas.copilot import (
    CaseSummary,
    CitationItem,
    CopilotPackageResponse,
    IntentEnum,
)
from app.services.retriever import search_knowledge_passages
from app.services.safety_checker import check_safety_hazard

logger = logging.getLogger(__name__)


class CopilotEngineService:
    """Service điều phối quy trình 3 bước phân tích sự cố và trích xuất bằng chứng."""

    def __init__(self, db: Optional[Any] = None, api_key: Optional[str] = None) -> None:
        """Khởi tạo CopilotEngineService.

        Args:
            db: Kết nối cơ sở dữ liệu (tùy chọn).
            api_key: API Key cho dịch vụ LLM (Gemini/OpenAI) nếu kích hoạt gọi AI thật.
        """
        self.db = db
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")

    async def analyze_ticket(self, ticket_description: str) -> CopilotPackageResponse:
        """Thực thi quy trình 3 bước phân tích ticket hỗ trợ kỹ thuật.

        Quy trình:
            - Bước 1: Kiểm tra an toàn bằng `check_safety_hazard(ticket_description)`.
              Nếu phát hiện nguy hiểm -> Ngắt luồng ngay lập tức, trả về gói khẩn cấp
              (`is_hazard_escalated = True`, `intent = TECHNICAL_ESCALATION`),
              tuyệt đối KHÔNG gọi mô hình AI.
            - Bước 2: Truy xuất tài liệu kỹ thuật qua `search_knowledge_passages()`.
            - Bước 3: Phân tích Intent, tóm tắt sự cố, xác định dữ kiện còn thiếu và
              soạn bản nháp phản hồi tiếng Việt trung tính (< 180 từ).

        Args:
            ticket_description: Nội dung mô tả sự cố của khách hàng.

        Returns:
            Đối tượng `CopilotPackageResponse` hoàn chỉnh.
        """
        # =====================================================================
        # BƯỚC 1: QUÉT AN TOÀN KHẨN CẤP (MANDATORY SAFETY ROUTING)
        # =====================================================================
        if check_safety_hazard(ticket_description):
            logger.warning(
                "Phát hiện dấu hiệu mất an toàn! Kích hoạt ngắt khẩn cấp (Hazard Escalation)."
            )
            return self._build_hazard_emergency_package(ticket_description)

        # =====================================================================
        # BƯỚC 2: TRUY XUẤT BẰNG CHỨNG TỪ KNOWLEDGE BASE
        # =====================================================================
        citations: List[CitationItem] = await search_knowledge_passages(
            query=ticket_description,
            db=self.db,
        )

        # =====================================================================
        # BƯỚC 3: PHÂN TÍCH INTENT, TÓM TẮT SỰ CỐ & TẠO PHẢN HỒI NHÁP (< 180 TỪ)
        # =====================================================================
        return await self._generate_copilot_analysis(
            ticket_description=ticket_description,
            citations=citations,
        )

    def _build_hazard_emergency_package(
        self,
        ticket_description: str,
    ) -> CopilotPackageResponse:
        """Tạo gói phản hồi ngắt an toàn khẩn cấp mà không gọi mô hình AI."""
        emergency_draft = (
            "CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn "
            "(khói, cháy nổ hoặc sự cố điện) từ mô tả của quý khách. Quý khách vui lòng "
            "ngắt nguồn điện cấp cho thiết bị ngay lập tức nếu đảm bảo an toàn, giữ khoảng "
            "cách an toàn và tuyệt đối không tự ý kiểm tra hay khởi động lại máy. Yêu cầu "
            "này đã được chuyển khẩn cấp tới Kỹ sư Phụ trách An toàn của SongNhat để liên "
            "hệ hỗ trợ trực tiếp."
        )
        return CopilotPackageResponse(
            intent=IntentEnum.TECHNICAL_ESCALATION,
            summary=CaseSummary(
                reported_symptom=ticket_description.strip(),
                confirmed_observation=(
                    "Phát hiện từ khóa cảnh báo nguy cơ mất an toàn nghiêm trọng "
                    "(cháy, nổ, bốc khói hoặc điện giật)."
                ),
                outstanding_questions=(
                    "Đã ngắt nguồn điện tổng chưa? Khu vực xung quanh thiết bị và nhân sự "
                    "vận hành hiện đã đảm bảo an toàn chưa?"
                ),
            ),
            missing_facts=[
                "Tình trạng ngắt nguồn điện khẩn cấp tại hiện trường",
                "Số điện thoại liên hệ trực tiếp của người phụ trách tại hiện trường",
                "Mã Serial (S/N) và vị trí lắp đặt thiết bị",
            ],
            draft_response=emergency_draft,
            citations=[],
            is_hazard_escalated=True,
        )

    async def _generate_copilot_analysis(
        self,
        ticket_description: str,
        citations: List[CitationItem],
    ) -> CopilotPackageResponse:
        """Phân tích Intent, tóm tắt và tạo bản nháp phản hồi dựa trên bằng chứng."""
        intent = self._classify_intent_from_text(ticket_description)
        missing_facts = self._detect_missing_facts(ticket_description, intent)
        summary = self._build_case_summary(ticket_description, citations, missing_facts)
        draft_response = self._compose_neutral_draft(
            ticket_description=ticket_description,
            intent=intent,
            citations=citations,
            missing_facts=missing_facts,
        )

        return CopilotPackageResponse(
            intent=intent,
            summary=summary,
            missing_facts=missing_facts,
            draft_response=draft_response,
            citations=citations,
            is_hazard_escalated=False,
        )

    def _classify_intent_from_text(self, text: str) -> IntentEnum:
        """Phân loại ý định ticket vào 1 trong 3 danh mục SongNhat."""
        lowered = text.lower()

        doc_keywords = ["tài liệu", "manual", "sơ đồ", "hướng dẫn", "catalog", "datasheet"]
        if any(keyword in lowered for keyword in doc_keywords):
            return IntentEnum.DOCUMENT_REQUEST

        progress_keywords = ["tiến độ", "bảo hành", "khi nào xong", "giao hàng", "tình trạng sửa"]
        if any(keyword in lowered for keyword in progress_keywords):
            return IntentEnum.SERVICE_PROGRESS

        return IntentEnum.TECHNICAL_ESCALATION

    def _detect_missing_facts(self, text: str, intent: IntentEnum) -> List[str]:
        """Xác định các thông tin kỹ thuật còn thiếu trong mô tả của khách hàng."""
        lowered = text.lower()
        missing: List[str] = []

        if "serial" not in lowered and "s/n" not in lowered:
            missing.append("Mã Serial (S/N) của thiết bị")
        if "firmware" not in lowered and "phiên bản" not in lowered:
            missing.append("Phiên bản Firmware hiện tại")

        if intent == IntentEnum.TECHNICAL_ESCALATION:
            if "p1120" not in lowered and "thời gian tăng tốc" not in lowered:
                missing.append("Thông số thời gian tăng tốc (P1120) và công suất tải")
            if "r0027" not in lowered and "dòng điện" not in lowered:
                missing.append("Giá trị dòng điện đầu ra tại thời điểm báo lỗi")

        return missing

    def _build_case_summary(
        self,
        ticket_description: str,
        citations: List[CitationItem],
        missing_facts: List[str],
    ) -> CaseSummary:
        """Tạo cấu trúc tóm tắt sự cố (CaseSummary)."""
        confirmed_obs: Optional[str] = None
        if citations:
            confirmed_obs = (
                f"Đã đối chiếu với '{citations[0].document_title}' (trang {citations[0].page_number}): "
                f"{citations[0].content_snippet}"
            )

        questions: Optional[str] = None
        if missing_facts:
            questions = (
                "Cần khách hàng cung cấp bổ sung: " + ", ".join(missing_facts) + "."
            )

        return CaseSummary(
            reported_symptom=ticket_description.strip(),
            confirmed_observation=confirmed_obs,
            outstanding_questions=questions,
        )

    def _compose_neutral_draft(
        self,
        ticket_description: str,
        intent: IntentEnum,
        citations: List[CitationItem],
        missing_facts: List[str],
    ) -> str:
        """Soạn thảo phản hồi tiếng Việt trung tính, có căn cứ và dưới 180 từ."""
        if intent == IntentEnum.DOCUMENT_REQUEST:
            draft = (
                "Chào quý khách, bộ phận Hỗ trợ Kỹ thuật SongNhat đã tiếp nhận yêu cầu "
                "cung cấp tài liệu của quý khách. Dựa trên hệ thống cơ sở tri thức, chúng "
                "tôi đã trích xuất các phần hướng dẫn liên quan đính kèm. Để gửi chính xác "
                "bộ sơ đồ đấu nối và tài liệu theo đúng đời máy, quý khách vui lòng phản hồi "
                "thêm Mã Serial (S/N) và mã hiệu đầy đủ trên nhãn thiết bị. Trân trọng."
            )
        elif intent == IntentEnum.SERVICE_PROGRESS:
            draft = (
                "Chào quý khách, bộ phận Dịch vụ SongNhat đã nhận được yêu cầu tra cứu "
                "tiến độ của quý khách. Để chúng tôi kiểm tra chính xác trạng thái xử lý "
                "trên hệ thống quản lý bảo hành, quý khách vui lòng cung cấp Mã phiếu dịch vụ "
                "hoặc Mã Serial (S/N) của thiết bị. Nhân viên phụ trách sẽ phản hồi chi tiết "
                "ngay sau khi đối chiếu thông tin. Trân trọng."
            )
        else:
            citation_ref = (
                f"Theo {citations[0].document_title} (trang {citations[0].page_number}), "
                "hiện tượng này thường liên quan đến quá dòng phần cứng tại IGBT, chạm đất "
                "cáp động cơ hoặc thời gian tăng tốc (P1120) cài đặt quá ngắn so với tải."
                if citations
                else "Chúng tôi đã ghi nhận triệu chứng kỹ thuật để chuyển kỹ sư chuyên trách kiểm tra."
            )
            missing_str = (
                ", ".join(missing_facts[:3])
                if missing_facts
                else "Mã Serial và Phiên bản Firmware"
            )
            draft = (
                f"Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "
                f"\"{ticket_description.strip()}\". {citation_ref} "
                f"Để kỹ sư chẩn đoán chính xác và hướng dẫn xử lý an toàn, quý khách vui lòng "
                f"cung cấp thêm: {missing_str}. Trong thời gian chờ phản hồi, quý khách vui lòng "
                f"không liên tục reset nguồn khi chưa kiểm tra cách điện cáp động cơ. Trân trọng."
            )

        # Đảm bảo chắc chắn giới hạn dưới 180 từ
        words = draft.split()
        if len(words) >= 180:
            draft = " ".join(words[:175]) + "..."
        return draft
