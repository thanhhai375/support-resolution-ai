"""Unit & integration tests for Camunda 7 BPMN Intent Routing Workflow (CRM-44)."""

import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.camunda.worker import (
    PROCESS_DEFINITION_KEY,
    SUBSCRIBED_TOPICS,
    TOPIC_DOCUMENT_REQUEST,
    TOPIC_SERVICE_PROGRESS,
    TOPIC_TECHNICAL_ESCALATION,
    CamundaExternalTaskWorker,
    deploy_bpmn_to_camunda,
    reset_process_store,
    start_ticket_triage_process,
)
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean_camunda_state(monkeypatch: pytest.MonkeyPatch):
    from app.api.v1 import camunda_workflow
    from app.main import _copilot_role_guard, get_db

    async def _no_db_persist(*args, **kwargs):
        return False

    monkeypatch.delenv("CAMUNDA_URL", raising=False)
    # CRM-40 guards the copilot routes and CRM-44 tests must not need Postgres / a login.
    monkeypatch.setattr(camunda_workflow, "_persist_decision", _no_db_persist)
    app.dependency_overrides[_copilot_role_guard] = lambda: {"role": "STAFF", "email": "test"}
    app.dependency_overrides[camunda_workflow.require_approver_role] = lambda: {
        "role": "ENGINEER",
        "email": "engineer@example.com",
    }
    app.dependency_overrides[get_db] = lambda: None
    reset_process_store()
    yield
    app.dependency_overrides.pop(_copilot_role_guard, None)
    app.dependency_overrides.pop(camunda_workflow.require_approver_role, None)
    app.dependency_overrides.pop(get_db, None)
    reset_process_store()


# --- 1. BPMN XML Structure Validation --------------------------------------
def test_ticket_triage_bpmn_has_safety_gateway_intent_gateway_and_3_topics():
    repo_root = Path(__file__).resolve().parents[2]
    bpmn_file = repo_root / "camunda" / "ticket-triage.bpmn"
    assert bpmn_file.exists(), "camunda/ticket-triage.bpmn must exist"

    tree = ET.parse(bpmn_file)
    root = tree.getroot()
    ns = {
        "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        "camunda": "http://camunda.org/schema/1.0/bpmn",
    }

    process = root.find("bpmn:process", ns)
    assert process is not None
    assert process.attrib.get("id") == PROCESS_DEFINITION_KEY
    assert process.attrib.get("isExecutable") == "true"

    gateways = {g.attrib["id"] for g in process.findall("bpmn:exclusiveGateway", ns)}
    assert "Gateway_SafetyCheck" in gateways
    assert "Gateway_IntentRouting" in gateways

    service_tasks = process.findall("bpmn:serviceTask", ns)
    topics = {
        t.attrib.get(f"{{{ns['camunda']}}}topic")
        for t in service_tasks
        if t.attrib.get(f"{{{ns['camunda']}}}type") == "external"
    }
    assert topics == set(SUBSCRIBED_TOPICS)


# --- 2. External Task Worker Topic Routing ---------------------------------
def test_worker_subscribes_and_routes_all_three_intent_topics():
    worker = CamundaExternalTaskWorker()
    assert set(worker.subscribed_topics) == {
        TOPIC_DOCUMENT_REQUEST,
        TOPIC_SERVICE_PROGRESS,
        TOPIC_TECHNICAL_ESCALATION,
    }

    doc_res = worker.dispatch_topic(
        TOPIC_DOCUMENT_REQUEST, {"ticket_id": "T-1", "intent": "DOCUMENT_REQUEST"}
    )
    assert doc_res["routed_topic"] == TOPIC_DOCUMENT_REQUEST
    assert doc_res["triage_queue"] == "DOCUMENTATION_QUEUE"
    assert doc_res["requires_technical_approver"] is False

    prog_res = worker.dispatch_topic(
        TOPIC_SERVICE_PROGRESS, {"ticket_id": "T-2", "intent": "SERVICE_PROGRESS"}
    )
    assert prog_res["routed_topic"] == TOPIC_SERVICE_PROGRESS
    assert prog_res["triage_queue"] == "SERVICE_STATUS_QUEUE"

    tech_res = worker.dispatch_topic(
        TOPIC_TECHNICAL_ESCALATION,
        {"ticket_id": "T-3", "intent": "TECHNICAL_ESCALATION"},
    )
    assert tech_res["routed_topic"] == TOPIC_TECHNICAL_ESCALATION
    assert tech_res["triage_queue"] == "ENGINEERING_ESCALATION_QUEUE"
    assert tech_res["requires_technical_approver"] is True


# --- 3. Fallback when CAMUNDA_URL is unset (Backward Compatible) ------------
def test_analyze_without_camunda_url_runs_legacy_fallback():
    res = client.post(
        "/api/copilot/analyze",
        json={
            "ticket_id": "TCK-LEGACY-01",
            "ticket_description": "Biến tần báo lỗi F0022 khi tăng tốc",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["intent"] == "TECHNICAL_ESCALATION"
    assert body.get("process_instance_id") is None

    status_res = client.get("/api/copilot/process/TCK-LEGACY-01/status")
    assert status_res.status_code == 404


# --- 4. Analyze with CAMUNDA_URL set -> Starts Process & Status Endpoint ----
def test_analyze_with_camunda_url_starts_process_for_3_intents_and_hazard(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("CAMUNDA_URL", "http://localhost:18080")

    cases = [
        (
            "TCK-DOC-01",
            "Cho tôi xin tài liệu hướng dẫn lắp đặt và manual biến tần SINAMICS G120",
            "DOCUMENT_REQUEST",
            TOPIC_DOCUMENT_REQUEST,
            "WAITING_HUMAN_APPROVAL",
        ),
        (
            "TCK-PROG-02",
            "Cho hỏi tiến độ bảo hành đơn hàng của tôi đến đâu rồi, bao giờ xong?",
            "SERVICE_PROGRESS",
            TOPIC_SERVICE_PROGRESS,
            "WAITING_HUMAN_APPROVAL",
        ),
        (
            "TCK-TECH-03",
            "Biến tần báo lỗi F0022 khi tăng tốc ở tải 80%",
            "TECHNICAL_ESCALATION",
            TOPIC_TECHNICAL_ESCALATION,
            "WAITING_HUMAN_APPROVAL",
        ),
        (
            "TCK-HAZ-04",
            "Tủ điều khiển biến tần bốc khói trắng và có mùi khét",
            "TECHNICAL_ESCALATION",
            None,
            "ESCALATED_HAZARD",
        ),
    ]

    for ticket_id, desc, expected_intent, expected_topic, expected_status in cases:
        res = client.post(
            "/api/copilot/analyze",
            json={"ticket_id": ticket_id, "ticket_description": desc},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["intent"] == expected_intent
        assert data["process_instance_id"] is not None
        assert data["camunda_topic"] == expected_topic

        status_res = client.get(f"/api/copilot/process/{ticket_id}/status")
        assert status_res.status_code == 200
        proc = status_res.json()
        assert proc["ticket_id"] == ticket_id
        assert proc["process_definition_key"] == PROCESS_DEFINITION_KEY
        assert proc["status"] == expected_status
        assert proc["routed_topic"] == expected_topic


# --- 5. Camunda REST API Integration (Deploy, Start, FetchAndLock, Complete)
@pytest.mark.anyio
async def test_camunda_rest_deploy_start_and_external_worker_complete():
    completed_tasks: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/deployment/create"):
            return httpx.Response(
                200,
                json={"id": "dep-001", "name": "songnhat-ticket-triage"},
            )
        if path.endswith(f"/process-definition/key/{PROCESS_DEFINITION_KEY}/start"):
            return httpx.Response(
                200,
                json={"id": "camunda-proc-999", "businessKey": "TCK-REST-99"},
            )
        if path.endswith("/external-task/fetchAndLock"):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "ext-task-1",
                        "topicName": TOPIC_DOCUMENT_REQUEST,
                        "processInstanceId": "camunda-proc-999",
                        "variables": {
                            "ticket_id": {"value": "TCK-REST-99", "type": "String"},
                            "intent": {"value": "DOCUMENT_REQUEST", "type": "String"},
                        },
                    }
                ],
            )
        if path.endswith("/external-task/ext-task-1/complete"):
            completed_tasks.append("ext-task-1")
            return httpx.Response(204)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        dep = await deploy_bpmn_to_camunda(
            camunda_url="http://camunda.local:8080",
            client=mock_client,
        )
        assert dep["id"] == "dep-001"

        proc = await start_ticket_triage_process(
            ticket_id="TCK-REST-99",
            ticket_description="Xin tài liệu hướng dẫn động cơ",
            intent="DOCUMENT_REQUEST",
            is_hazard_escalated=False,
            camunda_url="http://camunda.local:8080",
            client=mock_client,
        )
        assert proc is not None
        assert proc["process_instance_id"] == "camunda-proc-999"
        assert proc["engine_mode"] == "camunda_rest"
        assert proc["routed_topic"] == TOPIC_DOCUMENT_REQUEST
        assert completed_tasks == ["ext-task-1"]


# --- 8. Approval API (CRM-41 request, implemented in CRM-44) ---------------
def _start_local_process(ticket_id: str, hazard: bool = False):
    import asyncio

    return asyncio.run(
        start_ticket_triage_process(
            ticket_id=ticket_id,
            ticket_description="Xin tài liệu SINAMICS G120",
            intent="DOCUMENT_REQUEST",
            is_hazard_escalated=hazard,
            camunda_url="http://camunda.invalid:9",
        )
    )


def test_approve_completes_process_and_stores_approver():
    _start_local_process("TCK-APR-1")
    res = client.patch("/api/v1/copilot/TCK-APR-1/approve", json={"approved_by": "engineer@example.com"})
    assert res.status_code == 200
    body = res.json()
    assert body["approval_status"] == "APPROVED"
    assert body["approved_by"] == "engineer@example.com"
    assert body["process_status"] == "COMPLETED"
    assert client.get("/api/copilot/process/TCK-APR-1/status").json()["status"] == "COMPLETED"


def test_reject_stores_reason_and_ends_process():
    _start_local_process("TCK-REJ-1")
    res = client.patch(
        "/api/v1/copilot/TCK-REJ-1/reject",
        json={"rejection_reason": "Thiếu số serial", "rejected_by": "manager@example.com"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["approval_status"] == "REJECTED"
    assert body["rejection_reason"] == "Thiếu số serial"
    assert body["process_status"] == "REJECTED"


def test_reject_requires_reason_and_approve_requires_approver():
    assert client.patch("/api/v1/copilot/TCK-X/reject", json={}).status_code == 422
    assert client.patch("/api/v1/copilot/TCK-X/approve", json={}).status_code == 422


def test_second_review_returns_409():
    _start_local_process("TCK-DUP-1")
    assert client.patch("/api/v1/copilot/TCK-DUP-1/approve", json={"approved_by": "a"}).status_code == 200
    assert client.patch("/api/v1/copilot/TCK-DUP-1/reject", json={"rejection_reason": "x"}).status_code == 409


def test_approve_without_process_still_succeeds_without_camunda():
    res = client.patch("/api/v1/copilot/TCK-NOPROC/approve", json={"approvedBy": "engineer@example.com"})
    assert res.status_code == 200
    assert res.json()["process_status"] is None


# --- 9. CRM-69 RBAC Enforcement on /api/v1/copilot/{ticket_id}/approve|reject
def test_crm69_approve_and_reject_without_token_return_401():
    from app.api.v1 import camunda_workflow
    from app.repositories import revocation_repository

    revocation_repository.reset_all()
    app.dependency_overrides.pop(camunda_workflow.require_approver_role, None)

    approve_res = client.patch(
        "/api/v1/copilot/TCK-UNAUTH/approve",
        json={"approved_by": "nobody@example.com"},
    )
    reject_res = client.patch(
        "/api/v1/copilot/TCK-UNAUTH/reject",
        json={"rejection_reason": "no auth"},
    )
    assert approve_res.status_code == 401
    assert reject_res.status_code == 401


@pytest.mark.parametrize("forbidden_role", ["STAFF", "support_agent", "ADMIN", "administrator"])
def test_crm69_staff_and_admin_are_forbidden_403(forbidden_role: str):
    from app.api.deps import get_current_user
    from app.api.v1 import camunda_workflow

    app.dependency_overrides.pop(camunda_workflow.require_approver_role, None)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u-forbidden",
        "email": "forbidden@songnhat.vn",
        "role": forbidden_role,
    }
    try:
        approve_res = client.patch(
            "/api/v1/copilot/TCK-FORBID/approve",
            json={"approved_by": "forbidden@songnhat.vn"},
        )
        reject_res = client.patch(
            "/api/v1/copilot/TCK-FORBID/reject",
            json={"rejection_reason": "not allowed"},
        )
        assert approve_res.status_code == 403
        assert reject_res.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.parametrize(
    "allowed_role",
    ["ENGINEER", "technical_approver", "MANAGER", "knowledge_steward"],
)
def test_crm69_engineer_and_manager_can_approve_and_reject(allowed_role: str):
    from app.api.deps import get_current_user
    from app.api.v1 import camunda_workflow

    app.dependency_overrides.pop(camunda_workflow.require_approver_role, None)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u-approver",
        "email": "approver@songnhat.vn",
        "role": allowed_role,
    }
    try:
        _start_local_process(f"TCK-OK-APR-{allowed_role}")
        approve_res = client.patch(
            f"/api/v1/copilot/TCK-OK-APR-{allowed_role}/approve",
            json={"approved_by": "approver@songnhat.vn"},
        )
        assert approve_res.status_code == 200
        assert approve_res.json()["approval_status"] == "APPROVED"

        _start_local_process(f"TCK-OK-REJ-{allowed_role}")
        reject_res = client.patch(
            f"/api/v1/copilot/TCK-OK-REJ-{allowed_role}/reject",
            json={"rejection_reason": "Thiếu thông tin", "rejected_by": "approver@songnhat.vn"},
        )
        assert reject_res.status_code == 200
        assert reject_res.json()["approval_status"] == "REJECTED"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_crm69_real_jwt_token_rbac_end_to_end():
    from app.api.v1 import camunda_workflow
    from app.core.security import create_access_token
    from app.repositories import revocation_repository, user_repository

    revocation_repository.reset_all()
    app.dependency_overrides.pop(camunda_workflow.require_approver_role, None)

    staff_email = "staff-crm69@songnhat.vn"
    eng_email = "eng-crm69@songnhat.vn"
    user_repository.add_user(
        staff_email, "pw", full_name="Staff", role="support_agent", user_id="u-s69"
    )
    user_repository.add_user(
        eng_email, "pw", full_name="Engineer", role="technical_approver", user_id="u-e69"
    )
    try:
        staff_token = create_access_token(staff_email)
        eng_token = create_access_token(eng_email)

        denied = client.patch(
            "/api/v1/copilot/TCK-JWT-69/approve",
            json={"approved_by": staff_email},
            headers={"Authorization": f"Bearer {staff_token}"},
        )
        assert denied.status_code == 403

        _start_local_process("TCK-JWT-69")
        allowed = client.patch(
            "/api/v1/copilot/TCK-JWT-69/approve",
            json={"approved_by": eng_email},
            headers={"Authorization": f"Bearer {eng_token}"},
        )
        assert allowed.status_code == 200
        assert allowed.json()["approval_status"] == "APPROVED"

        # CRM-32: immediate token revocation also blocks approval endpoints (401)
        revocation_repository.revoke_token(eng_token)
        revoked = client.patch(
            "/api/v1/copilot/TCK-JWT-69-REV/approve",
            json={"approved_by": eng_email},
            headers={"Authorization": f"Bearer {eng_token}"},
        )
        assert revoked.status_code == 401
    finally:
        user_repository._USERS.pop(staff_email, None)
        user_repository._USERS.pop(eng_email, None)
        revocation_repository.reset_all()

