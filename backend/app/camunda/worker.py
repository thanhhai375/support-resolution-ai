"""Camunda 7 External Task Worker & REST Engine integration for Ticket Triage (CRM-44).

Subscribes to the 3 intent routing topics defined in `camunda/ticket-triage.bpmn`:
  - `triage.document_request`     (DOCUMENT_REQUEST)
  - `triage.service_progress`     (SERVICE_PROGRESS)
  - `triage.technical_escalation` (TECHNICAL_ESCALATION)

When `CAMUNDA_URL` is set, `start_ticket_triage_process()` starts a process
instance via the Camunda 7 REST API (with deterministic local BPMN execution
fallback when the Camunda container is unreachable) and routes the ticket
through the subscribed External Task Worker handler. When `CAMUNDA_URL` is not
set, the function returns `None` so `run_copilot_pipeline()` runs the legacy
in-process flow without side effects (100% backward compatible).
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

PROCESS_DEFINITION_KEY = "ticket-triage"

TOPIC_DOCUMENT_REQUEST = "triage.document_request"
TOPIC_SERVICE_PROGRESS = "triage.service_progress"
TOPIC_TECHNICAL_ESCALATION = "triage.technical_escalation"

SUBSCRIBED_TOPICS: List[str] = [
    TOPIC_DOCUMENT_REQUEST,
    TOPIC_SERVICE_PROGRESS,
    TOPIC_TECHNICAL_ESCALATION,
]

INTENT_TO_TOPIC: Dict[str, str] = {
    "DOCUMENT_REQUEST": TOPIC_DOCUMENT_REQUEST,
    "SERVICE_PROGRESS": TOPIC_SERVICE_PROGRESS,
    "TECHNICAL_ESCALATION": TOPIC_TECHNICAL_ESCALATION,
}

INTENT_TO_ACTIVITY: Dict[str, Dict[str, str]] = {
    "DOCUMENT_REQUEST": {
        "service_task_id": "Task_DocumentRequest",
        "service_task_name": "Xử lý Yêu cầu Tài liệu (Document Request)",
    },
    "SERVICE_PROGRESS": {
        "service_task_id": "Task_ServiceProgress",
        "service_task_name": "Xử lý Tra cứu Tiến độ (Service Progress)",
    },
    "TECHNICAL_ESCALATION": {
        "service_task_id": "Task_TechnicalEscalation",
        "service_task_name": "Xử lý Chuyển cấp Kỹ thuật (Technical Escalation)",
    },
}

_PROCESS_STORE: Dict[str, Dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_camunda_base_url(explicit_url: Optional[str] = None) -> Optional[str]:
    """Return normalized Camunda base URL if configured, otherwise None."""
    raw = explicit_url if explicit_url is not None else os.getenv("CAMUNDA_URL")
    if not raw or not raw.strip():
        return None
    url = raw.strip().rstrip("/")
    if url.endswith("/engine-rest"):
        return url
    return f"{url}/engine-rest"


class CamundaExternalTaskWorker:
    """Python External Task Worker subscribing to the 3 SongNhat triage topics."""

    def __init__(
        self,
        worker_id: str = "songnhat-copilot-worker",
        camunda_url: Optional[str] = None,
    ) -> None:
        self.worker_id = worker_id
        self.camunda_url = camunda_url
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
            TOPIC_DOCUMENT_REQUEST: self.handle_document_request,
            TOPIC_SERVICE_PROGRESS: self.handle_service_progress,
            TOPIC_TECHNICAL_ESCALATION: self.handle_technical_escalation,
        }

    @property
    def subscribed_topics(self) -> List[str]:
        return list(self._handlers.keys())

    def handle_document_request(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        """External task handler for `triage.document_request`."""
        return {
            "routed_topic": TOPIC_DOCUMENT_REQUEST,
            "triage_queue": "DOCUMENTATION_QUEUE",
            "requires_technical_approver": False,
            "routing_Action": "Attach approved manual citation and forward draft to staff review",
            "handled_by_worker": self.worker_id,
            "ticket_id": str(variables.get("ticket_id", "")),
        }

    def handle_service_progress(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        """External task handler for `triage.service_progress`."""
        return {
            "routed_topic": TOPIC_SERVICE_PROGRESS,
            "triage_queue": "SERVICE_STATUS_QUEUE",
            "requires_technical_approver": False,
            "routing_Action": "Verify latest service status record and forward draft to staff review",
            "handled_by_worker": self.worker_id,
            "ticket_id": str(variables.get("ticket_id", "")),
        }

    def handle_technical_escalation(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        """External task handler for `triage.technical_escalation`."""
        return {
            "routed_topic": TOPIC_TECHNICAL_ESCALATION,
            "triage_queue": "ENGINEERING_ESCALATION_QUEUE",
            "requires_technical_approver": True,
            "routing_Action": "Collect missing equipment identifiers and route to qualified engineer",
            "handled_by_worker": self.worker_id,
            "ticket_id": str(variables.get("ticket_id", "")),
        }

    def dispatch_topic(self, topic_name: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the registered handler for `topic_name`."""
        handler = self._handlers.get(topic_name)
        if handler is None:
            raise ValueError(
                f"Unsupported Camunda external task topic '{topic_name}'. "
                f"Subscribed topics: {self.subscribed_topics}"
            )
        return handler(variables)

    async def poll_and_execute_once(
        self,
        max_tasks: int = 5,
        lock_duration_ms: int = 10_000,
        client: Optional[httpx.AsyncClient] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch, lock, execute, and complete external tasks from Camunda REST API."""
        base_url = get_camunda_base_url(self.camunda_url)
        if not base_url:
            return []

        payload = {
            "workerId": self.worker_id,
            "maxTasks": max_tasks,
            "usePriority": True,
            "topics": [
                {"topicName": topic, "lockDuration": lock_duration_ms}
                for topic in self.subscribed_topics
            ],
        }

        close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=5.0)
            close_client = True

        completed: List[Dict[str, Any]] = []
        try:
            res = await client.post(f"{base_url}/external-task/fetchAndLock", json=payload)
            res.raise_for_status()
            tasks = res.json()
            for task in tasks:
                task_id = task["id"]
                topic_name = task["topicName"]
                raw_vars = task.get("variables") or {}
                flat_vars = {
                    k: (v.get("value") if isinstance(v, dict) else v)
                    for k, v in raw_vars.items()
                }
                result_vars = self.dispatch_topic(topic_name, flat_vars)
                camunda_vars = {
                    k: {
                        "value": v,
                        "type": "Boolean" if isinstance(v, bool) else "String",
                    }
                    for k, v in result_vars.items()
                }
                complete_res = await client.post(
                    f"{base_url}/external-task/{task_id}/complete",
                    json={"workerId": self.worker_id, "variables": camunda_vars},
                )
                complete_res.raise_for_status()
                completed.append(
                    {
                        "task_id": task_id,
                        "topic": topic_name,
                        "process_instance_id": task.get("processInstanceId"),
                        "result": result_vars,
                    }
                )
        finally:
            if close_client:
                await client.aclose()

        return completed


async def deploy_bpmn_to_camunda(
    bpmn_path: Optional[Path] = None,
    camunda_url: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Deploy `camunda/ticket-triage.bpmn` to Camunda 7 via REST API."""
    base_url = get_camunda_base_url(camunda_url)
    if not base_url:
        raise ValueError("CAMUNDA_URL is not configured")

    if bpmn_path is None:
        repo_root = Path(__file__).resolve().parents[3]
        bpmn_path = repo_root / "camunda" / "ticket-triage.bpmn"

    content = bpmn_path.read_bytes()
    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=10.0)
        close_client = True

    try:
        files = {
            "deployment-name": (None, "songnhat-ticket-triage"),
            "enable-duplicate-filtering": (None, "true"),
            "deploy-changed-only": (None, "true"),
            bpmn_path.name: (bpmn_path.name, content, "application/xml"),
        }
        res = await client.post(f"{base_url}/deployment/create", files=files)
        res.raise_for_status()
        return res.json()
    finally:
        if close_client:
            await client.aclose()


async def start_ticket_triage_process(
    *,
    ticket_id: str,
    ticket_description: str,
    intent: str,
    is_hazard_escalated: bool,
    camunda_url: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> Optional[Dict[str, Any]]:
    """Start a `ticket-triage` BPMN process instance when `CAMUNDA_URL` is configured.

    If `CAMUNDA_URL` is unset/empty, returns `None` immediately (backward-compatible
    fallback). When `CAMUNDA_URL` is set, starts the process on Camunda 7 REST API
    (or falls back to the embedded BPMN state machine if the container is unreachable)
    and executes the matching External Task Worker topic handler.
    """
    base_url = get_camunda_base_url(camunda_url)
    if not base_url:
        return None

    normalized_intent = str(getattr(intent, "value", intent))
    if normalized_intent not in INTENT_TO_TOPIC:
        normalized_intent = "TECHNICAL_ESCALATION"

    worker = CamundaExternalTaskWorker(camunda_url=base_url)

    camunda_variables = {
        "ticket_id": {"value": str(ticket_id), "type": "String"},
        "ticket_description": {"value": ticket_description, "type": "String"},
        "intent": {"value": normalized_intent, "type": "String"},
        "is_hazard_escalated": {"value": bool(is_hazard_escalated), "type": "Boolean"},
    }

    process_instance_id: Optional[str] = None
    engine_mode = "camunda_rest"

    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=3.0)
        close_client = True

    try:
        try:
            start_res = await client.post(
                f"{base_url}/process-definition/key/{PROCESS_DEFINITION_KEY}/start",
                json={
                    "businessKey": str(ticket_id),
                    "variables": camunda_variables,
                },
            )
            start_res.raise_for_status()
            body = start_res.json()
            process_instance_id = body.get("id")
            if not is_hazard_escalated:
                await worker.poll_and_execute_once(client=client)
        except Exception as exc:
            logger.info(
                "Camunda REST endpoint (%s) unreachable (%s); using local BPMN worker fallback.",
                base_url,
                exc,
            )
            engine_mode = "local_bpmn_fallback"
            process_instance_id = f"proc-{uuid.uuid4()}"
    finally:
        if close_client:
            await client.aclose()

    if is_hazard_escalated:
        routed_topic = None
        worker_output = {
            "triage_queue": "EMERGENCY_SAFETY_ESCALATION",
            "requires_technical_approver": True,
            "handled_by_worker": worker.worker_id,
        }
        current_activity_id = "Task_HazardEscalation"
        current_activity_name = "Chuyển khẩn cấp cho Kỹ sư An toàn (Escalate)"
        process_status = "ESCALATED_HAZARD"
    else:
        routed_topic = INTENT_TO_TOPIC[normalized_intent]
        worker_output = worker.dispatch_topic(
            routed_topic,
            {
                "ticket_id": str(ticket_id),
                "ticket_description": ticket_description,
                "intent": normalized_intent,
            },
        )
        current_activity_id = "Task_HumanApproval"
        current_activity_name = "Nhân viên kỹ thuật duyệt / chỉnh sửa bản nháp"
        process_status = "WAITING_HUMAN_APPROVAL"

    record: Dict[str, Any] = {
        "ticket_id": str(ticket_id),
        "process_definition_key": PROCESS_DEFINITION_KEY,
        "process_instance_id": process_instance_id,
        "business_key": str(ticket_id),
        "engine_mode": engine_mode,
        "camunda_url": base_url,
        "status": process_status,
        "is_hazard_escalated": bool(is_hazard_escalated),
        "intent": normalized_intent,
        "routed_topic": routed_topic,
        "service_task_id": (
            "Task_HazardEscalation"
            if is_hazard_escalated
            else INTENT_TO_ACTIVITY[normalized_intent]["service_task_id"]
        ),
        "current_activity_id": current_activity_id,
        "current_activity_name": current_activity_name,
        "worker_result": worker_output,
        "started_at": _now_iso(),
    }
    _PROCESS_STORE[str(ticket_id)] = record
    return record


async def get_process_status(
    ticket_id: str,
    camunda_url: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> Optional[Dict[str, Any]]:
    """Return the BPMN process status for `ticket_id`, querying Camunda REST if available."""
    key = str(ticket_id)
    record = _PROCESS_STORE.get(key)

    base_url = get_camunda_base_url(camunda_url)
    if base_url and record and record.get("engine_mode") == "camunda_rest":
        proc_id = record.get("process_instance_id")
        close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=3.0)
            close_client = True
        try:
            res = await client.get(f"{base_url}/process-instance/{proc_id}")
            if res.status_code == 200:
                info = res.json()
                record["ended"] = bool(info.get("ended", False))
                record["suspended"] = bool(info.get("suspended", False))
            elif res.status_code == 404:
                record["status"] = "COMPLETED"
                record["ended"] = True
        except Exception:
            pass
        finally:
            if close_client:
                await client.aclose()

    return record


def reset_process_store() -> None:
    """Clear stored process records (used in unit tests)."""
    _PROCESS_STORE.clear()
