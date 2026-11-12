"""User data access repository.

Currently backed by an in-memory store until the `users` table (with
`password_hash`) is added to the PostgreSQL schema. Replace the functions
below with database queries without changing the service or API layers.
"""
from app.core.config import settings
from app.core.security import hash_password

_USERS: dict[str, dict] = {}


def add_user(
    email: str,
    password: str,
    *,
    full_name: str,
    role: str,
    user_id: str | None = None,
) -> dict:
    key = email.lower()
    user = {
        "id": user_id or f"00000000-0000-0000-0000-{len(_USERS) + 1:012d}",
        "email": key,
        "full_name": full_name,
        "role": role,
        "password_hash": hash_password(password),
    }
    _USERS[key] = user
    return user


def get_user_by_email(email: str) -> dict | None:
    return _USERS.get(email.lower())


def _seed_admin() -> None:
    add_user(
        settings.seed_admin_email,
        settings.seed_admin_password,
        full_name="Administrator",
        role="admin",
        user_id="00000000-0000-0000-0000-000000000001",
    )


_seed_admin()
