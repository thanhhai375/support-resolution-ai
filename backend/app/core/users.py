"""Temporary in-memory user store.

docs/database/schema.sql has no password column yet, so until the DB layer
(and a password_hash column) exists, users live here. Swap this module for a
repository backed by PostgreSQL later.
"""
from app.core.config import settings
from app.core.security import hash_password

_USERS: dict[str, dict] = {}


def _seed() -> None:
    email = settings.seed_admin_email.lower()
    _USERS[email] = {
        "id": "00000000-0000-0000-0000-000000000001",
        "email": email,
        "full_name": "Administrator",
        "role": "admin",
        "password_hash": hash_password(settings.seed_admin_password),
    }


_seed()


def get_user_by_email(email: str) -> dict | None:
    return _USERS.get(email.lower())
