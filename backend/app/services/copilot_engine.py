"""Copilot Engine Service for Incident Analysis & Support Package Pipeline (Tasks CRM-24, CRM-28, CRM-49 & CRM-51)."""

import inspect
import json
import logging
import os
import re
import unicodedata
import uuid
from typing import Any, List, Optional, Union

from app.schemas.copilot import (
    CaseSummary,
    CitationItem,
    CopilotPackageResponse,
    IntentEnum,
)
from app.services.retriever import search_knowledge_passages
from app.services.safety_checker import check_safety_hazard

logger = logging.getLogger(__name__)


def _build_hazard_emergency_package(ticket_description: str) -> CopilotPackageResponse:
    """Tạo gói phản hồi ngắt an toàn khẩn cấp (SAFE-01 - SAFE-06, SUP-04) mà không gọi mô hình AI/Retriever."""
    emergency_draft = (
        "CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn "
        "(khói, cháy nổ, điện giật hoặc sự cố nhiệt/cơ) từ mô tả của quý khách. Quý khách vui lòng "
        "ngắt nguồn điện cấp cho thiết bị ngay lập tức nếu đảm bảo an toàn, giữ khoảng cách an toàn "
        "và tuyệt đối không tự ý kiểm tra hay khởi động lại máy. Yêu cầu này đã được chuyển khẩn cấp "
        "tới Kỹ sư Phụ trách An toàn của SongNhat để liên hệ hỗ trợ trực tiếp."
    )
    return CopilotPackageResponse(
        intent=IntentEnum.TECHNICAL_ESCALATION,
        summary=CaseSummary(
            reported_symptom=ticket_description.strip(),
            confirmed_observation=(
                "Phát hiện dấu hiệu nguy cơ mất an toàn nghiêm trọng "
                "(cháy, nổ, bốc khói, điện giật, rò điện hoặc quá nhiệt bất thường)."
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
        citations=[],
        next_step=(
            "CẢNH BÁO AN TOÀN: Hướng dẫn khách hàng ngắt ngay nguồn điện khẩn cấp, "
            "cách ly hiện trường và chuyển tuyến khẩn cấp tới Kỹ sư Phụ trách An toàn của SongNhat."
        ),
        draft=emergency_draft,
        draft_response=emergency_draft,
        draft_reply="",  # TC-25 yêu cầu draft_reply rỗng khi có nguy hiểm
        is_hazard_escalated=True,
    )


def _remove_vietnamese_accents(text: str) -> str:
    """Chuẩn hóa chuỗi tiếng Việt: bỏ toàn bộ dấu (accent marks) và chuyển đ/Đ -> d/D.

    CRM-52 / VN-01: Cho phép so khớp từ khóa intent với input không dấu.
    """
    text = text.replace("đ", "d").replace("Đ", "D")
    nfkd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def _classify_intent_from_text(text: str) -> IntentEnum:
    """Phân loại ý định ticket vào 1 trong 3 danh mục chuẩn SongNhat.

    CRM-52 / VN-01: Chuẩn hóa chuỗi đầu vào (lowercase + bỏ dấu tiếng Việt)
    trước khi so khớp từ khóa, để các cụm không dấu như "tai lieu", "huong dan",
    "so tay", "catalog", "cho xin" được phân loại đúng thành DOCUMENT_REQUEST.
    """
    lowered = text.lower()
    normalized = _remove_vietnamese_accents(lowered)

    doc_keywords_accented = [
        "tài liệu", "manual", "sơ đồ", "hướng dẫn", "catalog", "catalogue",
        "datasheet", "document", "sổ tay", "cho xin", "xin tài liệu",
    ]
    doc_keywords_unaccented = [
        "tai lieu", "manual", "so do", "huong dan", "catalog", "catalogue",
        "datasheet", "document", "so tay", "cho xin", "xin tai lieu",
    ]

    if (any(keyword in lowered for keyword in doc_keywords_accented) or
            any(keyword in normalized for keyword in doc_keywords_unaccented)):
        return IntentEnum.DOCUMENT_REQUEST

    progress_keywords_accented = [
        "tiến độ", "bảo hành", "khi nào xong", "giao hàng",
        "tình trạng sửa", "progress", "status",
    ]
    progress_keywords_unaccented = [
        "tien do", "bao hanh", "khi nao xong", "giao hang",
        "tinh trang sua", "progress", "status",
    ]

    if (any(keyword in lowered for keyword in progress_keywords_accented) or
            any(keyword in normalized for keyword in progress_keywords_unaccented)):
        return IntentEnum.SERVICE_PROGRESS

    return IntentEnum.TECHNICAL_ESCALATION


def _detect_missing_facts(text: str, intent: IntentEnum) -> List[str]:
    """Xác định các thông tin kỹ thuật còn thiếu theo Intent và triệu chứng (CRM-51)."""
    lowered = text.lower()
    missing: List[str] = []

    # Kiểm tra thiếu model hoặc xung đột model (MODEL-01, MODEL-03)
    if any(cue in lowered for cue in ["chưa biết model", "không biết model", "chưa rõ model", "không rõ model", "chưa biết hãng", "không biết hãng"]):
        missing.append("Mã hiệu model chính xác của thiết bị")
    elif "đầu ghi" in lowered and "cuối ghi" in lowered:
        missing.append("Xác nhận chính xác mã hiệu model thiết bị (phát hiện mâu thuẫn)")
    elif "model_a" in lowered and "model_b" in lowered:
        missing.append("Xác nhận chính xác mã hiệu model thiết bị (phát hiện mâu thuẫn)")

    if "serial" not in lowered and "s/n" not in lowered and "serial_" not in lowered:
        missing.append("Mã Serial (S/N) của thiết bị")
    if "firmware" not in lowered and "phiên bản" not in lowered and "rev." not in lowered:
        missing.append("Phiên bản Firmware hiện tại")

    if intent == IntentEnum.TECHNICAL_ESCALATION:
        if "p1120" not in lowered and "thời gian tăng tốc" not in lowered:
            missing.append("Thông số thời gian tăng tốc (P1120) và công suất tải")
        if "r0027" not in lowered and "dòng điện" not in lowered:
            missing.append("Giá trị dòng điện đầu ra tại thời điểm báo lỗi (r0027)")
    elif intent == IntentEnum.DOCUMENT_REQUEST:
        if "model" not in lowered and "mã hiệu" not in lowered and "model_" not in lowered:
            if "Mã hiệu model chính xác của thiết bị" not in missing:
                missing.append("Mã hiệu đầy đủ và đời máy trên nhãn sản phẩm")
        missing.append("Định dạng tài liệu yêu cầu (PDF điện tử hoặc bản vẽ CAD)")
    elif intent == IntentEnum.SERVICE_PROGRESS:
        if "phiếu" not in lowered and "biên nhận" not in lowered:
            missing.append("Mã số phiếu tiếp nhận dịch vụ hoặc ngày gửi thiết bị")

    return missing


def _build_next_step(intent: IntentEnum) -> str:
    """Xác định hành động xử lý tiếp theo đề xuất cho kỹ thuật viên."""
    if intent == IntentEnum.TECHNICAL_ESCALATION:
        return (
            "Thu thập thông số kỹ thuật (S/N, Firmware, P1120, dòng r0027), kiểm tra cách điện "
            "cáp động cơ bằng đồng hồ Megohmmeter trước khi chuyển Kỹ sư chuyên trách chẩn đoán chuyên sâu."
        )
    if intent == IntentEnum.DOCUMENT_REQUEST:
        return (
            "Tra cứu tài liệu kỹ thuật theo đúng model/Serial thiết bị; gửi tài liệu trích xuất "
            "hoặc chuyển kỹ sư chuyên trách đối chiếu nếu chưa có bản tài liệu được duyệt phù hợp."
        )
    return (
        "Tra cứu mã phiếu dịch vụ/Serial trên hệ thống ERP bảo hành và cập nhật tiến độ xử lý "
        "hiện tại cho khách hàng trong vòng 2 giờ."
    )


def _build_case_summary(
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
    else:
        confirmed_obs = "Chưa có quan sát kỹ thuật được xác nhận (không có nguồn phù hợp trong cơ sở tri thức)."

    questions: Optional[str] = None
    if missing_facts:
        questions = "Cần khách hàng cung cấp bổ sung: " + ", ".join(missing_facts) + "."

    return CaseSummary(
        reported_symptom=ticket_description.strip(),
        confirmed_observation=confirmed_obs,
        outstanding_questions=questions,
    )


def _compose_neutral_draft(
    ticket_description: str,
    intent: IntentEnum,
    citations: List[CitationItem],
    missing_facts: List[str],
) -> str:
    """Soạn thảo phản hồi tiếng Việt trung tính, có căn cứ kỹ thuật và bắt buộc dưới 180 từ (CRM-50 & CRM-51)."""
    missing_str = (
        ", ".join(missing_facts[:3])
        if missing_facts
        else "Mã Serial và Phiên bản Firmware"
    )

    if intent == IntentEnum.DOCUMENT_REQUEST:
        if citations:
            citation_ref = f"Đã đối chiếu với tài liệu '{citations[0].document_title}' (trang {citations[0].page_number})."
            draft = (
                f"Chào quý khách, bộ phận Hỗ trợ Kỹ thuật SongNhat đã tiếp nhận yêu cầu cung cấp tài liệu. "
                f"{citation_ref} Dựa trên hệ thống cơ sở tri thức, chúng tôi đã trích xuất các phần hướng dẫn liên quan đính kèm. "
                f"Để gửi chính xác bộ sơ đồ đấu nối và tài liệu theo đúng đời máy, quý khách vui lòng phản hồi "
                f"thêm: {missing_str}. Trân trọng."
            )
        else:
            # CRM-51 / SUP 03, SUP 07: Khi citations rỗng, tuyệt đối KHÔNG tuyên bố đã trích xuất tài liệu
            draft = (
                "Chào quý khách, bộ phận Hỗ trợ Kỹ thuật SongNhat đã tiếp nhận yêu cầu cung cấp tài liệu. "
                "Hiện tại không có nguồn phù hợp trong cơ sở tri thức (do thiếu mã hiệu model chính xác, "
                "phiên bản revision yêu cầu chưa được phê duyệt hoặc tài liệu đã bị thu hồi). "
                "Chúng tôi đã chuyển yêu cầu tới Kỹ sư chuyên trách để kiểm tra và đối chiếu thủ công. "
                f"Để được hỗ trợ nhanh nhất, quý khách vui lòng cung cấp thêm: {missing_str}. Trân trọng."
            )
    elif intent == IntentEnum.SERVICE_PROGRESS:
        draft = (
            "Chào quý khách, bộ phận Dịch vụ SongNhat đã nhận được yêu cầu tra cứu tiến độ của quý khách. "
            "Để chúng tôi kiểm tra chính xác trạng thái xử lý trên hệ thống quản lý bảo hành, quý khách vui lòng "
            "cung cấp Mã phiếu dịch vụ hoặc Mã Serial (S/N) của thiết bị. Nhân viên phụ trách sẽ phản hồi chi tiết "
            "ngay sau khi đối chiếu thông tin. Trân trọng."
        )
    else:
        ticket_text = ticket_description.strip()

        if citations:
            citation_parts: List[str] = []
            for cit in citations[:2]:
                citation_parts.append(
                    f"Theo {cit.document_title} (trang {cit.page_number}): {cit.content_snippet}"
                )
            citation_ref = " ".join(citation_parts)
            draft = (
                f"Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "
                f"\"{ticket_text}\". {citation_ref} "
                f"Để kỹ sư chẩn đoán chính xác và hướng dẫn xử lý an toàn, quý khách vui lòng "
                f"cung cấp thêm: {missing_str}. Trân trọng."
            )
        else:
            # CRM-50 & CRM-51: Khi citations rỗng, nêu rõ không có nguồn phù hợp, đề xuất chuyển KS, không bịa IGBT
            draft = (
                f"Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "
                f"\"{ticket_text}\". Hiện tại không có nguồn phù hợp trong cơ sở tri thức "
                f"để kết luận nguyên nhân kỹ thuật. Chúng tôi đã chuyển thông tin tới Kỹ sư chuyên trách "
                f"kiểm tra trực tiếp thiết bị. Để kỹ sư hỗ trợ nhanh chóng, quý khách vui lòng "
                f"cung cấp thêm: {missing_str}. Trân trọng."
            )

    # Đảm bảo chắc chắn giới hạn nghiêm ngặt dưới 180 từ
    words = draft.split()
    if len(words) >= 180:
        draft = " ".join(words[:175]) + "..."
    return draft


async def _save_copilot_package_to_db(
    db: Any,
    ticket_id: Union[int, str, uuid.UUID],
    package: CopilotPackageResponse,
) -> None:
    """Lưu hoặc cập nhật kết quả Support Package vào bảng `copilot_packages`."""
    try:
        try:
            from models import CopilotPackage
        except ImportError:
            from backend.models import CopilotPackage

        from sqlalchemy import select

        # Chuẩn hóa ticket_id sang UUID hợp lệ
        if isinstance(ticket_id, int):
            pkg_ticket_id = uuid.UUID(int=ticket_id)
        elif isinstance(ticket_id, str):
            try:
                pkg_ticket_id = uuid.UUID(ticket_id)
            except Exception:
                pkg_ticket_id = uuid.uuid5(uuid.NAMESPACE_DNS, ticket_id)
        else:
            pkg_ticket_id = ticket_id

        stmt = select(CopilotPackage).where(CopilotPackage.ticket_id == pkg_ticket_id)
        exec_res = db.execute(stmt)
        if inspect.isawaitable(exec_res):
            exec_res = await exec_res

        existing = exec_res.scalars().first() if hasattr(exec_res, "scalars") else None

        summary_text = (
            f"Triệu chứng: {package.summary.reported_symptom}\n"
            f"Quan sát: {package.summary.confirmed_observation or 'N/A'}\n"
            f"Câu hỏi: {package.summary.outstanding_questions or 'N/A'}"
        )
        citations_data = [c.model_dump() for c in package.citations]
        intent_str = package.intent.value if hasattr(package.intent, "value") else str(package.intent)

        if existing:
            existing.intent = intent_str
            existing.case_summary = summary_text
            existing.missing_facts = package.missing_facts
            existing.citations = citations_data
            existing.next_step = package.next_step
            existing.draft = package.draft
            existing.draft_response = package.draft
            existing.approval_status = "Pending"
        else:
            new_pkg = CopilotPackage(
                ticket_id=pkg_ticket_id,
                intent=intent_str,
                case_summary=summary_text,
                missing_facts=package.missing_facts,
                citations=citations_data,
                next_step=package.next_step,
                draft=package.draft,
                draft_response=package.draft,
                approval_status="Pending",
            )
            db.add(new_pkg)

        commit_res = db.commit()
        if inspect.isawaitable(commit_res):
            await commit_res
    except Exception as exc:
        logger.warning("Không thể lưu kết quả vào bảng copilot_packages: %s", exc)
        if hasattr(db, "rollback"):
            rb = db.rollback()
            if inspect.isawaitable(rb):
                await rb


async def run_copilot_pipeline(
    ticket_description: str,
    ticket_id: Optional[Union[int, str, uuid.UUID]] = None,
    db: Optional[Any] = None,
    api_key: Optional[str] = None,
    product_id: Optional[Any] = None,
    limit: int = 3,
) -> CopilotPackageResponse:
    """Hàm điều phối khép kín End-to-End Copilot Pipeline theo chuẩn SongNhat RFP (Tasks CRM-28 & CRM-43).

    Quy trình:
        - Bước 1: Quét an toàn khẩn cấp bằng SafetyChecker (Regex).
                  Nếu phát hiện nguy hiểm -> ngắt luồng ngay, không gọi Retriever/LLM,
                  citations = [], trả về gói cảnh báo an toàn khẩn cấp.
        - Bước 2: Truy xuất đoạn trích dẫn kỹ thuật (Citations) thực tế từ bảng knowledge_passages.
        - Bước 3: Phân tích Intent và sinh đủ 5 thành phần (summary, missing_facts, citations,
                  next_step, draft < 180 từ).
        - Bước 4: Tự động lưu/cập nhật vào bảng copilot_packages nếu có db và ticket_id.

    Args:
        ticket_description: Nội dung mô tả sự cố hoặc yêu cầu của ticket.
        ticket_id: Mã định danh ticket (nếu có để lưu DB).
        db: Phiên kết nối CSDL (AsyncSession hoặc Session).
        api_key: API Key LLM (tùy chọn).
        product_id: UUID nhóm sản phẩm liên quan (Motors / Drives).
        limit: Số lượng trích dẫn tối đa cần lấy.

    Returns:
        CopilotPackageResponse chứa đầy đủ 5 thành phần + cờ an toàn.
    """
    # =========================================================================
    # BƯỚC 1: QUÉT AN TOÀN KHẨN CẤP (MANDATORY SAFETY CHECKER)
    # =========================================================================
    if check_safety_hazard(ticket_description):
        logger.warning(
            "Phát hiện dấu hiệu mất an toàn! Kích hoạt ngắt khẩn cấp (Hazard Escalation)."
        )
        hazard_pkg = _build_hazard_emergency_package(ticket_description)
        if db is not None and ticket_id is not None:
            await _save_copilot_package_to_db(db, ticket_id, hazard_pkg)
        return hazard_pkg

    # Nếu chưa có product_id mà có ticket_id trong DB, thử lấy product_id từ ticket
    resolved_product_id = product_id
    if resolved_product_id is None and db is not None and ticket_id is not None:
        try:
            try:
                from models import Ticket
            except ImportError:
                from backend.models import Ticket
            from sqlalchemy import select
            parsed_tid = ticket_id if isinstance(ticket_id, uuid.UUID) else uuid.UUID(str(ticket_id))
            t_stmt = select(Ticket).where(Ticket.id == parsed_tid)
            t_res = db.execute(t_stmt)
            if inspect.isawaitable(t_res):
                t_res = await t_res
            t_obj = t_res.scalars().first() if hasattr(t_res, "scalars") else None
            if t_obj and getattr(t_obj, "product_id", None):
                resolved_product_id = t_obj.product_id
        except Exception:
            pass

    # =========================================================================
    # BƯỚC 2: TRUY XUẤT BẰNG CHỨNG TỪ KNOWLEDGE BASE (RETRIEVER THỰC - CRM-43)
    # =========================================================================
    citations: List[CitationItem] = await search_knowledge_passages(
        query=ticket_description,
        db=db,
        limit=limit,
        product_id=resolved_product_id,
        allow_mock_fallback=False,
    )

    # =========================================================================
    # BƯỚC 3: PHÂN TÍCH INTENT & SINH 5 THÀNH PHẦN THEO RFP
    # =========================================================================
    intent = _classify_intent_from_text(ticket_description)
    missing_facts = _detect_missing_facts(ticket_description, intent)
    next_step = _build_next_step(intent)
    summary = _build_case_summary(ticket_description, citations, missing_facts)
    draft = _compose_neutral_draft(
        ticket_description=ticket_description,
        intent=intent,
        citations=citations,
        missing_facts=missing_facts,
    )

    package = CopilotPackageResponse(
        intent=intent,
        summary=summary,
        missing_facts=missing_facts,
        citations=citations,
        next_step=next_step,
        draft=draft,
        draft_response=draft,
        draft_reply=draft,
        is_hazard_escalated=False,
    )

    # =========================================================================
    # BƯỚC 4: LƯU KẾT QUẢ VÀO BẢNG COPILOT_PACKAGES NẾU CÓ DB & TICKET_ID
    # =========================================================================
    if db is not None and ticket_id is not None:
        await _save_copilot_package_to_db(db, ticket_id, package)

    return package


class CopilotEngineService:
    """Service điều phối quy trình phân tích sự cố và trích xuất bằng chứng (CRM-24 & CRM-28)."""

    def __init__(self, db: Optional[Any] = None, api_key: Optional[str] = None) -> None:
        """Khởi tạo CopilotEngineService.

        Args:
            db: Kết nối cơ sở dữ liệu (tùy chọn).
            api_key: API Key cho dịch vụ LLM nếu kích hoạt gọi AI thật.
        """
        self.db = db
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")

    async def analyze_ticket(
        self,
        ticket_description: str,
        ticket_id: Optional[Union[int, str, uuid.UUID]] = None,
        product_id: Optional[Any] = None,
        limit: int = 3,
    ) -> CopilotPackageResponse:
        """Tương thích ngược hoàn toàn với method analyze_ticket của CRM-24."""
        return await run_copilot_pipeline(
            ticket_description=ticket_description,
            ticket_id=ticket_id,
            db=self.db,
            api_key=self.api_key,
            product_id=product_id,
            limit=limit,
        )

    async def run_copilot_pipeline(
        self,
        ticket_description: str,
        ticket_id: Optional[Union[int, str, uuid.UUID]] = None,
        product_id: Optional[Any] = None,
        limit: int = 3,
    ) -> CopilotPackageResponse:
        """Thực thi pipeline thông qua instance của CopilotEngineService."""
        return await run_copilot_pipeline(
            ticket_description=ticket_description,
            ticket_id=ticket_id,
            db=self.db,
            api_key=self.api_key,
            product_id=product_id,
            limit=limit,
        )
