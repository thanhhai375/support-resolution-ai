from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    role: str
    full_name: str


class RevokeTargetRequest(BaseModel):
    target_type: Literal["user", "source", "case"]
    target_id: str = Field(..., min_length=1)
    reason: str = "Administrative revocation"


class CacheCleanupRequest(BaseModel):
    target_type: Literal["user", "source", "case"]
    target_id: str = Field(..., min_length=1)


class RevocationRecordResponse(BaseModel):
    target_type: str
    target_id: str
    reason: str
    revoked_at: str
    cache_cleanup_due_at: str
    cache_cleaned: bool


class RetrievalAccessCheckRequest(BaseModel):
    case_id: str = Field(..., min_length=1)
    account_id: str | None = None
    source_ids: list[str] = Field(default_factory=list)


class ExportAccessCheckRequest(BaseModel):
    case_id: str = Field(..., min_length=1)
    account_id: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    approved_by_role: str | None = None
    requires_technical_approval: bool = False


class AccessCheckResponse(BaseModel):
    allowed: bool
    stage: Literal["retrieval", "export"]
    user_email: str
    role: str
    case_id: str
