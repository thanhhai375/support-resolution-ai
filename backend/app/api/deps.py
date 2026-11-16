from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.services import auth_service

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """Extract and validate the current user from the Bearer token, or raise 401."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    user = auth_service.get_user_from_token(credentials.credentials)
    if user is None:
        raise unauthorized
    return user


def require_role(*allowed_roles: str) -> Callable[..., dict]:
    """Dependency that restricts endpoint access to users with one of `allowed_roles`.

    Raises 401 if unauthenticated and 403 Forbidden if the user's role is not allowed.
    """
    unknown = set(allowed_roles) - set(settings.valid_roles)
    if not allowed_roles or unknown:
        raise ValueError(
            f"Invalid role(s): {sorted(unknown) or 'none provided'}. "
            f"Valid roles: {settings.valid_roles}"
        )

    def checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: insufficient permissions",
            )
        return current_user

    return checker
