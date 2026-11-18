import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.repositories import revocation_repository, user_repository

client = TestClient(app)


@pytest.fixture(autouse=True)
def _setup_roles_and_reset_revocations():
    revocation_repository.reset_all()
    user_repository.add_user(
        "agent@songnhat.vn",
        "Agent@123",
        full_name="Support Agent",
        role="support_agent",
        allowed_accounts=["ACC-01"],
        allowed_cases=["CASE-101", "CASE-102"],
    )
    user_repository.add_user(
        "approver@songnhat.vn",
        "Approver@123",
        full_name="Technical Approver",
        role="technical_approver",
        allowed_accounts=["ACC-01"],
        allowed_cases=["CASE-101"],
    )
    user_repository.add_user(
        "steward@songnhat.vn",
        "Steward@123",
        full_name="Knowledge Steward",
        role="knowledge_steward",
    )
    yield
    revocation_repository.reset_all()


def _token_for(email: str, password: str) -> str:
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- 1. 4-Role Least Privilege & Account/Case Access (SEC 01) ---------------
def test_retrieval_allowed_for_authorized_case_and_account():
    token = _token_for("agent@songnhat.vn", "Agent@123")
    res = client.post(
        "/api/auth/access/retrieval-check",
        headers=_auth(token),
        json={
            "case_id": "CASE-101",
            "account_id": "ACC-01",
            "source_ids": ["DOC-G120-P142"],
        },
    )
    assert res.status_code == 200
    assert res.json()["allowed"] is True


def test_retrieval_blocks_cross_account_access_403():
    token = _token_for("agent@songnhat.vn", "Agent@123")
    res = client.post(
        "/api/auth/access/retrieval-check",
        headers=_auth(token),
        json={
            "case_id": "CASE-101",
            "account_id": "ACC-OTHER-99",
            "source_ids": ["DOC-G120-P142"],
        },
    )
    assert res.status_code == 403
    assert "Cross-account" in res.json()["detail"]


def test_retrieval_blocks_unauthorized_case_403():
    token = _token_for("agent@songnhat.vn", "Agent@123")
    res = client.post(
        "/api/auth/access/retrieval-check",
        headers=_auth(token),
        json={
            "case_id": "CASE-999",
            "account_id": "ACC-01",
            "source_ids": [],
        },
    )
    assert res.status_code == 403


def test_export_blocks_knowledge_steward_role_403():
    token = _token_for("steward@songnhat.vn", "Steward@123")
    res = client.post(
        "/api/auth/access/export-check",
        headers=_auth(token),
        json={"case_id": "CASE-101", "source_ids": ["DOC-G120-P142"]},
    )
    assert res.status_code == 403


def test_export_technical_content_requires_technical_approver():
    token = _token_for("agent@songnhat.vn", "Agent@123")
    denied = client.post(
        "/api/auth/access/export-check",
        headers=_auth(token),
        json={
            "case_id": "CASE-101",
            "account_id": "ACC-01",
            "source_ids": ["DOC-G120-P142"],
            "requires_technical_approval": True,
            "approved_by_role": "support_agent",
        },
    )
    assert denied.status_code == 403

    allowed = client.post(
        "/api/auth/access/export-check",
        headers=_auth(token),
        json={
            "case_id": "CASE-101",
            "account_id": "ACC-01",
            "source_ids": ["DOC-G120-P142"],
            "requires_technical_approval": True,
            "approved_by_role": "technical_approver",
        },
    )
    assert allowed.status_code == 200
    assert allowed.json()["allowed"] is True


# --- 2. Immediate Token & User Revocation (SEC 04) --------------------------
def test_logout_immediately_revokes_active_token():
    token = _token_for("agent@songnhat.vn", "Agent@123")
    assert client.get("/api/auth/me", headers=_auth(token)).status_code == 200

    logout_res = client.post("/api/auth/logout", headers=_auth(token))
    assert logout_res.status_code == 200

    assert client.get("/api/auth/me", headers=_auth(token)).status_code == 401


def test_admin_revoking_user_blocks_in_flight_token_and_future_login():
    agent_token = _token_for("agent@songnhat.vn", "Agent@123")
    admin_token = _token_for(settings.seed_admin_email, settings.seed_admin_password)

    rev = client.post(
        "/api/auth/revocations",
        headers=_auth(admin_token),
        json={
            "target_type": "user",
            "target_id": "agent@songnhat.vn",
            "reason": "Role reassigned",
        },
    )
    assert rev.status_code == 200
    assert rev.json()["cache_cleaned"] is False

    # Existing token is immediately rejected
    assert client.get("/api/auth/me", headers=_auth(agent_token)).status_code == 401

    # New login attempt is also blocked
    relogin = client.post(
        "/api/auth/login",
        json={"email": "agent@songnhat.vn", "password": "Agent@123"},
    )
    assert relogin.status_code == 403

    # Admin restores user access
    restore = client.post(
        "/api/auth/revocations/restore",
        headers=_auth(admin_token),
        json={"target_type": "user", "target_id": "agent@songnhat.vn"},
    )
    assert restore.status_code == 200
    assert restore.json()["restored"] is True
    assert client.get("/api/auth/me", headers=_auth(agent_token)).status_code == 200


# --- 3. In-Flight Source Withdrawal & Pending Cache Cleanup (OPS 05) -------
def test_in_flight_source_withdrawal_blocks_export_before_cache_cleanup():
    agent_token = _token_for("agent@songnhat.vn", "Agent@123")
    steward_token = _token_for("steward@songnhat.vn", "Steward@123")

    # Step 1: Retrieval check succeeds before generation starts
    pre = client.post(
        "/api/auth/access/retrieval-check",
        headers=_auth(agent_token),
        json={
            "case_id": "CASE-101",
            "account_id": "ACC-01",
            "source_ids": ["DOC-G120-P142"],
        },
    )
    assert pre.status_code == 200

    # Step 2: While output is paused/in-flight, steward withdraws DOC-G120-P142
    rev = client.post(
        "/api/auth/revocations",
        headers=_auth(steward_token),
        json={
            "target_type": "source",
            "target_id": "DOC-G120-P142",
            "reason": "Superseded manual revision",
        },
    )
    assert rev.status_code == 200
    assert rev.json()["cache_cleaned"] is False

    # Step 3: Pending cache cleanup NEVER permits export
    export_res = client.post(
        "/api/auth/access/export-check",
        headers=_auth(agent_token),
        json={
            "case_id": "CASE-101",
            "account_id": "ACC-01",
            "source_ids": ["DOC-G120-P142"],
        },
    )
    assert export_res.status_code == 403
    assert "DOC-G120-P142" in export_res.json()["detail"]

    # Step 4: Separate 5-minute cache cleanup test completes
    cleanup = client.post(
        "/api/auth/revocations/cache-cleanup",
        headers=_auth(steward_token),
        json={"target_type": "source", "target_id": "DOC-G120-P142"},
    )
    assert cleanup.status_code == 200
    assert cleanup.json()["cache_cleaned"] is True


def test_knowledge_steward_cannot_revoke_user_403():
    steward_token = _token_for("steward@songnhat.vn", "Steward@123")
    res = client.post(
        "/api/auth/revocations",
        headers=_auth(steward_token),
        json={"target_type": "user", "target_id": "agent@songnhat.vn"},
    )
    assert res.status_code == 403


# --- 4. Fail Closed When Authoritative Check Unavailable (SEC 04 / REV 03) --
def test_fails_closed_when_authoritative_policy_service_unavailable():
    agent_token = _token_for("agent@songnhat.vn", "Agent@123")
    revocation_repository.set_authoritative_check_available(False)

    res = client.post(
        "/api/auth/access/export-check",
        headers=_auth(agent_token),
        json={"case_id": "CASE-101", "account_id": "ACC-01", "source_ids": []},
    )
    assert res.status_code == 503
