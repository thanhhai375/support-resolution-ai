from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.deps import require_role
from app.core.config import settings
from app.core.security import create_access_token
from app.main import app
from app.repositories import user_repository

client = TestClient(app)

AGENT_EMAIL = "agent@example.com"
AGENT_PASSWORD = "Agent@123"


@pytest.fixture(scope="module", autouse=True)
def _agent_user():
    user_repository.add_user(
        AGENT_EMAIL, AGENT_PASSWORD, full_name="Support Agent", role="agent"
    )


def _login(email: str, password: str):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _admin_token() -> str:
    r = _login(settings.seed_admin_email, settings.seed_admin_password)
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- Login -----------------------------------------------------------------
def test_login_success_returns_token():
    r = _login(settings.seed_admin_email, settings.seed_admin_password)
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_login_wrong_password_401():
    assert _login(settings.seed_admin_email, "wrong").status_code == 401


def test_login_unknown_email_401():
    assert _login("nobody@example.com", "x").status_code == 401


# --- /me and 401 -----------------------------------------------------------
def test_me_with_token():
    r = client.get("/api/auth/me", headers=_auth(_admin_token()))
    assert r.status_code == 200
    assert r.json()["email"] == settings.seed_admin_email
    assert r.json()["role"] == "admin"


def test_me_without_token_401():
    assert client.get("/api/auth/me").status_code == 401


def test_me_invalid_token_401():
    r = client.get("/api/auth/me", headers=_auth("garbage"))
    assert r.status_code == 401


def test_me_expired_token_401():
    token = create_access_token(settings.seed_admin_email, timedelta(seconds=-5))
    assert client.get("/api/auth/me", headers=_auth(token)).status_code == 401


# --- Role-Based Access Control (403) ---------------------------------------
def test_admin_route_allows_admin():
    r = client.get("/api/auth/admin/ping", headers=_auth(_admin_token()))
    assert r.status_code == 200
    assert r.json()["message"] == "pong"


def test_admin_route_forbidden_for_agent_403():
    token = _login(AGENT_EMAIL, AGENT_PASSWORD).json()["access_token"]
    r = client.get("/api/auth/admin/ping", headers=_auth(token))
    assert r.status_code == 403


def test_admin_route_without_token_is_401_not_403():
    assert client.get("/api/auth/admin/ping").status_code == 401


def test_require_role_rejects_unknown_role():
    with pytest.raises(ValueError):
        require_role("superuser")


def test_require_role_needs_at_least_one_role():
    with pytest.raises(ValueError):
        require_role()


# --- CORS ------------------------------------------------------------------
def test_cors_allows_frontend_origin():
    origin = settings.cors_origins[0]
    r = client.options(
        "/api/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == origin


def test_cors_blocks_unknown_origin():
    r = client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in r.headers
