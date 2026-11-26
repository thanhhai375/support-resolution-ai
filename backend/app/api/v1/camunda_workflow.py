"""FastAPI router for Camunda 7 BPMN Ticket Triage integration (CRM-44).

Wraps `run_copilot_pipeline()` without modifying other team members' files and
exposes:
  - `POST /api/copilot/analyze`
  - `GET  /api/copilot/process/{ticket_id}/status`
"""
import asyncio
import logging
import uuid
import io
import re
from xml.sax.saxutils import escape
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.main import get_db  # imported lazily by app.main.register_backend_components()

from app.camunda.worker import (
    ProcessAlreadyReviewedError,
    complete_human_approval,
    get_process_status,
    start_ticket_triage_process,
)
from app.services.copilot_engine import run_copilot_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/copilot", tags=["Camunda BPMN & Copilot Workflow"])


class CamundaAnalyzeRequest(BaseModel):
    ticket_description: str = Field(..., min_length=1)
    ticket_id: Optional[str] = Field(default=None)


@router.post("/analyze")
async def analyze_with_camunda_workflow(
    payload: CamundaAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Run Copilot analysis and start a Camunda BPMN process instance when `CAMUNDA_URL` is set.

    This is the single `POST /api/copilot/analyze` handler: it uses the shared DB session
    (real retriever + saved `copilot_packages`) exactly like the legacy copilot router.
    """
    package = await run_copilot_pipeline(
        ticket_description=payload.ticket_description,
        ticket_id=payload.ticket_id,
        db=db,
    )
    result = package.model_dump(mode="json")

    effective_ticket_id = str(payload.ticket_id) if payload.ticket_id else "latest"
    proc = await start_ticket_triage_process(
        ticket_id=effective_ticket_id,
        ticket_description=payload.ticket_description,
        intent=result["intent"],
        is_hazard_escalated=bool(result.get("is_hazard_escalated", False)),
    )
    if proc is not None:
        result["process_instance_id"] = proc.get("process_instance_id")
        result["camunda_topic"] = proc.get("routed_topic")
    else:
        result["process_instance_id"] = None
        result["camunda_topic"] = None

    return result


@router.get("/process/{ticket_id}/status")
async def get_copilot_process_status(ticket_id: str) -> dict[str, Any]:
    """Return the Camunda BPMN process status for `ticket_id` (CRM-44)."""
    record = await get_process_status(ticket_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Camunda BPMN process instance found for ticket '{ticket_id}'",
        )
    return record


# --- Approval API (requested by CRM-41, implemented under CRM-44) -------------------------
approval_router = APIRouter(prefix="/api/v1/copilot", tags=["Copilot Approval"])


class ApproveRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    approved_by: str = Field(
        ..., min_length=1, validation_alias=AliasChoices("approved_by", "approvedBy", "approver_id", "approverId")
    )


class RejectRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    rejection_reason: str = Field(
        ..., min_length=1, validation_alias=AliasChoices("rejection_reason", "rejectionReason", "reason")
    )
    rejected_by: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("rejected_by", "rejectedBy", "reviewer")
    )


def _to_uuid(ticket_id: str) -> uuid.UUID:
    """Same ticket-id -> UUID mapping used by `copilot_engine` when saving packages."""
    try:
        return uuid.UUID(str(ticket_id))
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(ticket_id))


DB_PERSIST_TIMEOUT_SECONDS = 5.0


async def _persist_decision(
    ticket_id: str, *, approved: bool, reviewer: str, reason: Optional[str]
) -> bool:
    """Best-effort DB update; never blocks the API longer than DB_PERSIST_TIMEOUT_SECONDS."""
    try:
        return await asyncio.wait_for(
            _persist_decision_inner(ticket_id, approved=approved, reviewer=reviewer, reason=reason),
            timeout=DB_PERSIST_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning("Persisting approval decision for %s timed out (DB unreachable?)", ticket_id)
        return False


async def _persist_decision_inner(
    ticket_id: str, *, approved: bool, reviewer: str, reason: Optional[str]
) -> bool:
    """Best-effort DB update of `copilot_packages` (+ ticket status). Returns True if saved."""
    try:
        import app.main as app_main
        from models import CopilotPackage, Ticket
        from sqlalchemy.future import select

        await app_main.ensure_db_initialized()
        AsyncSessionLocal = app_main.AsyncSessionLocal
        pkg_id = _to_uuid(ticket_id)
        async with AsyncSessionLocal() as db:
            pkg = (
                await db.execute(select(CopilotPackage).where(CopilotPackage.ticket_id == pkg_id))
            ).scalars().first()
            if pkg is None:
                return False
            pkg.approval_status = "APPROVED" if approved else "REJECTED"
            pkg.reviewed_by = reviewer
            pkg.reviewed_at = datetime.now(timezone.utc)
            pkg.review_note = None if approved else reason
            ticket = (await db.execute(select(Ticket).where(Ticket.id == pkg_id))).scalars().first()
            if ticket is not None:
                ticket.status = "RESOLVED" if approved else "IN_PROGRESS"
                ticket.updated_at = datetime.now(timezone.utc)
            await db.commit()
            return True
    except Exception as exc:  # DB not available (e.g. CRM-44 standalone run)
        logger.warning("Could not persist approval decision for %s: %s", ticket_id, exc)
        return False


async def _review(
    ticket_id: str, *, approved: bool, reviewer: str, reason: Optional[str]
) -> dict[str, Any]:
    try:
        process = await complete_human_approval(
            ticket_id, approved=approved, reviewer=reviewer, reason=reason
        )
    except ProcessAlreadyReviewedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    persisted = await _persist_decision(ticket_id, approved=approved, reviewer=reviewer, reason=reason)
    decision = "APPROVED" if approved else "REJECTED"
    body: dict[str, Any] = {
        "ticket_id": ticket_id,
        "approval_status": decision,
        "persisted": persisted,
        "process_status": process["status"] if process else None,
        "process_instance_id": process.get("process_instance_id") if process else None,
    }
    if approved:
        body["approved_by"] = reviewer
    else:
        body["rejected_by"] = reviewer
        body["rejection_reason"] = reason
    return body


@approval_router.patch("/{ticket_id}/approve")
async def approve_copilot_draft(ticket_id: str, payload: ApproveRequest) -> dict[str, Any]:
    """APPROVED + `approved_by`; completes the Camunda `Task_HumanApproval` user task."""
    return await _review(ticket_id, approved=True, reviewer=payload.approved_by, reason=None)


@approval_router.patch("/{ticket_id}/reject")
async def reject_copilot_draft(ticket_id: str, payload: RejectRequest) -> dict[str, Any]:
    """REJECTED + `rejection_reason`; ends the Camunda process as rejected."""
    return await _review(
        ticket_id,
        approved=False,
        reviewer=payload.rejected_by or "unknown",
        reason=payload.rejection_reason,
    )



# --- Official customer response export (CRM-60) ---------------------------------------
from app.api.deps import get_current_user, require_role
from models import CopilotPackage, Ticket
from app.repositories import user_repository

_export_user = require_role("support_agent", "technical_approver", "administrator")


def _public_text(value: Any) -> str:
    """Remove internal identifiers and control characters before customer export."""
    text_value = str(value or "")
    text_value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[đã ẩn]", text_value)
    text_value = re.sub(r"(?im)^.*(?:system\s*prompt|internal\s*notes?|ghi chú nội bộ|prompt hệ thống).*$", "[đã ẩn]", text_value)
    text_value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text_value)
    return text_value.strip()


def _citation_public_fields(citation: Any) -> dict[str, str]:
    """Whitelist customer-safe evidence fields; never serialize arbitrary metadata."""
    if not isinstance(citation, dict):
        return {}
    aliases = {
        "document": ("document_name", "document_title", "title"),
        "document_code": ("document_code", "code"),
        "section": ("section", "section_name", "section_number"),
        "version": ("version",),
        "status": ("status",),
        "page": ("page_number", "page"),
        "evidence": ("excerpt", "snippet", "content_snippet", "passage_content", "content"),
        "url": ("url", "source_url"),
    }
    result: dict[str, str] = {}
    for output_key, keys in aliases.items():
        for key in keys:
            value = citation.get(key)
            if value not in (None, ""):
                if output_key == "url" and not str(value).lower().startswith(("https://", "http://")):
                    continue
                result[output_key] = _public_text(value)
                break
    return result


def _build_customer_pdf(ticket: Ticket, package: CopilotPackage, engineer_name: str) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise HTTPException(status_code=503, detail="PDF export dependency is not installed") from exc

    # Register a Unicode font when available so Vietnamese text renders correctly.
    font_name = "Helvetica"
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for font_path in font_candidates:
        try:
            pdfmetrics.registerFont(TTFont("SongNhatUnicode", font_path))
            font_name = "SongNhatUnicode"
            break
        except Exception:
            continue

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=18*mm, bottomMargin=18*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SNBody", parent=styles["BodyText"], fontName=font_name, fontSize=9, leading=14, alignment=TA_LEFT, spaceAfter=5))
    styles.add(ParagraphStyle(name="SNTitle", parent=styles["Title"], fontName=font_name, fontSize=17, leading=22, textColor=colors.HexColor("#17365D")))
    styles.add(ParagraphStyle(name="SNHeading", parent=styles["Heading2"], fontName=font_name, fontSize=11, leading=15, textColor=colors.HexColor("#17365D"), spaceBefore=9))
    story = [Paragraph("SONGNHAT", styles["SNTitle"]), Paragraph("PHẢN HỒI HỖ TRỢ KỸ THUẬT CHÍNH THỨC", styles["SNHeading"]), Spacer(1, 5*mm)]
    ticket_number = _public_text(getattr(ticket, "ticket_number", "")) or str(ticket.id)
    story.append(Paragraph(f"<b>Mã Ticket:</b> {escape(ticket_number)}", styles["SNBody"]))
    story.append(Paragraph("<b>Tiêu đề:</b> " + escape(_public_text(ticket.subject)), styles["SNBody"]))
    story.append(Paragraph("<b>Nội dung hướng dẫn kỹ thuật</b>", styles["SNHeading"]))
    response_text = _public_text(package.draft_response or package.draft)
    if not response_text:
        raise HTTPException(status_code=409, detail="Approved customer response is empty")
    for paragraph in response_text.splitlines() or [response_text]:
        if paragraph.strip():
            story.append(Paragraph(escape(paragraph), styles["SNBody"]))

    story.append(Paragraph("Trích dẫn chứng cứ công khai", styles["SNHeading"]))
    citations = package.citations if isinstance(package.citations, list) else []
    safe_citations = [_citation_public_fields(item) for item in citations]
    safe_citations = [item for item in safe_citations if item]
    if safe_citations:
        for index, item in enumerate(safe_citations, 1):
            bits = []
            for label in ("document", "document_code", "section", "page", "version", "status", "evidence", "url"):
                if item.get(label):
                    bits.append(f"{label}: {item[label]}")
            story.append(Paragraph(escape(f"{index}. " + " | ".join(bits)), styles["SNBody"]))
    else:
        story.append(Paragraph("Không có trích dẫn chứng cứ công khai được lưu cho phản hồi này.", styles["SNBody"]))

    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("<b>Kỹ sư phê duyệt:</b> " + escape(_public_text(engineer_name)), styles["SNBody"]))
    story.append(Paragraph("Tài liệu được tạo tự động từ phản hồi đã được phê duyệt trên hệ thống SongNhat.", styles["SNBody"]))
    doc.build(story)
    return buffer.getvalue()


@approval_router.get("/{ticket_id}/export")
async def export_approved_response(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(_export_user),
) -> StreamingResponse:
    """Export the approved customer-facing response as a sanitized PDF (CRM-60)."""
    try:
        parsed_id = uuid.UUID(ticket_id)
    except ValueError:
        parsed_id = _to_uuid(ticket_id)

    ticket = (await db.execute(select(Ticket).where(Ticket.id == parsed_id))).scalars().first()
    package = (await db.execute(select(CopilotPackage).where(CopilotPackage.ticket_id == parsed_id))).scalars().first()
    if ticket is None or package is None:
        raise HTTPException(status_code=404, detail="Ticket or Copilot response not found")
    if str(package.approval_status).upper() != "APPROVED":
        raise HTTPException(status_code=409, detail="Only approved responses can be exported")
    if not package.reviewed_by:
        raise HTTPException(status_code=409, detail="Approval reviewer is missing")

    reviewer = user_repository.get_user_by_email(package.reviewed_by)
    reviewer_role = (reviewer or {}).get("role", "")
    if reviewer_role not in {"technical_approver", "ENGINEER", "engineer"}:
        raise HTTPException(status_code=403, detail="Response must be approved by an ENGINEER")
    engineer_name = (reviewer or {}).get("full_name") or "Kỹ sư phê duyệt"
    pdf_bytes = _build_customer_pdf(ticket, package, engineer_name)
    filename = f"SongNhat_Response_{_public_text(ticket.ticket_number or str(ticket.id))}.pdf"
    safe_filename = re.sub(r"[^A-Za-z0-9_.-]", "_", filename)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"', "Cache-Control": "no-store"},
    )
