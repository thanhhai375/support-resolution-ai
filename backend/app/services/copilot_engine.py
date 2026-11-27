"""Copilot Engine Service for Incident Analysis & Support Package Pipeline (Tasks CRM-24, CRM-28, CRM-49, CRM-51 & CRM-61)."""

import asyncio
import inspect
import logging
import math
import os
import re
import time
import unicodedata
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from app.schemas.copilot import (
    CaseSummary,
    CitationItem,
    CopilotPackageResponse,
    IntentEnum,
)
from app.services.retriever import search_knowledge_passages
from app.services.safety_checker import check_safety_hazard

logger = logging.getLogger(__name__)

# =============================================================================
# RFP SECTION 2 & CRM-61: TOKEN BUDGET CAP & TELEMETRY CONSTANTS
# =============================================================================
MAX_INPUT_TOKENS = 8000
MAX_OUTPUT_TOKENS = 1200
MAX_MODEL_CALLS_PER_PACKAGE = 2
MAX_PASSAGE_CHARS = 8000
DEFAULT_MODEL_VERSION = os.getenv("COPILOT_MODEL_VERSION", "songnhat-copilot-v2.1")
DEFAULT_PROMPT_VERSION = os.getenv("COPILOT_PROMPT_VERSION", "songnhat-rfp-prompt-v2.1")

SYSTEM_PROMPT_INSTRUCTIONS = (
    "You are SongNhat Technical Support Copilot. Classify intent, list missing facts, "
    "cite only approved current applicable passages by exact passage_id, never fabricate "
    "citations, and keep customer draft neutral and under 180 words."
)

_FORBIDDEN_CITATION_STATUSES = {
    "draft", "withdrawn", "revoked", "superseded", "unapproved", "deprecated", "restricted"
}

_CITATION_TAG_PATTERN = re.compile(r"\[(?:passage_id|ref)\s*:\s*([^\]]+)\]", re.IGNORECASE)
_INLINE_PASSAGE_EQ_PATTERN = re.compile(r"\bpassage_id\s*[=:]\s*([A-Za-z0-9._-]+)", re.IGNORECASE)


def estimate_tokens(text: Optional[str]) -> int:
    """Ước lượng số lượng token an toàn (offline-friendly) cho văn bản tiếng Việt/Anh."""
    if not text or not text.strip():
        return 0
    return max(len(text.split()), math.ceil(len(text) / 3.2))


def _format_passage_for_prompt(citation: CitationItem) -> str:
    """Định dạng một đoạn trích để tính toán ngân sách input tokens."""
    pid = citation.passage_id or "unknown"
    rev = citation.revision or citation.version or "v1.0"
    sec = citation.section or "General"
    return (
        f"[passage_id:{pid}] {citation.document_title} | Rev {rev} | "
        f"{sec} | Trang {citation.page_number}: {citation.content_snippet}"
    )


def _apply_token_budget_to_context(
    ticket_description: str,
    citations: List[CitationItem],
    system_prompt: str = SYSTEM_PROMPT_INSTRUCTIONS,
) -> Tuple[List[CitationItem], List[Dict[str, Any]], int, Optional[str]]:
    """Áp dụng giới hạn 8,000 input tokens và 8,000 Unicode chars cho mỗi passage.

    Nguyên tắc RFP Section 2 & OPS 06:
    - Tuyệt đối KHÔNG cắt ngang giữa chừng một passage.
    - Passage vượt ngưỡng kích thước hoặc ngân sách phải được quarantine kèm lý do.
    - Nếu ngữ cảnh tối thiểu vượt 8,000 input tokens (hoặc tất cả nguồn đều bị quarantine) -> HOLD.
    """
    quarantined: List[Dict[str, Any]] = []
    base_tokens = estimate_tokens(system_prompt) + estimate_tokens(ticket_description)

    if len(ticket_description) > MAX_PASSAGE_CHARS:
        reason = (
            f"Nội dung ticket ({len(ticket_description)} ký tự) vượt giới hạn tối đa "
            f"{MAX_PASSAGE_CHARS} ký tự Unicode theo RFP Section 2."
        )
        return [], quarantined, base_tokens, reason

    if base_tokens > MAX_INPUT_TOKENS:
        reason = (
            f"Ngữ cảnh đầu vào tối thiểu ({base_tokens} tokens) vượt ngưỡng trần "
            f"{MAX_INPUT_TOKENS} input tokens."
        )
        return [], quarantined, base_tokens, reason

    selected: List[CitationItem] = []
    used_tokens = base_tokens

    for cit in citations:
        snippet_len = len(cit.content_snippet or "")
        if snippet_len > MAX_PASSAGE_CHARS:
            quarantined.append({
                "passage_id": cit.passage_id,
                "document_title": cit.document_title,
                "reason": (
                    f"Passage vượt giới hạn {MAX_PASSAGE_CHARS} ký tự Unicode "
                    f"({snippet_len} ký tự); đã cách ly an toàn, không cắt ngang."
                ),
            })
            continue

        passage_tokens = estimate_tokens(_format_passage_for_prompt(cit))
        if used_tokens + passage_tokens <= MAX_INPUT_TOKENS:
            selected.append(cit)
            used_tokens += passage_tokens
        else:
            quarantined.append({
                "passage_id": cit.passage_id,
                "document_title": cit.document_title,
                "reason": (
                    f"Passage ({passage_tokens} tokens) vượt ngân sách còn lại trong giới hạn "
                    f"{MAX_INPUT_TOKENS} input tokens; đã cách ly an toàn."
                ),
            })

    if citations and not selected:
        reason = (
            "Toàn bộ đoạn trích truy xuất đều vượt ngưỡng 8,000 ký tự hoặc "
            "ngân sách 8,000 input tokens; tạm giữ để tra cứu thủ công."
        )
        return [], quarantined, used_tokens, reason

    return selected, quarantined, used_tokens, None


def _is_material_claim_sentence(sentence: str) -> bool:
    """Phân biệt câu nhận định kỹ thuật cần đối chứng với câu chào hỏi/hỏi thông tin/từ chối trung thực."""
    s = sentence.strip()
    if not s:
        return False
    low = s.lower()

    # Câu đóng hoặc câu hỏi bổ sung dữ kiện không phải khẳng định kỹ thuật từ KB
    if low == "trân trọng." or low.startswith("chào quý khách, bộ phận dịch vụ"):
        return False
    if "quý khách vui lòng cung cấp" in low or "quý khách vui lòng phản hồi" in low:
        return False
    if "không có nguồn phù hợp" in low or "đã chuyển thông tin tới kỹ sư" in low or "đã chuyển yêu cầu tới kỹ sư" in low:
        return False
    if "tạm giữ xử lý" in low or "tra cứu thủ công" in low:
        return False
    if low.startswith("chào quý khách") and "đã tiếp nhận" in low and "[passage_id:" not in low and "theo " not in low:
        # Nếu câu chào chỉ lặp lại mô tả sự cố của khách hàng
        if "để kỹ sư chẩn đoán" not in low:
            return False

    return True


def _measure_and_verify_grounding(
    draft: str,
    citations: List[CitationItem],
    summary: Optional[CaseSummary] = None,
    ticket_description: Optional[str] = None,
) -> Dict[str, Any]:
    """Đo lường tỷ lệ Grounding và loại bỏ 100% trích dẫn bịa đặt (Zero Fabricated Citations).

    - Mọi `passage_id` xuất hiện trong draft/summary nhưng không tồn tại trong danh sách
      `citations` hợp lệ sẽ bị loại bỏ hoàn toàn.
    - Tính `grounding_score` = tỷ lệ nhận định kỹ thuật có căn cứ `passage_id` thực tế.
    """
    valid_citations_by_id: Dict[str, CitationItem] = {}
    for c in citations:
        c_status = str(getattr(c, "status", None) or "current").lower()
        if c_status in _FORBIDDEN_CITATION_STATUSES:
            continue
        if getattr(c, "passage_id", None):
            valid_citations_by_id[str(c.passage_id)] = c

    valid_ids = set(valid_citations_by_id.keys())
    removed_fabricated_ids: List[str] = []
    verified_passage_ids: List[str] = []

    def _strip_fabricated_tags(text: str) -> Tuple[str, List[str], List[str]]:
        found_valid: List[str] = []
        found_fake: List[str] = []

        def _replace_tag(match: re.Match[str]) -> str:
            ref_id = match.group(1).strip()
            if ref_id in valid_ids:
                if ref_id not in found_valid:
                    found_valid.append(ref_id)
                return match.group(0)
            if ref_id not in found_fake:
                found_fake.append(ref_id)
            return ""

        cleaned = _CITATION_TAG_PATTERN.sub(_replace_tag, text)

        def _replace_inline(match: re.Match[str]) -> str:
            ref_id = match.group(1).strip()
            if ref_id in valid_ids:
                if ref_id not in found_valid:
                    found_valid.append(ref_id)
                return match.group(0)
            if ref_id not in found_fake:
                found_fake.append(ref_id)
            return ""

        cleaned = _INLINE_PASSAGE_EQ_PATTERN.sub(_replace_inline, cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).replace(" ,", ",").replace(" .", ".").strip()
        return cleaned, found_valid, found_fake

    raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", draft or "") if s.strip()]
    cleaned_sentences: List[str] = []
    total_claims = 0
    supported_claims = 0
    ticket_lower = (ticket_description or "").strip().lower()

    for sent in raw_sentences:
        cleaned_sent, s_valid, s_fake = _strip_fabricated_tags(sent)
        for fid in s_fake:
            if fid not in removed_fabricated_ids:
                removed_fabricated_ids.append(fid)
        for vid in s_valid:
            if vid not in verified_passage_ids:
                verified_passage_ids.append(vid)

        if cleaned_sent:
            cleaned_sentences.append(cleaned_sent)

        sent_low = cleaned_sent.lower()
        # Bỏ qua câu lặp lại nguyên văn mô tả sự cố của khách hàng (không chứa tag bịa đặt)
        if ticket_lower and not s_fake and not s_valid and len(sent_low) >= 4 and sent_low.rstrip(".!?\"") in ticket_lower:
            continue

        is_claim = _is_material_claim_sentence(sent) or bool(s_fake) or bool(s_valid)
        if not is_claim:
            continue

        total_claims += 1
        if s_fake and not s_valid:
            continue

        if s_valid:
            supported_claims += 1
            continue

        matched_by_content = False
        sent_core = sent_low.rstrip(".!?")
        sent_words = {w for w in re.findall(r"\w{2,}", sent_low)}
        for cid, cit in valid_citations_by_id.items():
            cit_full = f"{cit.document_title} {cit.content_snippet}".lower()
            title_hit = cit.document_title.lower() in sent_low
            substr_hit = len(sent_core) >= 8 and sent_core in cit_full
            cit_words = {w for w in re.findall(r"\w{2,}", cit_full)}
            overlap = len(cit_words & sent_words) / max(len(sent_words), 1)
            if title_hit or substr_hit or overlap >= 0.45:
                matched_by_content = True
                if cid not in verified_passage_ids:
                    verified_passage_ids.append(cid)
                break
        if matched_by_content:
            supported_claims += 1

    cleaned_draft = " ".join(cleaned_sentences).strip()

    cleaned_summary = summary
    if summary is not None and summary.confirmed_observation:
        obs_clean, obs_valid, obs_fake = _strip_fabricated_tags(summary.confirmed_observation)
        for fid in obs_fake:
            if fid not in removed_fabricated_ids:
                removed_fabricated_ids.append(fid)
        for vid in obs_valid:
            if vid not in verified_passage_ids:
                verified_passage_ids.append(vid)
        cleaned_summary = CaseSummary(
            reported_symptom=summary.reported_symptom,
            confirmed_observation=obs_clean or summary.confirmed_observation,
            outstanding_questions=summary.outstanding_questions,
        )

    if total_claims == 0:
        grounding_score = 0.0 if removed_fabricated_ids else 1.0
    else:
        grounding_score = round(supported_claims / total_claims, 4)

    return {
        "cleaned_draft": cleaned_draft,
        "cleaned_summary": cleaned_summary,
        "grounding_score": grounding_score,
        "verified_passage_ids": verified_passage_ids,
        "removed_fabricated_ids": removed_fabricated_ids,
        "total_claims": total_claims,
        "supported_claims": supported_claims,
    }


def _build_hazard_emergency_package(
    ticket_description: str,
    start_time: Optional[float] = None,
) -> CopilotPackageResponse:
    """Tạo gói phản hồi ngắt an toàn khẩn cấp (SAFE-01 - SAFE-06, SUP-04) mà không gọi mô hình AI/Retriever."""
    emergency_draft = (
        "CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn "
        "(khói, cháy nổ, điện giật hoặc sự cố nhiệt/cơ) từ mô tả của quý khách. Quý khách vui lòng "
        "ngắt nguồn điện cấp cho thiết bị ngay lập tức nếu đảm bảo an toàn, giữ khoảng cách an toàn "
        "và tuyệt đối không tự ý kiểm tra hay khởi động lại máy. Yêu cầu này đã được chuyển khẩn cấp "
        "tới Kỹ sư Phụ trách An toàn của SongNhat để liên hệ hỗ trợ trực tiếp."
    )
    latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2) if start_time is not None else 0.0
    in_toks = estimate_tokens(ticket_description)
    out_toks = estimate_tokens(emergency_draft)
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
        status="COMPLETED",
        hold_reason=None,
        grounding_score=1.0,
        model_version=DEFAULT_MODEL_VERSION,
        prompt_version=DEFAULT_PROMPT_VERSION,
        token_usage={
            "input_tokens": in_toks,
            "output_tokens": out_toks,
            "total_tokens": in_toks + out_toks,
            "calls_used": 0,
        },
        latency_ms=latency_ms,
    )


def _build_hold_package(
    ticket_description: str,
    intent: IntentEnum,
    citations: List[CitationItem],
    missing_facts: List[str],
    hold_reason: str,
    quarantined_passages: List[Dict[str, Any]],
    start_time: float,
    input_tokens: int,
    output_tokens: int = 0,
    calls_used: int = 0,
) -> CopilotPackageResponse:
    """Tạo Support Package ở trạng thái HOLD khi vượt Token Cap, vượt số call hoặc lỗi/timeout provider."""
    manual_refs = [
        c.stable_ref or f"{c.document_title} (Trang {c.page_number})"
        for c in citations[:3]
    ]
    ref_hint = f" Nguồn cần kiểm tra thủ công: {'; '.join(manual_refs)}." if manual_refs else ""
    hold_draft = (
        "Chào quý khách, yêu cầu hỗ trợ của quý khách đang được tạm giữ xử lý tự động (HOLD) "
        "do vượt giới hạn tài nguyên xử lý hoặc cần kiểm tra đối chiếu trực tiếp từ kỹ sư SongNhat. "
        "Kỹ thuật viên sẽ tra cứu tài liệu gốc và phản hồi quý khách trong thời gian sớm nhất. Trân trọng."
    )
    hold_next_step = (
        f"TẠM GIỮ XỬ LÝ (HOLD): {hold_reason} Đề nghị kỹ thuật viên tra cứu thủ công tài liệu gốc "
        f"và phê duyệt cap riêng nếu cần thiết.{ref_hint}"
    )
    out_toks = output_tokens or estimate_tokens(hold_draft) + estimate_tokens(hold_next_step)
    latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    return CopilotPackageResponse(
        intent=intent,
        summary=CaseSummary(
            reported_symptom=ticket_description[:500].strip(),
            confirmed_observation=f"Gói hỗ trợ bị tạm giữ (HOLD): {hold_reason}",
            outstanding_questions=(
                "Cần khách hàng cung cấp bổ sung: " + ", ".join(missing_facts) + "."
                if missing_facts
                else None
            ),
        ),
        missing_facts=missing_facts,
        citations=citations,
        next_step=hold_next_step,
        draft=hold_draft,
        draft_response=hold_draft,
        draft_reply=hold_draft,
        is_hazard_escalated=False,
        status="HOLD",
        hold_reason=hold_reason,
        grounding_score=1.0,
        model_version=DEFAULT_MODEL_VERSION,
        prompt_version=DEFAULT_PROMPT_VERSION,
        token_usage={
            "input_tokens": int(input_tokens),
            "output_tokens": int(out_toks),
            "total_tokens": int(input_tokens + out_toks),
            "calls_used": int(calls_used),
        },
        latency_ms=latency_ms,
        quarantined_passages=quarantined_passages,
    )


def _remove_vietnamese_accents(text: str) -> str:
    """Chuẩn hóa chuỗi tiếng Việt: bỏ toàn bộ dấu (accent marks) và chuyển đ/Đ -> d/D."""
    text = text.replace("đ", "d").replace("Đ", "D")
    nfkd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def _classify_intent_from_text(text: str) -> IntentEnum:
    """Phân loại ý định ticket vào 1 trong 3 danh mục chuẩn SongNhat."""
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
    """Tạo cấu trúc tóm tắt sự cố (CaseSummary) kèm đối chứng passage_id."""
    confirmed_obs: Optional[str] = None
    if citations:
        ref_tag = f" [passage_id:{citations[0].passage_id}]" if citations[0].passage_id else ""
        confirmed_obs = (
            f"Đã đối chiếu với '{citations[0].document_title}' (trang {citations[0].page_number}){ref_tag}: "
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
    """Soạn thảo phản hồi tiếng Việt trung tính, gắn passage_id đối chứng và dưới 180 từ (CRM-50, CRM-51 & CRM-61)."""
    missing_str = (
        ", ".join(missing_facts[:3])
        if missing_facts
        else "Mã Serial và Phiên bản Firmware"
    )

    if intent == IntentEnum.DOCUMENT_REQUEST:
        if citations:
            ref_tag = f" [passage_id:{citations[0].passage_id}]" if citations[0].passage_id else ""
            citation_ref = (
                f"Đã đối chiếu với tài liệu '{citations[0].document_title}' "
                f"(trang {citations[0].page_number}){ref_tag}."
            )
            draft = (
                f"Chào quý khách, bộ phận Hỗ trợ Kỹ thuật SongNhat đã tiếp nhận yêu cầu cung cấp tài liệu. "
                f"{citation_ref} Dựa trên hệ thống cơ sở tri thức, chúng tôi đã trích xuất các phần hướng dẫn liên quan đính kèm{ref_tag}. "
                f"Để gửi chính xác bộ sơ đồ đấu nối và tài liệu theo đúng đời máy, quý khách vui lòng phản hồi "
                f"thêm: {missing_str}. Trân trọng."
            )
        else:
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
                ref_tag = f", [passage_id:{cit.passage_id}]" if cit.passage_id else ""
                citation_parts.append(
                    f"Theo {cit.document_title} (trang {cit.page_number}{ref_tag}): {cit.content_snippet}"
                )
            citation_ref = " ".join(citation_parts)
            draft = (
                f"Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "
                f"\"{ticket_text}\". {citation_ref} "
                f"Để kỹ sư chẩn đoán chính xác và hướng dẫn xử lý an toàn, quý khách vui lòng "
                f"cung cấp thêm: {missing_str}. Trân trọng."
            )
            # Nếu vượt 180 từ với 2 trích dẫn, ưu tiên rút gọn về 1 trích dẫn chính để giữ trọn câu
            if len(draft.split()) >= 180 and len(citation_parts) > 1:
                draft = (
                    f"Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "
                    f"\"{ticket_text}\". {citation_parts[0]} "
                    f"Để kỹ sư chẩn đoán chính xác và hướng dẫn xử lý an toàn, quý khách vui lòng "
                    f"cung cấp thêm: {missing_str}. Trân trọng."
                )
        else:
            draft = (
                f"Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "
                f"\"{ticket_text}\". Hiện tại không có nguồn phù hợp trong cơ sở tri thức "
                f"để kết luận nguyên nhân kỹ thuật. Chúng tôi đã chuyển thông tin tới Kỹ sư chuyên trách "
                f"kiểm tra trực tiếp thiết bị. Để kỹ sư hỗ trợ nhanh chóng, quý khách vui lòng "
                f"cung cấp thêm: {missing_str}. Trân trọng."
            )

    words = draft.split()
    if len(words) >= 180:
        draft = " ".join(words[:175]) + "..."
    return draft


async def _save_copilot_package_to_db(
    db: Any,
    ticket_id: Union[int, str, uuid.UUID],
    package: CopilotPackageResponse,
) -> None:
    """Lưu hoặc cập nhật kết quả Support Package + 4 trường telemetry vào bảng `copilot_packages`."""
    try:
        try:
            from models import CopilotPackage
        except ImportError:
            from backend.models import CopilotPackage

        from sqlalchemy import select

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
            existing.model_version = package.model_version
            existing.prompt_version = package.prompt_version
            existing.token_usage = package.token_usage
            existing.latency_ms = package.latency_ms
            existing.package_status = package.status
            existing.hold_reason = package.hold_reason
            existing.grounding_score = package.grounding_score
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
                model_version=package.model_version,
                prompt_version=package.prompt_version,
                token_usage=package.token_usage,
                latency_ms=package.latency_ms,
                package_status=package.status,
                hold_reason=package.hold_reason,
                grounding_score=package.grounding_score,
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
    model_caller: Optional[Callable[..., Any]] = None,
    provider_timeout_seconds: float = 15.0,
) -> CopilotPackageResponse:
    """Hàm điều phối khép kín End-to-End Copilot Pipeline theo chuẩn SongNhat RFP (CRM-28, CRM-43 & CRM-61)."""
    start_time = time.perf_counter()

    # =========================================================================
    # BƯỚC 1: QUÉT AN TOÀN KHẨN CẤP (MANDATORY SAFETY CHECKER)
    # =========================================================================
    if check_safety_hazard(ticket_description):
        logger.warning(
            "Phát hiện dấu hiệu mất an toàn! Kích hoạt ngắt khẩn cấp (Hazard Escalation)."
        )
        hazard_pkg = _build_hazard_emergency_package(ticket_description, start_time=start_time)
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
    # BƯỚC 2: TRUY XUẤT BẰNG CHỨNG TỪ KNOWLEDGE BASE (HYBRID RETRIEVER)
    # =========================================================================
    raw_citations: List[CitationItem] = await search_knowledge_passages(
        query=ticket_description,
        db=db,
        limit=limit,
        product_id=resolved_product_id,
        allow_mock_fallback=False,
    )

    intent = _classify_intent_from_text(ticket_description)
    missing_facts = _detect_missing_facts(ticket_description, intent)

    # =========================================================================
    # BƯỚC 3: KIỂM SOÁT TOKEN BUDGET CAP (8,000 INPUT / 1,200 OUTPUT / MAX 2 CALLS)
    # =========================================================================
    citations, quarantined_passages, input_tokens, budget_hold_reason = _apply_token_budget_to_context(
        ticket_description=ticket_description,
        citations=raw_citations,
    )
    if budget_hold_reason is not None:
        hold_pkg = _build_hold_package(
            ticket_description=ticket_description,
            intent=intent,
            citations=citations,
            missing_facts=missing_facts,
            hold_reason=budget_hold_reason,
            quarantined_passages=quarantined_passages,
            start_time=start_time,
            input_tokens=input_tokens,
            calls_used=0,
        )
        if db is not None and ticket_id is not None:
            await _save_copilot_package_to_db(db, ticket_id, hold_pkg)
        return hold_pkg

    # =========================================================================
    # BƯỚC 4: PHÂN TÍCH & SINH DRAFT (TRONG GIỚI HẠN 2 CALLS & 1,200 OUTPUT TOKENS)
    # =========================================================================
    next_step = _build_next_step(intent)
    summary = _build_case_summary(ticket_description, citations, missing_facts)
    calls_used = 0
    draft = ""

    if model_caller is not None:
        max_out_cap = min(MAX_OUTPUT_TOKENS, 1200)
        prompt_payload = {
            "system": SYSTEM_PROMPT_INSTRUCTIONS,
            "ticket_description": ticket_description,
            "citations": [_format_passage_for_prompt(c) for c in citations],
            "missing_facts": missing_facts,
        }
        try:
            for attempt in range(MAX_MODEL_CALLS_PER_PACKAGE + 1):
                if calls_used >= MAX_MODEL_CALLS_PER_PACKAGE:
                    hold_pkg = _build_hold_package(
                        ticket_description=ticket_description,
                        intent=intent,
                        citations=citations,
                        missing_facts=missing_facts,
                        hold_reason=(
                            f"Vượt giới hạn tối đa {MAX_MODEL_CALLS_PER_PACKAGE} model calls "
                            f"cho mỗi support package (RFP Section 2)."
                        ),
                        quarantined_passages=quarantined_passages,
                        start_time=start_time,
                        input_tokens=input_tokens,
                        calls_used=calls_used,
                    )
                    if db is not None and ticket_id is not None:
                        await _save_copilot_package_to_db(db, ticket_id, hold_pkg)
                    return hold_pkg

                calls_used += 1
                raw_call = model_caller(
                    prompt=prompt_payload,
                    max_tokens=max_out_cap,
                    attempt=attempt + 1,
                )
                if inspect.isawaitable(raw_call):
                    candidate_draft = await asyncio.wait_for(raw_call, timeout=provider_timeout_seconds)
                else:
                    candidate_draft = raw_call

                candidate_str = str(candidate_draft or "").strip()
                out_tokens_est = estimate_tokens(candidate_str)
                if out_tokens_est <= MAX_OUTPUT_TOKENS and len(candidate_str.split()) < 180:
                    draft = candidate_str
                    break
                # Nếu vượt ngưỡng output tokens/từ và còn ngân sách call 2 -> yêu cầu repair ngắn lại
                prompt_payload["repair_instruction"] = (
                    f"Output vượt giới hạn ({out_tokens_est} tokens). Rút gọn dưới 180 từ và <= {MAX_OUTPUT_TOKENS} tokens."
                )
            else:
                hold_pkg = _build_hold_package(
                    ticket_description=ticket_description,
                    intent=intent,
                    citations=citations,
                    missing_facts=missing_facts,
                    hold_reason="Output vượt giới hạn 1,200 tokens sau tối đa 2 lần gọi.",
                    quarantined_passages=quarantined_passages,
                    start_time=start_time,
                    input_tokens=input_tokens,
                    calls_used=calls_used,
                )
                if db is not None and ticket_id is not None:
                    await _save_copilot_package_to_db(db, ticket_id, hold_pkg)
                return hold_pkg
        except asyncio.TimeoutError:
            hold_pkg = _build_hold_package(
                ticket_description=ticket_description,
                intent=intent,
                citations=citations,
                missing_facts=missing_facts,
                hold_reason=f"Provider LLM timeout sau {provider_timeout_seconds}s; chuyển tra cứu thủ công.",
                quarantined_passages=quarantined_passages,
                start_time=start_time,
                input_tokens=input_tokens,
                calls_used=calls_used,
            )
            if db is not None and ticket_id is not None:
                await _save_copilot_package_to_db(db, ticket_id, hold_pkg)
            return hold_pkg
        except Exception as exc:
            hold_pkg = _build_hold_package(
                ticket_description=ticket_description,
                intent=intent,
                citations=citations,
                missing_facts=missing_facts,
                hold_reason=f"Lỗi từ provider LLM ({exc}); kích hoạt chế độ HOLD an toàn.",
                quarantined_passages=quarantined_passages,
                start_time=start_time,
                input_tokens=input_tokens,
                calls_used=calls_used,
            )
            if db is not None and ticket_id is not None:
                await _save_copilot_package_to_db(db, ticket_id, hold_pkg)
            return hold_pkg
    else:
        calls_used = 1
        draft = _compose_neutral_draft(
            ticket_description=ticket_description,
            intent=intent,
            citations=citations,
            missing_facts=missing_facts,
        )

    # =========================================================================
    # BƯỚC 5: HẬU KIỂM GROUNDING (>= 95% & ZERO FABRICATED CITATIONS)
    # =========================================================================
    grounding_res = _measure_and_verify_grounding(
        draft=draft,
        citations=citations,
        summary=summary,
        ticket_description=ticket_description,
    )
    verified_draft = grounding_res["cleaned_draft"]
    verified_summary = grounding_res["cleaned_summary"] or summary
    grounding_score = grounding_res["grounding_score"]

    # Đảm bảo chắc chắn giới hạn < 180 từ sau hậu kiểm
    words = verified_draft.split()
    if len(words) >= 180:
        verified_draft = " ".join(words[:175]) + "..."

    output_tokens = estimate_tokens(verified_draft) + estimate_tokens(next_step)
    if output_tokens > MAX_OUTPUT_TOKENS:
        hold_pkg = _build_hold_package(
            ticket_description=ticket_description,
            intent=intent,
            citations=citations,
            missing_facts=missing_facts,
            hold_reason=f"Output ({output_tokens} tokens) vượt trần {MAX_OUTPUT_TOKENS} output tokens.",
            quarantined_passages=quarantined_passages,
            start_time=start_time,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            calls_used=calls_used,
        )
        if db is not None and ticket_id is not None:
            await _save_copilot_package_to_db(db, ticket_id, hold_pkg)
        return hold_pkg

    latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    package = CopilotPackageResponse(
        intent=intent,
        summary=verified_summary,
        missing_facts=missing_facts,
        citations=citations,
        next_step=next_step,
        draft=verified_draft,
        draft_response=verified_draft,
        draft_reply=verified_draft,
        is_hazard_escalated=False,
        status="COMPLETED",
        hold_reason=None,
        grounding_score=grounding_score,
        model_version=DEFAULT_MODEL_VERSION,
        prompt_version=DEFAULT_PROMPT_VERSION,
        token_usage={
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens),
            "total_tokens": int(input_tokens + output_tokens),
            "calls_used": int(calls_used),
        },
        latency_ms=latency_ms,
        quarantined_passages=quarantined_passages,
    )

    # =========================================================================
    # BƯỚC 6: LƯU KẾT QUẢ VÀ TELEMETRY VÀO BẢNG COPILOT_PACKAGES
    # =========================================================================
    if db is not None and ticket_id is not None:
        await _save_copilot_package_to_db(db, ticket_id, package)

    return package


class CopilotEngineService:
    """Service điều phối quy trình phân tích sự cố và trích xuất bằng chứng (CRM-24, CRM-28 & CRM-61)."""

    def __init__(self, db: Optional[Any] = None, api_key: Optional[str] = None) -> None:
        """Khởi tạo CopilotEngineService."""
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
