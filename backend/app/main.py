"""Single FastAPI entry point for the Support Resolution Copilot backend.

Database setup and legacy CRM routers are consolidated here so every backend
module imports the same Base, engine and get_db dependency.
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from uuid import UUID

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings

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


# Load backend/.env regardless of the process working directory.
BACKEND_DIR = Path(__file__).resolve().parent.parent
env_path = BACKEND_DIR / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

try:
    from app.migrations.runner import run_migrations
except ImportError:
    try:
        from migrations.runner import run_migrations
    except ImportError:
        run_migrations = None

_pg_user = os.getenv("POSTGRES_USER", "songnhat")
_pg_pass = os.getenv("POSTGRES_PASSWORD", "songnhat_dev")
_pg_host = os.getenv("POSTGRES_HOST", "localhost")
_pg_port = os.getenv("POSTGRES_PORT", "5432")
_pg_db = os.getenv("POSTGRES_DB", "songnhat_copilot")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql+asyncpg://{_pg_user}:{_pg_pass}@{_pg_host}:{_pg_port}/{_pg_db}",
)
# Compose commonly supplies postgresql://; async SQLAlchemy requires an async driver.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+asyncpg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+asyncpg://" + DATABASE_URL[len("postgresql://"):]

# The one canonical SQLAlchemy metadata registry for all backend models.
Base = declarative_base()


def _create_engine(url: str):
    kwargs = {"echo": False, "future": True}
    if url.startswith("sqlite") and ":memory:" in url:
        kwargs.update(
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_async_engine(url, **kwargs)


try:
    engine = _create_engine(DATABASE_URL)
except Exception:
    # Local fallback when PostgreSQL's async driver is not installed.
    DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    engine = _create_engine(DATABASE_URL)

AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)
logger = logging.getLogger(__name__)
_db_initialized = False


async def ensure_db_initialized():
    """Run database migrations once for the shared application engine."""
    global _db_initialized, engine, AsyncSessionLocal, DATABASE_URL
    if _db_initialized:
        return

    # Import/register ORM models and API routers only after app.main has finished
    # defining Base/get_db; this avoids the models -> app.main circular import.
    register_backend_components()

    if run_migrations:
        try:
            await run_migrations(engine)
        except Exception as exc:
            if "postgresql" in str(getattr(engine, "url", "")):
                logger.warning(
                    "Không thể kết nối PostgreSQL (%s). Chuyển sang SQLite in-memory.",
                    exc,
                )
                await engine.dispose()
                DATABASE_URL = "sqlite+aiosqlite:///:memory:"
                engine = _create_engine(DATABASE_URL)
                AsyncSessionLocal = sessionmaker(
                    bind=engine, class_=AsyncSession, expire_on_commit=False
                )
                await run_migrations(engine)
            else:
                raise
    _db_initialized = True


async def get_db():
    await ensure_db_initialized()
    async with AsyncSessionLocal() as session:
        yield session


# Existing request schemas retained for compatibility with backend clients.
class TicketCreateRequest(BaseModel):
    title: str
    description: str
    category_id: Optional[UUID] = None
    priority: Optional[str] = "medium"
    created_by: UUID


class TicketApprovalRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    approver_id: UUID = Field(..., alias="approverId")
    approved_text: str = Field(..., alias="approvedText")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_db_initialized()
    yield
    await engine.dispose()


app = FastAPI(
    title="Support Resolution Copilot API",
    version="2.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "SongNhat Copilot Backend is running successfully!"}



_backend_components_registered = False


def register_backend_components():
    """Register every API module once, after the canonical Base is available."""
    global _backend_components_registered
    if _backend_components_registered:
        return

    import models  # noqa: F401 — register ORM tables on Base.metadata
    from routers import copilot, knowledge, tickets
    from app.api.v1 import auth
    from app.api.v1.ingestion import router as ingestion_router
    from app.api.v1.camunda_workflow import (
        approval_router as copilot_approval_router,
        router as camunda_workflow_router,
    )

    app.include_router(tickets.router)

    # The Camunda router owns POST /api/copilot/analyze (same pipeline + DB + Camunda start)
    # so it must be registered BEFORE the legacy copilot router, which has the same path.
    # Both use the CRM-40 role guard, so analyze/status stay authenticated.
    app.include_router(camunda_workflow_router, dependencies=[Depends(_copilot_role_guard)])
    app.include_router(copilot.router, dependencies=[Depends(_copilot_role_guard)])
    app.include_router(knowledge.router)
    app.include_router(auth.router, prefix="/api")
    app.include_router(ingestion_router)
    app.include_router(copilot_approval_router)

    bearer = HTTPBearer(auto_error=False)

    @app.delete("/api/auth/revoke", status_code=204, tags=["auth"])
    def revoke_current_access_token(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
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

    _backend_components_registered = True
register_backend_components()

if __name__ == "__main__":
    # Register routes before serving when run directly via this module.
    register_backend_components()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
