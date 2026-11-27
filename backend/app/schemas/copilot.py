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
    revision: Optional[str] = Field(
        default=None,
        description="Phiên bản revision tài liệu (DAT 04 / CRM-61)",
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
    effective_date: Optional[str] = Field(
        default=None,
        description="Ngày hiệu lực của tài liệu/đoạn trích (DAT 08)",
        examples=["2025-01-15"],
    )
    deep_link: Optional[str] = Field(
        default=None,
        description="Liên kết trực tiếp tới tài liệu gốc (DAT 05)",
    )
    stable_ref: Optional[str] = Field(
        default=None,
        description="Tham chiếu ổn định để tra cứu thủ công khi không có deep_link (DAT 05)",
    )
    supersession_ref: Optional[str] = Field(
        default=None,
        description="Mã/tham chiếu tài liệu thay thế nếu đã superseded (DAT 04 / DAT 08)",
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

    @model_validator(mode="after")
    def populate_citation_defaults(self) -> "CitationItem":
        """Đồng bộ revision/version và tạo stable_ref mặc định khi thiếu deep_link."""
        if self.revision is None and self.version is not None:
            self.revision = self.version
        elif self.version is None and self.revision is not None:
            self.version = self.revision

        if not self.deep_link and not self.stable_ref:
            rev_label = self.revision or self.version or "v1.0"
            sec_label = self.section or "General"
            self.stable_ref = (
                f"{self.document_title} | Rev {rev_label} | Mục {sec_label} | Trang {self.page_number}"
            )
        return self


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

    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

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
    status: str = Field(
        default="COMPLETED",
        description="Trạng thái xử lý Support Package (COMPLETED hoặc HOLD khi vượt ngân sách/lỗi provider)",
    )
    hold_reason: Optional[str] = Field(
        default=None,
        description="Lý do cách ly an toàn (HOLD) khi vượt Token Budget Cap, vượt số call hoặc lỗi provider",
    )
    grounding_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Tỷ lệ thông tin kỹ thuật trong draft có passage_id đối chứng thực tế (mục tiêu >= 0.95)",
    )
    model_version: Optional[str] = Field(
        default="songnhat-copilot-v2.1",
        description="Phiên bản mô hình AI xử lý gói hỗ trợ",
    )
    prompt_version: Optional[str] = Field(
        default="songnhat-rfp-prompt-v2.1",
        description="Phiên bản mẫu prompt áp dụng",
    )
    token_usage: dict[str, int] = Field(
        default_factory=lambda: {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        description="Thống kê số lượng token đầu vào, đầu ra và tổng số token sử dụng",
    )
    latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Tổng thời gian xử lý gói hỗ trợ tính bằng mili-giây",
    )
    quarantined_passages: List[dict[str, Any]] = Field(
        default_factory=list,
        description="Danh sách các passage bị cách ly kèm lý do (vượt giới hạn ký tự hoặc token budget)",
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
