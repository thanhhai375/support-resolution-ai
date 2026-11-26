"""Unit & integration tests for CRM-58 (WP-05 CRM-54): Copilot Approval APIs & Camunda User Task RESOLVED flow.

Covers:
  1. GET   /api/v1/copilot/{ticket_id}/approval (draft, citations, approval_status, rejection_reason)
  2. PATCH /api/v1/copilot/{ticket_id}/approve  (status=APPROVED, approved_by, approved_at, RBAC ENGINEER/MANAGER)
  3. PATCH /api/v1/copilot/{ticket_id}/reject   (status=REJECTED, rejection_reason)
  4. Aliases under /api/tickets/{ticket_id}/copilot/...
  5. Camunda BPMN User Task transition & signal to RESOLVED on approval
"""
from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as app_main
from app.main import Base, app, get_db
from app.api.deps import get_current_user
from app.api.v1.camunda_workflow import reset_approval_cache
from app.camunda.worker import (
    APPROVAL_SIGNAL_NAME,
    complete_human_approval,
    reset_process_store,
    start_ticket_triage_process,
)
from models import Category, CopilotPackage, Product, Ticket


@pytest.fixture
def approval_env(monkeypatch: pytest.MonkeyPatch):
    """Isolated SQLite in-memory DB + clean Camunda/cache state for each test."""
    monkeypatch.setenv("CAMUNDA_URL", "http://camunda.invalid:9")
    reset_process_store()
    reset_approval_cache()

    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    TestSessionLocal = sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )
    monkeypatch.setattr(app_main, "AsyncSessionLocal", TestSessionLocal)

    async def _init_schema_and_seed() -> uuid.UUID:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with TestSessionLocal() as session:
            prod = Product(code="DRIVES", name="Biến tần (Drives)")
            cat = Category(code="TECHNICAL_ESCALATION", name="Chuyển cấp kỹ thuật")
            session.add_all([prod, cat])
            await session.flush()

            ticket = Ticket(
                ticket_number=f"TK-58-{uuid.uuid4().hex[:6].upper()}",
                product_id=prod.id,
                category_id=cat.id,
                subject="Biến tần SD700 báo lỗi E001",
                description="Biến tần báo lỗi quá dòng khi khởi động tải nặng",
                status="OPEN",
                priority="HIGH",
                created_by="staff@songnhat.vn",
            )
            session.add(ticket)
            await session.flush()

            pkg = CopilotPackage(
                ticket_id=ticket.id,
                intent="TECHNICAL_ESCALATION",
                case_summary="Triệu chứng: Lỗi E001 quá dòng khi tăng tốc",
                missing_facts=["Số serial thiết bị"],
                citations=[
                    {
                        "document_title": "SD700 Operating Manual",
                        "page_number": 42,
                        "content_snippet": "E001: Kiểm tra thời gian tăng tốc P1120 và dòng định mức.",
                        "section": "4.2 Fault Codes",
                        "version": "v2.1",
                    }
                ],
                next_step="Kiểm tra thông số P1120 và đo cách điện motor.",
                draft="Kính gửi Quý khách, vui lòng kiểm tra thời gian tăng tốc P1120 theo trang 42 tài liệu SD700.",
                draft_response="Kính gửi Quý khách, vui lòng kiểm tra thời gian tăng tốc P1120 theo trang 42 tài liệu SD700.",
                approval_status="Pending",
            )
            session.add(pkg)
            await session.commit()
            return ticket.id

    ticket_id = asyncio.run(_init_schema_and_seed())

    async def _override_get_db():
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)

    def set_role(role: str, email: str | None = None) -> None:
        app.dependency_overrides[get_current_user] = lambda: {
            "id": f"user-{role.lower()}",
            "email": email or f"{role.lower()}@songnhat.vn",
            "role": role,
        }

    try:
        yield {
            "client": client,
            "ticket_id": str(ticket_id),
            "ticket_uuid": ticket_id,
            "set_role": set_role,
            "session_factory": TestSessionLocal,
        }
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        reset_process_store()
        reset_approval_cache()
        asyncio.run(test_engine.dispose())


# --- 1. GET /api/v1/copilot/{ticket_id}/approval (200 & 404) -----------------
def test_01_get_approval_returns_draft_citations_status_and_null_reason(approval_env):
    client = approval_env["client"]
    ticket_id = approval_env["ticket_id"]
    approval_env["set_role"]("STAFF")

    res = client.get(f"/api/v1/copilot/{ticket_id}/approval")
    assert res.status_code == 200
    body = res.json()
    assert body["ticket_id"] == ticket_id
    assert body["intent"] == "TECHNICAL_ESCALATION"
    assert "SD700" in body["draft"]
    assert len(body["citations"]) == 1
    assert body["citations"][0]["document_title"] == "SD700 Operating Manual"
    assert body["approval_status"] == "PENDING"
    assert body["rejection_reason"] is None
    assert body["approved_by"] is None
    assert body["approved_at"] is None


def test_02_get_approval_returns_404_when_ticket_has_no_package(approval_env):
    client = approval_env["client"]
    approval_env["set_role"]("STAFF")

    missing_id = str(uuid.uuid4())
    res = client.get(f"/api/v1/copilot/{missing_id}/approval")
    assert res.status_code == 404


# --- 2. PATCH /api/v1/copilot/{ticket_id}/approve ----------------------------
def test_03_approve_persists_approved_by_and_approved_at_and_resolves_ticket(approval_env):
    client = approval_env["client"]
    ticket_id = approval_env["ticket_id"]
    approval_env["set_role"]("ENGINEER", "eng.bao@songnhat.vn")

    asyncio.run(
        start_ticket_triage_process(
            ticket_id=ticket_id,
            ticket_description="Biến tần báo lỗi E001",
            intent="TECHNICAL_ESCALATION",
            is_hazard_escalated=False,
        )
    )

    res = client.patch(
        f"/api/v1/copilot/{ticket_id}/approve",
        json={"approved_by": "eng.bao@songnhat.vn"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "APPROVED"
    assert body["approval_status"] == "APPROVED"
    assert body["approved_by"] == "eng.bao@songnhat.vn"
    assert body["approved_at"] is not None
    assert body["persisted"] is True
    assert body["process_status"] == "RESOLVED"

    # Verify via GET /approval & Ticket detail
    get_res = client.get(f"/api/v1/copilot/{ticket_id}/approval")
    assert get_res.status_code == 200
    state = get_res.json()
    assert state["approval_status"] == "APPROVED"
    assert state["approved_by"] == "eng.bao@songnhat.vn"
    assert state["approved_at"] is not None
    assert state["process_status"] == "RESOLVED"

    ticket_res = client.get(f"/api/tickets/{ticket_id}")
    assert ticket_res.status_code == 200
    assert ticket_res.json()["status"] == "RESOLVED"


def test_04_manager_can_approve_with_edited_draft(approval_env):
    client = approval_env["client"]
    ticket_id = approval_env["ticket_id"]
    approval_env["set_role"]("MANAGER", "manager@songnhat.vn")

    edited_text = "Kính gửi Quý khách, kỹ sư đã xác nhận thông số P1120 = 10s xử lý dứt điểm lỗi E001."
    res = client.patch(
        f"/api/v1/copilot/{ticket_id}/approve",
        json={"draft": edited_text},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["approval_status"] == "APPROVED"
    assert body["approved_by"] == "manager@songnhat.vn"
    assert body["approved_at"] is not None

    state = client.get(f"/api/v1/copilot/{ticket_id}/approval").json()
    assert state["draft"] == edited_text
    assert state["approval_status"] == "APPROVED"


# --- 3. RBAC Enforcement (401 & 403) -----------------------------------------
def test_05_rbac_unauthenticated_401_and_staff_or_admin_403(approval_env):
    from app.repositories import revocation_repository

    revocation_repository.reset_all()
    client = approval_env["client"]
    ticket_id = approval_env["ticket_id"]

    # Unauthenticated -> 401 on all 3 endpoints
    assert client.get(f"/api/v1/copilot/{ticket_id}/approval").status_code == 401
    assert (
        client.patch(
            f"/api/v1/copilot/{ticket_id}/approve",
            json={"approved_by": "anon@songnhat.vn"},
        ).status_code
        == 401
    )
    assert (
        client.patch(
            f"/api/v1/copilot/{ticket_id}/reject",
            json={"rejection_reason": "anon"},
        ).status_code
        == 401
    )

    # STAFF & ADMIN -> 403 on approve/reject
    for role in ("STAFF", "ADMIN"):
        approval_env["set_role"](role)
        assert (
            client.patch(
                f"/api/v1/copilot/{ticket_id}/approve",
                json={"approved_by": f"{role.lower()}@songnhat.vn"},
            ).status_code
            == 403
        )
        assert (
            client.patch(
                f"/api/v1/copilot/{ticket_id}/reject",
                json={"rejection_reason": "Không đủ quyền"},
            ).status_code
            == 403
        )


# --- 4. PATCH /api/v1/copilot/{ticket_id}/reject -----------------------------
def test_06_reject_saves_rejected_status_and_reason(approval_env):
    client = approval_env["client"]
    ticket_id = approval_env["ticket_id"]
    approval_env["set_role"]("ENGINEER", "eng.reject@songnhat.vn")

    asyncio.run(
        start_ticket_triage_process(
            ticket_id=ticket_id,
            ticket_description="Biến tần báo lỗi E001",
            intent="TECHNICAL_ESCALATION",
            is_hazard_escalated=False,
        )
    )

    res = client.patch(
        f"/api/v1/copilot/{ticket_id}/reject",
        json={"reason": "Trích dẫn chưa đúng dòng máy SD700, cần kiểm tra lại serial."},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "REJECTED"
    assert body["approval_status"] == "REJECTED"
    assert body["rejected_by"] == "eng.reject@songnhat.vn"
    assert body["rejection_reason"] == "Trích dẫn chưa đúng dòng máy SD700, cần kiểm tra lại serial."
    assert body["persisted"] is True
    assert body["process_status"] == "REJECTED"

    state = client.get(f"/api/v1/copilot/{ticket_id}/approval").json()
    assert state["approval_status"] == "REJECTED"
    assert state["rejection_reason"] == "Trích dẫn chưa đúng dòng máy SD700, cần kiểm tra lại serial."


def test_07_reject_without_reason_returns_422(approval_env):
    client = approval_env["client"]
    ticket_id = approval_env["ticket_id"]
    approval_env["set_role"]("ENGINEER")

    assert client.patch(f"/api/v1/copilot/{ticket_id}/reject", json={}).status_code == 422
    assert (
        client.patch(f"/api/v1/copilot/{ticket_id}/reject", json={"rejection_reason": ""}).status_code
        == 422
    )


# --- 5. Aliases under /api/tickets/{ticket_id}/copilot/... -------------------
def test_08_ticket_copilot_get_aliases_return_approval_package(approval_env):
    client = approval_env["client"]
    ticket_id = approval_env["ticket_id"]
    approval_env["set_role"]("STAFF")

    for path in (
        f"/api/tickets/{ticket_id}/copilot",
        f"/api/tickets/{ticket_id}/copilot/approval",
    ):
        res = client.get(path)
        assert res.status_code == 200
        data = res.json()
        assert data["ticket_id"] == ticket_id
        assert data["approval_status"] == "PENDING"
        assert len(data["citations"]) == 1


def test_09_ticket_copilot_approve_alias_updates_ticket_package_and_camunda(approval_env):
    client = approval_env["client"]
    ticket_id = approval_env["ticket_id"]

    asyncio.run(
        start_ticket_triage_process(
            ticket_id=ticket_id,
            ticket_description="Biến tần báo lỗi E001",
            intent="TECHNICAL_ESCALATION",
            is_hazard_escalated=False,
        )
    )

    # STAFF forbidden on alias too
    approval_env["set_role"]("STAFF")
    assert client.patch(f"/api/tickets/{ticket_id}/copilot/approve").status_code == 403

    # ENGINEER succeeds on alias
    approval_env["set_role"]("ENGINEER", "alias.eng@songnhat.vn")
    res = client.patch(f"/api/tickets/{ticket_id}/copilot/approve", json={})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "RESOLVED"
    assert body["approval_status"] == "APPROVED"
    assert body["approved_by"] == "alias.eng@songnhat.vn"
    assert body["approved_at"] is not None
    assert body["process_status"] == "RESOLVED"

    # Package in DB also updated to APPROVED
    pkg_state = client.get(f"/api/tickets/{ticket_id}/copilot/approval").json()
    assert pkg_state["approval_status"] == "APPROVED"
    assert pkg_state["approved_by"] == "alias.eng@songnhat.vn"


def test_10_ticket_copilot_reject_alias_updates_package_and_camunda(approval_env):
    client = approval_env["client"]
    ticket_id = approval_env["ticket_id"]
    approval_env["set_role"]("MANAGER", "alias.mgr@songnhat.vn")

    asyncio.run(
        start_ticket_triage_process(
            ticket_id=ticket_id,
            ticket_description="Biến tần báo lỗi E001",
            intent="TECHNICAL_ESCALATION",
            is_hazard_escalated=False,
        )
    )

    res = client.patch(
        f"/api/tickets/{ticket_id}/copilot/reject",
        json={"rejection_reason": "Cần bổ sung ảnh chụp màn hình lỗi"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["approval_status"] == "REJECTED"
    assert body["rejection_reason"] == "Cần bổ sung ảnh chụp màn hình lỗi"
    assert body["process_status"] == "REJECTED"


# --- 6. Camunda REST User Task Complete + Signal -> RESOLVED -----------------
@pytest.mark.anyio
async def test_11_camunda_rest_user_task_completes_and_emits_resolved_signal():
    reset_process_store()
    completed_payloads: list[dict] = []
    emitted_signals: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        path = request.url.path
        if path.endswith("/process-definition/key/ticket-triage/start"):
            return httpx.Response(200, json={"id": "proc-58-rest", "businessKey": "TCK-58-REST"})
        if path.endswith("/external-task/fetchAndLock"):
            return httpx.Response(200, json=[])
        if path.endswith("/task") and request.method == "GET":
            return httpx.Response(
                200,
                json=[{"id": "usertask-58-1", "taskDefinitionKey": "Task_HumanApproval"}],
            )
        if path.endswith("/task/usertask-58-1/complete"):
            completed_payloads.append(json.loads(request.content.decode("utf-8")))
            return httpx.Response(204)
        if path.endswith("/signal"):
            emitted_signals.append(json.loads(request.content.decode("utf-8")))
            return httpx.Response(204)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        await start_ticket_triage_process(
            ticket_id="TCK-58-REST",
            ticket_description="Xin tài liệu hướng dẫn G120",
            intent="DOCUMENT_REQUEST",
            is_hazard_escalated=False,
            camunda_url="http://camunda.local:8080",
            client=mock_client,
        )

        updated = await complete_human_approval(
            "TCK-58-REST",
            approved=True,
            reviewer="engineer@songnhat.vn",
            camunda_url="http://camunda.local:8080",
            client=mock_client,
        )

    assert updated is not None
    assert updated["status"] == "RESOLVED"
    assert updated["current_activity_id"] == "EndEvent_Resolved"
    assert len(completed_payloads) == 1
    vars_sent = completed_payloads[0]["variables"]
    assert vars_sent["approval_status"]["value"] == "APPROVED"
    assert vars_sent["workflow_step"]["value"] == "RESOLVED"
    assert vars_sent["ticket_status"]["value"] == "RESOLVED"
    assert len(emitted_signals) == 1
    assert emitted_signals[0]["name"] == APPROVAL_SIGNAL_NAME
    assert emitted_signals[0]["variables"]["status"]["value"] == "RESOLVED"


def test_12_second_review_after_resolved_returns_409_and_allows_pdf_export(approval_env):
    from app.repositories import user_repository

    client = approval_env["client"]
    ticket_id = approval_env["ticket_id"]

    eng_email = "eng-export-58@songnhat.vn"
    user_repository.add_user(
        eng_email, "pw", full_name="Kỹ sư Hoài Bảo", role="technical_approver", user_id="u-exp58"
    )
    try:
        approval_env["set_role"]("ENGINEER", eng_email)
        asyncio.run(
            start_ticket_triage_process(
                ticket_id=ticket_id,
                ticket_description="Biến tần báo lỗi E001",
                intent="TECHNICAL_ESCALATION",
                is_hazard_escalated=False,
            )
        )

        first = client.patch(
            f"/api/v1/copilot/{ticket_id}/approve",
            json={"approved_by": eng_email},
        )
        assert first.status_code == 200
        assert first.json()["process_status"] == "RESOLVED"

        # Second review returns 409 Conflict
        second = client.patch(
            f"/api/v1/copilot/{ticket_id}/reject",
            json={"rejection_reason": "Đổi ý"},
        )
        assert second.status_code == 409

        # STAFF can also export Long's PDF right after approval!
        approval_env["set_role"]("STAFF", "staff@songnhat.vn")
        pdf_res = client.get(f"/api/v1/copilot/{ticket_id}/export")
        assert pdf_res.status_code == 200
        assert pdf_res.headers["content-type"] == "application/pdf"
        assert pdf_res.content.startswith(b"%PDF-")
    finally:
        user_repository._USERS.pop(eng_email, None)
