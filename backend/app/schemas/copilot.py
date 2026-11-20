"""Pydantic schemas for Copilot Engine & Support Package (Tasks CRM-24 & CRM-28)."""

from enum import Enum
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class IntentEnum(str, Enum):
    """Phân loại ý định (Intent) theo 3 danh mục chuẩn SongNhat."""

    DOCUMENT_REQUEST = "DOCUMENT_REQUEST"
    SERVICE_PROGRESS = "SERVICE_PROGRESS"
    TECHNICAL_ESCALATION = "TECHNICAL_ESCALATION"


class CitationItem(BaseModel):
    """Thông tin trích dẫn bằng chứng từ tài liệu kỹ thuật."""

    document_title: str = Field(
        ...,
        description="Tên tài liệu kỹ thuật hoặc hướng dẫn sử dụng",
        examples=["SINAMICS G120 Operating Instructions"],
    )
    page_number: int = Field(
        ...,
        ge=1,
        description="Số trang trong tài liệu trích dẫn",
        examples=[142],
    )
    content_snippet: str = Field(
        ...,
        description="Đoạn nội dung trích xuất làm bằng chứng kỹ thuật",
    )
    section: Optional[str] = Field(
        default=None,
        description="Mục tài liệu hoặc chương trích dẫn (DAT 08)",
        examples=["4.2 - Electrical Connection & Starting Troubleshooting"],
    )
    version: Optional[str] = Field(
        default=None,
        description="Phiên bản tài liệu kỹ thuật",
        examples=["Rev. G (2025)"],
    )
    passage_id: Optional[str] = Field(
        default=None,
        description="Mã định danh đoạn trích dẫn trong cơ sở dữ liệu",
    )
    document_code: Optional[str] = Field(
        default=None,
        description="Mã hiệu tài liệu kỹ thuật",
        examples=["3GZF500730-87"],
    )
    status: Optional[str] = Field(
        default=None,
        description="Trạng thái hiệu lực nguồn (current, draft, superseded, withdrawn)",
        examples=["current"],
    )
    product_model: Optional[str] = Field(
        default=None,
        description="Model sản phẩm áp dụng",
        examples=["SD700"],
    )
    serial_range: Optional[str] = Field(
        default=None,
        description="Dải serial áp dụng",
        examples=["SN1000-SN5000"],
    )


class CaseSummary(BaseModel):
    """Tóm tắt có cấu trúc về sự cố kỹ thuật của khách hàng."""

    reported_symptom: str = Field(
        ...,
        description="Triệu chứng sự cố do khách hàng báo cáo",
    )
    confirmed_observation: Optional[str] = Field(
        default=None,
        description="Các quan sát kỹ thuật đã được xác nhận từ mô tả hoặc tài liệu",
    )
    outstanding_questions: Optional[str] = Field(
        default=None,
        description="Các câu hỏi hoặc thông tin cần làm rõ thêm với khách hàng",
    )


class CopilotAnalyzeRequest(BaseModel):
    """Yêu cầu phân tích ticket độc lập từ Frontend hoặc API."""

    ticket_description: str = Field(
        ...,
        description="Nội dung tiêu đề hoặc mô tả sự cố kỹ thuật của ticket",
        examples=["Biến tần báo lỗi F0022 khi tăng tốc"],
    )
    ticket_id: Optional[UUID] = Field(
        default=None,
        description="Mã định danh ticket (nếu có để lưu kết quả vào CSDL)",
    )
    product_id: Optional[UUID] = Field(
        default=None,
        description="Mã định danh nhóm sản phẩm liên quan (Motors / Drives)",
    )
    limit: Optional[int] = Field(
        default=3,
        ge=1,
        le=10,
        description="Số lượng trích dẫn tài liệu tối đa cần truy xuất",
    )


class CopilotPackageResponse(BaseModel):
    """Gói Support Package đầy đủ 5 thành phần bắt buộc + cờ an toàn (Task CRM-28 & SUP-01 - SUP-08)."""

    model_config = ConfigDict(populate_by_name=True)

    intent: IntentEnum = Field(
        ...,
        description="Ý định chính của ticket sau khi phân loại (DOCUMENT_REQUEST, SERVICE_PROGRESS, TECHNICAL_ESCALATION)",
    )
    summary: CaseSummary = Field(
        ...,
        description="Bản tóm tắt sự cố có cấu trúc (reported_symptom, confirmed_observation, outstanding_questions)",
    )
    missing_facts: List[str] = Field(
        default_factory=list,
        description="Danh sách các thông tin kỹ thuật còn thiếu (Mã Serial, Firmware, Tải, v.v.)",
    )
    citations: List[CitationItem] = Field(
        default_factory=list,
        description="Danh sách các trích dẫn bằng chứng từ cơ sở tri thức (knowledge_passages)",
    )
    next_step: str = Field(
        default="Chuyển kỹ sư chuyên trách kiểm tra.",
        description="Hành động xử lý tiếp theo đề xuất cho kỹ thuật viên",
    )
    draft: str = Field(
        ...,
        description="Bản nháp phản hồi khách hàng bằng tiếng Việt trung tính, bắt buộc dưới 180 từ",
    )
    draft_response: Optional[str] = Field(
        default=None,
        description="Alias tương thích ngược với Task CRM-24",
    )
    draft_reply: Optional[str] = Field(
        default=None,
        description="Alias tương thích với Postman Collection TC-22 & TC-25",
    )
    is_hazard_escalated: bool = Field(
        default=False,
        description="Cờ đánh dấu ngắt an toàn khẩn cấp khi phát hiện nguy cơ cháy nổ/điện giật/khói",
    )

    @model_validator(mode="before")
    @classmethod
    def sync_draft_fields(cls, data: Any) -> Any:
        """Đồng bộ các thuộc tính draft, draft_response và draft_reply."""
        if isinstance(data, dict):
            # Lấy nội dung draft từ bất kỳ trường nào có sẵn
            content = data.get("draft") or data.get("draft_response") or data.get("draft_reply") or ""
            if not data.get("draft"):
                data["draft"] = content
            if not data.get("draft_response"):
                data["draft_response"] = content
            if "draft_reply" not in data or data["draft_reply"] is None:
                # Postman TC-25 yêu cầu draft_reply rỗng khi có nguy hiểm
                if data.get("is_hazard_escalated", False):
                    data["draft_reply"] = ""
                else:
                    data["draft_reply"] = content
        return data

    @field_validator("draft", "draft_response")
    @classmethod
    def validate_word_limit(cls, value: Optional[str]) -> Optional[str]:
        """Đảm bảo bản nháp phản hồi không vượt quá 180 từ."""
        if value:
            word_count = len(value.split())
            if word_count >= 180:
                raise ValueError(
                    f"Bản nháp phản hồi phải dưới 180 từ (hiện tại: {word_count} từ)."
                )
        return value


# Alias SupportPackageOut theo chuẩn SongNhat RFP
SupportPackageOut = CopilotPackageResponse
