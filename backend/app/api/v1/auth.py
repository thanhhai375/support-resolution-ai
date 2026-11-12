from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, require_role
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    try:
        token = auth_service.login(body.email, body.password)
    except auth_service.InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(current_user: dict = Depends(get_current_user)) -> UserResponse:
    return UserResponse(**{k: current_user[k] for k in ("id", "email", "role", "full_name")})


@router.get("/admin/ping")
def admin_ping(current_user: dict = Depends(require_role("admin"))) -> dict:
    """Admin-only health check endpoint; returns 403 for non-admin roles."""
    return {"message": "pong", "email": current_user["email"]}
