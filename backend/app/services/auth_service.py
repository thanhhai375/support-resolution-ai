"""Authentication, RBAC, and immediate revocation service (CRM-19 & CRM-32)."""
from app.core.security import create_access_token, decode_access_token, verify_password
from app.repositories import revocation_repository, user_repository

EXPORT_ALLOWED_ROLES = {"support_agent", "technical_approver", "administrator"}
RETRIEVAL_ALLOWED_ROLES = {
    "support_agent",
    "technical_approver",
    "knowledge_steward",
    "administrator",
}


class InvalidCredentialsError(Exception):
    """Raised when the email or password is invalid."""


class AccessRevokedError(Exception):
    """Raised when a user, token, case, or knowledge source has been revoked."""


class PolicyServiceUnavailableError(Exception):
    """Raised when authoritative authorization cannot be verified (fail closed)."""


class InsufficientScopeError(Exception):
    """Raised when a user lacks role, account, case, or technical approval rights."""


def _ensure_policy_service() -> None:
    if not revocation_repository.is_authoritative_check_available():
        raise PolicyServiceUnavailableError(
            "Authoritative authorization service unavailable; failing closed"
        )


def login(email: str, password: str) -> str:
    """Verify credentials and return a signed JWT access token."""
    _ensure_policy_service()
    user = user_repository.get_user_by_email(email)
    if user is None or not verify_password(password, user["password_hash"]):
        raise InvalidCredentialsError
    if revocation_repository.is_user_revoked(user["email"]):
        raise AccessRevokedError("User access has been revoked")
    return create_access_token(user["email"])


def get_user_from_token(token: str) -> dict | None:
    """Resolve the user record for a valid, non-revoked JWT token, or return None."""
    if not revocation_repository.is_authoritative_check_available():
        return None
    if revocation_repository.is_token_revoked(token):
        return None
    email = decode_access_token(token)
    if not email:
        return None
    if revocation_repository.is_user_revoked(email):
        return None
    return user_repository.get_user_by_email(email)


def revoke_token(token: str) -> None:
    revocation_repository.revoke_token(token)


def revoke_target(target_type: str, target_id: str, reason: str) -> dict:
    if target_type == "user":
        return revocation_repository.revoke_user(target_id, reason)
    if target_type == "source":
        return revocation_repository.revoke_source(target_id, reason)
    if target_type == "case":
        return revocation_repository.revoke_case(target_id, reason)
    raise ValueError(f"Unsupported revocation target_type: {target_type}")


def restore_target(target_type: str, target_id: str) -> bool:
    if target_type == "user":
        return revocation_repository.restore_user(target_id)
    if target_type == "source":
        return revocation_repository.restore_source(target_id)
    if target_type == "case":
        return revocation_repository.restore_case(target_id)
    raise ValueError(f"Unsupported revocation target_type: {target_type}")


def _verify_account_and_case_scope(
    user: dict,
    case_id: str,
    account_id: str | None,
    source_ids: list[str],
) -> None:
    """Enforce account, case, and source access and immediate revocation checks."""
    _ensure_policy_service()

    if revocation_repository.is_user_revoked(user["email"]):
        raise AccessRevokedError("User access has been revoked")

    if revocation_repository.is_case_revoked(case_id):
        raise AccessRevokedError(f"Access to case '{case_id}' has been revoked")

    for source_id in source_ids:
        if revocation_repository.is_source_revoked(source_id):
            raise AccessRevokedError(
                f"Knowledge source '{source_id}' has been withdrawn or revoked"
            )

    if user["role"] != "administrator":
        allowed_accounts = user.get("allowed_accounts")
        if allowed_accounts is not None and account_id is not None:
            if account_id not in allowed_accounts:
                raise InsufficientScopeError(
                    f"Cross-account access denied for account '{account_id}'"
                )

        allowed_cases = user.get("allowed_cases")
        if allowed_cases is not None and case_id not in allowed_cases:
            raise InsufficientScopeError(
                f"User does not have access to case '{case_id}'"
            )


def verify_retrieval_access(
    user: dict,
    *,
    case_id: str,
    account_id: str | None = None,
    source_ids: list[str] | None = None,
) -> None:
    """Verify role, account, case, and source permissions before knowledge retrieval."""
    if user["role"] not in RETRIEVAL_ALLOWED_ROLES:
        raise InsufficientScopeError("Role is not permitted to perform retrieval")
    _verify_account_and_case_scope(user, case_id, account_id, source_ids or [])


def verify_export_access(
    user: dict,
    *,
    case_id: str,
    account_id: str | None = None,
    source_ids: list[str] | None = None,
    approved_by_role: str | None = None,
    requires_technical_approval: bool = False,
) -> None:
    """Re-verify permissions and revocations immediately before customer text export."""
    if user["role"] not in EXPORT_ALLOWED_ROLES:
        raise InsufficientScopeError(
            f"Role '{user['role']}' is not permitted to export customer responses"
        )
    _verify_account_and_case_scope(user, case_id, account_id, source_ids or [])

    if requires_technical_approval and approved_by_role != "technical_approver":
        raise InsufficientScopeError(
            "Technical content requires approval from a technical_approver before export"
        )
