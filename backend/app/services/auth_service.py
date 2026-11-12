"""Authentication business logic: credential verification, token issuance, and token resolution."""
from app.core.security import create_access_token, decode_access_token, verify_password
from app.repositories import user_repository


class InvalidCredentialsError(Exception):
    """Raised when the email or password is invalid."""


def login(email: str, password: str) -> str:
    """Verify credentials and return a signed JWT access token."""
    user = user_repository.get_user_by_email(email)
    if user is None or not verify_password(password, user["password_hash"]):
        raise InvalidCredentialsError
    return create_access_token(user["email"])


def get_user_from_token(token: str) -> dict | None:
    """Resolve the user record for a valid JWT token, or return None."""
    email = decode_access_token(token)
    if not email:
        return None
    return user_repository.get_user_by_email(email)
