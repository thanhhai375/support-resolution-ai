"""FastAPI router for Camunda 7 BPMN Ticket Triage integration (CRM-44).

Wraps `run_copilot_pipeline()` without modifying other team members' files and
exposes:
  - `POST /api/copilot/analyze`
  - `GET  /api/copilot/process/{ticket_id}/status`
"""
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.camunda.worker import get_process_status, start_ticket_triage_process
from app.services.copilot_engine import run_copilot_pipeline

router = APIRouter(prefix="/api/copilot", tags=["Camunda BPMN & Copilot Workflow"])


class CamundaAnalyzeRequest(BaseModel):
    ticket_description: str = Field(..., min_length=1)
    ticket_id: Optional[str] = Field(default=None)


@router.post("/analyze")
async def analyze_with_camunda_workflow(payload: CamundaAnalyzeRequest) -> dict[str, Any]:
    """Run Copilot analysis and start a Camunda BPMN process instance when `CAMUNDA_URL` is set."""
    package = await run_copilot_pipeline(
        ticket_description=payload.ticket_description,
        ticket_id=payload.ticket_id,
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
