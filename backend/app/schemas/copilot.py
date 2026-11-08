"""Pydantic schemas for Copilot Engine (Task CRM-24)."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


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


class CaseSummary(BaseModel):
    """Tóm tắt có cấu trúc về sự cố kỹ thuật của khách hàng."""

    reported_symptom: str = Field(
        ...,
        description="Triệu chứng sự cố do khách hàng báo cáo",
    )
    confirmed_observation: Optional[str] = Field(
        default=None,
        description="Các quan sát kỹ thuật đã được xác nhận từ mô tả",
    )
    outstanding_questions: Optional[str] = Field(
        default=None,
        description="Các câu hỏi hoặc thông tin cần làm rõ thêm với khách hàng",
    )


class CopilotPackageResponse(BaseModel):
    """Gói kết quả phân tích sự cố và trích xuất bằng chứng từ Copilot Engine."""

    intent: IntentEnum = Field(
        ...,
        description="Ý định chính của ticket sau khi phân loại",
    )
    summary: CaseSummary = Field(
        ...,
        description="Bản tóm tắt sự cố có cấu trúc",
    )
    missing_facts: List[str] = Field(
        default_factory=list,
        description="Danh sách các thông tin kỹ thuật còn thiếu (VD: Mã Serial, Phiên bản Firmware)",
    )
    draft_response: str = Field(
        ...,
        description="Bản nháp phản hồi tiếng Việt trung tính, giới hạn dưới 180 từ",
    )
    citations: List[CitationItem] = Field(
        default_factory=list,
        description="Danh sách các trích dẫn bằng chứng từ cơ sở tri thức",
    )
    is_hazard_escalated: bool = Field(
        default=False,
        description="Cờ đánh dấu ngắt an toàn khẩn cấp khi phát hiện nguy cơ cháy nổ/điện giật",
    )

    @field_validator("draft_response")
    @classmethod
    def validate_word_limit(cls, value: str) -> str:
        """Đảm bảo bản nháp phản hồi không vượt quá 180 từ."""
        word_count = len(value.split())
        if word_count >= 180:
            raise ValueError(
                f"draft_response phải dưới 180 từ (hiện tại: {word_count} từ)."
            )
        return value
