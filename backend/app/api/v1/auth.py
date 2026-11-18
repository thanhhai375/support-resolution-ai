from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_bearer_token, get_current_user, require_role
from app.repositories import revocation_repository
from app.schemas.auth import (
    AccessCheckResponse,
    CacheCleanupRequest,
    ExportAccessCheckRequest,
    LoginRequest,
    RetrievalAccessCheckRequest,
    RevocationRecordResponse,
    RevokeTargetRequest,
    TokenResponse,
    UserResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    try:
        token = auth_service.login(body.email, body.password)
    except auth_service.PolicyServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except auth_service.AccessRevokedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )
    except auth_service.InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=token)


@router.post("/logout")
def logout(
    token: str = Depends(get_bearer_token),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Revoke the caller's active JWT token immediately."""
    auth_service.revoke_token(token)
    return {"message": "Token revoked", "email": current_user["email"]}


@router.get("/me", response_model=UserResponse)
def me(current_user: dict = Depends(get_current_user)) -> UserResponse:
    return UserResponse(**{k: current_user[k] for k in ("id", "email", "role", "full_name")})


@router.get("/admin/ping")
def admin_ping(current_user: dict = Depends(require_role("administrator"))) -> dict:
    """Administrator-only health check endpoint; returns 403 for non-admin roles."""
    return {"message": "pong", "email": current_user["email"]}


@router.post("/revocations", response_model=RevocationRecordResponse)
def create_revocation(
    body: RevokeTargetRequest,
    current_user: dict = Depends(
        require_role("administrator", "knowledge_steward")
    ),
) -> RevocationRecordResponse:
    """Revoke a user, case, or knowledge source immediately (SEC 04).

    `knowledge_steward` may only revoke `source` targets; `administrator` may
    revoke `user`, `source`, or `case` targets.
    """
    if current_user["role"] == "knowledge_steward" and body.target_type != "source":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="knowledge_steward may only revoke knowledge sources",
        )
    record = auth_service.revoke_target(body.target_type, body.target_id, body.reason)
    return RevocationRecordResponse(**record)


@router.post("/revocations/restore")
def restore_revocation(
    body: CacheCleanupRequest,
    _: dict = Depends(require_role("administrator")),
) -> dict:
    restored = auth_service.restore_target(body.target_type, body.target_id)
    return {"restored": restored, "target_type": body.target_type, "target_id": body.target_id}


@router.post("/revocations/cache-cleanup")
def complete_cache_cleanup(
    body: CacheCleanupRequest,
    _: dict = Depends(require_role("administrator", "knowledge_steward")),
) -> dict:
    cleaned = revocation_repository.mark_cache_cleaned(body.target_type, body.target_id)
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Revocation record not found",
        )
    return {"cache_cleaned": True, "target_type": body.target_type, "target_id": body.target_id}


@router.get("/revocations")
def list_revocations(
    _: dict = Depends(require_role("administrator")),
) -> dict:
    return revocation_repository.list_revocations()


@router.post("/access/retrieval-check", response_model=AccessCheckResponse)
def retrieval_access_check(
    body: RetrievalAccessCheckRequest,
    current_user: dict = Depends(get_current_user),
) -> AccessCheckResponse:
    """Verify role, account, case, and source permissions before retrieval (SEC 01)."""
    try:
        auth_service.verify_retrieval_access(
            current_user,
            case_id=body.case_id,
            account_id=body.account_id,
            source_ids=body.source_ids,
        )
    except auth_service.PolicyServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except (auth_service.AccessRevokedError, auth_service.InsufficientScopeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )
    return AccessCheckResponse(
        allowed=True,
        stage="retrieval",
        user_email=current_user["email"],
        role=current_user["role"],
        case_id=body.case_id,
    )


@router.post("/access/export-check", response_model=AccessCheckResponse)
def export_access_check(
    body: ExportAccessCheckRequest,
    current_user: dict = Depends(get_current_user),
) -> AccessCheckResponse:
    """Re-verify permissions and revocations immediately before customer export (SEC 01 / SEC 04 / REV 03)."""
    try:
        auth_service.verify_export_access(
            current_user,
            case_id=body.case_id,
            account_id=body.account_id,
            source_ids=body.source_ids,
            approved_by_role=body.approved_by_role,
            requires_technical_approval=body.requires_technical_approval,
        )
    except auth_service.PolicyServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except (auth_service.AccessRevokedError, auth_service.InsufficientScopeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )
    return AccessCheckResponse(
        allowed=True,
        stage="export",
        user_email=current_user["email"],
        role=current_user["role"],
        case_id=body.case_id,
    )
