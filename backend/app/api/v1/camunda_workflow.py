"""FastAPI router for Camunda 7 BPMN Ticket Triage integration (CRM-44).

Wraps `run_copilot_pipeline()` without modifying other team members' files and
exposes:
  - `POST /api/copilot/analyze`
  - `GET  /api/copilot/process/{ticket_id}/status`
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

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

