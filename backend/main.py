import os
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base

env_path = Path(__file__).resolve().parent / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# Tự động lấy DATABASE_URL hoặc ghép từ các biến POSTGRES_* có sẵn trong .env
_pg_user = os.getenv("POSTGRES_USER", "songnhat")
_pg_pass = os.getenv("POSTGRES_PASSWORD", "songnhat_dev")
_pg_host = os.getenv("POSTGRES_HOST", "localhost")
_pg_port = os.getenv("POSTGRES_PORT", "5432")
_pg_db = os.getenv("POSTGRES_DB", "songnhat_copilot")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql+asyncpg://{_pg_user}:{_pg_pass}@{_pg_host}:{_pg_port}/{_pg_db}",
)
Base = declarative_base()

try:
    engine = create_async_engine(DATABASE_URL, echo=True, future=True)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
except Exception:
    # Fallback to in-memory sqlite if asyncpg driver is not available locally
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# Pydantic Schemas
class TicketCreateRequest(BaseModel):
    title: str
    description: str
    category_id: Optional[UUID] = None
    priority: Optional[str] = "medium"
    created_by: UUID

class TicketApprovalRequest(BaseModel):
    approver_id: UUID = Field(..., alias="approverId")
    approved_text: str = Field(..., alias="approvedText")

    class Config:
        populate_by_name = True

# Khởi tạo ứng dụng FastAPI
app = FastAPI(
    title="SongNhat Support Resolution Copilot API",
    version="2.0.0"
)


@app.get("/")
def root():
    return {"message": "SongNhat Copilot Backend is running successfully!"}

# Import và đăng ký các router
from routers import tickets, copilot, knowledge
from app.api.v1 import auth  # Thêm import auth router từ thư mục app/api/v1/auth.py

app.include_router(tickets.router)
# CRM-40: Copilot endpoints are authenticated for all four operational roles.
# Use the existing auth vocabulary here; the knowledge/ticket routers additionally
# adapt CRM-40 enum values to that vocabulary for endpoint-specific policies.
from app.api.deps import get_current_user, require_role as _require_role
from app.services import auth_service

_copilot_access = _require_role(
    "support_agent", "technical_approver", "knowledge_steward", "administrator"
)
_CRM40_ROLE_TO_LEGACY = {
    "STAFF": "support_agent",
    "ENGINEER": "technical_approver",
    "MANAGER": "knowledge_steward",
    "ADMIN": "administrator",
}

def _copilot_role_guard(current_user: dict = Depends(get_current_user)):
    normalized_user = dict(current_user)
    normalized_user["role"] = _CRM40_ROLE_TO_LEGACY.get(
        normalized_user.get("role"), normalized_user.get("role")
    )
    return _copilot_access(normalized_user)

app.include_router(copilot.router, dependencies=[Depends(_copilot_role_guard)])
app.include_router(knowledge.router)
app.include_router(auth.router, prefix="/api")  # Đăng ký auth router với prefix /api[cite: 2]

# CRM-40: canonical DELETE logout endpoint. The existing auth service performs
# the same immediate revocation check used by get_current_user on every request.

_bearer = HTTPBearer(auto_error=False)

@app.delete("/api/auth/revoke", status_code=204, tags=["auth"])
def revoke_current_access_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    current_user: dict = Depends(get_current_user),
):
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    auth_service.revoke_token(credentials.credentials)
    return None
