from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token
from app.main import app

client = TestClient(app)


def _login():
    return client.post(
        "/api/auth/login",
        json={"email": settings.seed_admin_email, "password": settings.seed_admin_password},
    )


def test_login_success_returns_token():
    r = _login()
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_login_wrong_password_401():
    r = client.post(
        "/api/auth/login",
        json={"email": settings.seed_admin_email, "password": "wrong"},
    )
    assert r.status_code == 401


def test_me_with_token():
    token = _login().json()["access_token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == settings.seed_admin_email
    assert r.json()["role"] == "admin"


def test_me_without_token_401():
    assert client.get("/api/auth/me").status_code == 401


def test_me_invalid_token_401():
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


def test_me_expired_token_401():
    token = create_access_token(settings.seed_admin_email, timedelta(seconds=-5))
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
