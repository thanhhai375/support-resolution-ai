"""Repository for managing token, user, case, and knowledge-source revocations (SEC 04).

Enforces immediate logical blocking upon revocation and tracks cache cleanup
deadlines (must complete within 5 minutes; pending cleanup never permits export).
"""
from datetime import datetime, timedelta, timezone

CACHE_CLEANUP_WINDOW = timedelta(minutes=5)

_REVOKED_TOKENS: set[str] = set()
_REVOKED_USERS: dict[str, dict] = {}
_REVOKED_SOURCES: dict[str, dict] = {}
_REVOKED_CASES: dict[str, dict] = {}
_AUTHORITATIVE_CHECK_AVAILABLE: bool = True


def _now() -> datetime:
    return datetime.now(timezone.utc)


def revoke_token(token: str) -> None:
    """Immediately block a specific JWT access token."""
    _REVOKED_TOKENS.add(token)


def is_token_revoked(token: str) -> bool:
    return token in _REVOKED_TOKENS


def revoke_user(email: str, reason: str = "Administrative revocation") -> dict:
    """Immediately block all active and future sessions for a user."""
    key = email.lower()
    now = _now()
    record = {
        "target_type": "user",
        "target_id": key,
        "reason": reason,
        "revoked_at": now.isoformat(),
        "cache_cleanup_due_at": (now + CACHE_CLEANUP_WINDOW).isoformat(),
        "cache_cleaned": False,
    }
    _REVOKED_USERS[key] = record
    return record


def restore_user(email: str) -> bool:
    """Remove user revocation so the user can authenticate again."""
    return _REVOKED_USERS.pop(email.lower(), None) is not None


def is_user_revoked(email: str) -> bool:
    return email.lower() in _REVOKED_USERS


def revoke_source(source_id: str, reason: str = "Source withdrawn") -> dict:
    """Immediately block a knowledge source or passage from retrieval and export."""
    now = _now()
    record = {
        "target_type": "source",
        "target_id": source_id,
        "reason": reason,
        "revoked_at": now.isoformat(),
        "cache_cleanup_due_at": (now + CACHE_CLEANUP_WINDOW).isoformat(),
        "cache_cleaned": False,
    }
    _REVOKED_SOURCES[source_id] = record
    return record


def restore_source(source_id: str) -> bool:
    return _REVOKED_SOURCES.pop(source_id, None) is not None


def is_source_revoked(source_id: str) -> bool:
    return source_id in _REVOKED_SOURCES


def get_source_revocation(source_id: str) -> dict | None:
    return _REVOKED_SOURCES.get(source_id)


def revoke_case(case_id: str, reason: str = "Case access revoked") -> dict:
    """Immediately block access to a specific support case."""
    now = _now()
    record = {
        "target_type": "case",
        "target_id": case_id,
        "reason": reason,
        "revoked_at": now.isoformat(),
        "cache_cleanup_due_at": (now + CACHE_CLEANUP_WINDOW).isoformat(),
        "cache_cleaned": False,
    }
    _REVOKED_CASES[case_id] = record
    return record


def restore_case(case_id: str) -> bool:
    return _REVOKED_CASES.pop(case_id, None) is not None


def is_case_revoked(case_id: str) -> bool:
    return case_id in _REVOKED_CASES


def mark_cache_cleaned(target_type: str, target_id: str) -> bool:
    """Mark cache cleanup completed for a revoked entity (OPS 05 / SEC 04 test)."""
    store = {
        "user": _REVOKED_USERS,
        "source": _REVOKED_SOURCES,
        "case": _REVOKED_CASES,
    }.get(target_type)
    if store is None:
        return False
    key = target_id.lower() if target_type == "user" else target_id
    record = store.get(key)
    if record is None:
        return False
    record["cache_cleaned"] = True
    record["cache_cleaned_at"] = _now().isoformat()
    return True


def set_authoritative_check_available(available: bool) -> None:
    """Toggle authoritative policy service availability (for fail-closed testing)."""
    global _AUTHORITATIVE_CHECK_AVAILABLE
    _AUTHORITATIVE_CHECK_AVAILABLE = available


def is_authoritative_check_available() -> bool:
    return _AUTHORITATIVE_CHECK_AVAILABLE


def list_revocations() -> dict[str, list[dict]]:
    return {
        "users": list(_REVOKED_USERS.values()),
        "sources": list(_REVOKED_SOURCES.values()),
        "cases": list(_REVOKED_CASES.values()),
    }


def reset_all() -> None:
    """Clear all revocations and restore authoritative service availability."""
    global _AUTHORITATIVE_CHECK_AVAILABLE
    _REVOKED_TOKENS.clear()
    _REVOKED_USERS.clear()
    _REVOKED_SOURCES.clear()
    _REVOKED_CASES.clear()
    _AUTHORITATIVE_CHECK_AVAILABLE = True
