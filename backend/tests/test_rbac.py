"""CRM-40 RBAC and immediate token-revocation regression tests.

Run from backend/: pytest -q tests/test_rbac.py
"""
from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

# Import the main module first: models.py reuses its declarative Base, and this
# order avoids a partially-initialized models module during router registration.
from main import app as backend_app
from models import UserRole
from app.api.deps import get_current_user
from app.repositories import revocation_repository, user_repository
from app.core.security import create_access_token
from routers.knowledge import require_role as knowledge_require_role
from routers.tickets import require_role as tickets_require_role


ROLE_FIXTURES = {
    "STAFF": "STAFF",
    "ENGINEER": "ENGINEER",
    "MANAGER": "MANAGER",
    "ADMIN": "ADMIN",
}


@pytest.fixture
def policy_client():
    app = FastAPI()

    @app.get("/knowledge")
    def knowledge(user=Depends(knowledge_require_role(
        UserRole.STAFF, UserRole.ENGINEER, UserRole.MANAGER, UserRole.ADMIN
    ))):
        return {"role": user["role"]}

    @app.post("/knowledge")
    def create_knowledge(user=Depends(knowledge_require_role(UserRole.MANAGER, UserRole.ADMIN))):
        return {"role": user["role"]}

    @app.patch("/tickets/{ticket_id}/copilot/approve")
    def approve(user=Depends(tickets_require_role(UserRole.ENGINEER, UserRole.MANAGER))):
        return {"role": user["role"]}

    return app


def _client_for_role(app: FastAPI, role: str) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "test-user",
        "email": "rbac-test@songnhat.vn",
        "role": role,
    }
    return TestClient(app)


@pytest.mark.parametrize("role", ["STAFF", "ENGINEER", "MANAGER", "ADMIN"])
def test_get_knowledge_passages_all_four_roles_are_allowed(policy_client, role):
    client = _client_for_role(policy_client, ROLE_FIXTURES[role])
    response = client.get("/knowledge")
    assert response.status_code == 200
    assert response.json()["role"] == ROLE_FIXTURES[role]


def test_staff_cannot_create_knowledge_passage(policy_client):
    response = _client_for_role(policy_client, "STAFF").post("/knowledge")
    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}


def test_engineer_cannot_create_knowledge_passage(policy_client):
    response = _client_for_role(policy_client, "ENGINEER").post("/knowledge")
    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}


@pytest.mark.parametrize("role", ["MANAGER", "ADMIN"])
def test_manager_and_admin_can_create_knowledge_passage(policy_client, role):
    response = _client_for_role(policy_client, role).post("/knowledge")
    assert response.status_code == 200
    assert response.json()["role"] == role


def test_staff_cannot_approve_copilot_ticket(policy_client):
    response = _client_for_role(policy_client, "STAFF").patch(
        "/tickets/00000000-0000-0000-0000-000000000001/copilot/approve"
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}




def test_admin_is_not_allowed_to_approve_copilot_ticket(policy_client):
    response = _client_for_role(policy_client, "ADMIN").patch(
        "/tickets/00000000-0000-0000-0000-000000000001/copilot/approve"
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}

@pytest.mark.parametrize("role", ["ENGINEER", "MANAGER"])
def test_engineer_and_manager_can_approve_copilot_ticket(policy_client, role):
    response = _client_for_role(policy_client, role).patch(
        "/tickets/00000000-0000-0000-0000-000000000001/copilot/approve"
    )
    assert response.status_code == 200
    assert response.json()["role"] == role


def test_unknown_role_is_denied(policy_client):
    response = _client_for_role(policy_client, "auditor").get("/knowledge")
    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}


def test_missing_credentials_return_401():
    # Exercise the real backend auth dependency rather than a mocked role check.
    from app.api.deps import get_current_user as real_get_current_user
    app = FastAPI()

    @app.get("/protected")
    def protected(user=Depends(real_get_current_user)):
        return {"email": user["email"]}

    response = TestClient(app).get("/protected")
    assert response.status_code == 401


def test_delete_revoke_immediately_invalidates_the_old_token():
    revocation_repository.reset_all()
    email = "crm40-revoke@songnhat.vn"
    user_repository.add_user(
        email,
        "not-used-for-token-test",
        full_name="CRM-40 Revocation Test",
        role="STAFF",
        user_id="crm40-revoke-user",
    )
    token = create_access_token(email)
    client = TestClient(backend_app)

    revoke_response = client.delete(
        "/api/auth/revoke", headers={"Authorization": f"Bearer {token}"}
    )
    assert revoke_response.status_code == 204

    old_token_response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert old_token_response.status_code == 401


def test_delete_revoke_requires_authentication():
    response = TestClient(backend_app).delete("/api/auth/revoke")
    assert response.status_code == 401
