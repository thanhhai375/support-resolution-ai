import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

try:
    from migrations.runner import run_migrations
except ImportError:
    try:
        from backend.migrations.runner import run_migrations
    except ImportError:
        run_migrations = None

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
    engine = create_async_engine(DATABASE_URL, echo=False, future=True)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
except Exception:
    # Fallback to shared in-memory sqlite if asyncpg driver is not available locally
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

logger = logging.getLogger(__name__)
_db_initialized = False


async def ensure_db_initialized():
    """Khởi tạo cấu trúc bảng + migration pg_trgm/GIN index.
    
    KHÔNG seed dữ liệu — bảng knowledge_passages giữ nguyên rỗng
    cho đến khi CRM-42 nạp CSV thật. Retriever sẽ fallback về mock
    khi bảng rỗng (hành vi đúng theo thiết kế).
    """
    global _db_initialized, engine, AsyncSessionLocal
    if _db_initialized:
        return
    if run_migrations:
        try:
            await run_migrations(engine)
        except Exception as exc:
            if "postgresql" in str(getattr(engine, "url", "")):
                logger.warning("Không thể kết nối PostgreSQL (%s). Chuyển sang fallback SQLite in-memory.", exc)
                engine = create_async_engine(
                    "sqlite+aiosqlite:///:memory:",
                    echo=False,
                    future=True,
                    connect_args={"check_same_thread": False},
                    poolclass=StaticPool,
                )
                AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
                await run_migrations(engine)
    _db_initialized = True


async def get_db():
    await ensure_db_initialized()
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
    model_config = ConfigDict(populate_by_name=True)

    approver_id: UUID = Field(..., alias="approverId")
    approved_text: str = Field(..., alias="approvedText")

# ——— Lifespan context manager (thay thế @on_event deprecated) ———
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Khởi động: tạo bảng + chạy migration pg_trgm/GIN index.
    
    Không seed data — bảng knowledge_passages rỗng cho đến khi CRM-42 nạp CSV.
    Dừng: cleanup tài nguyên (SQLAlchemy async tự quản lý pool).
    """
    await ensure_db_initialized()
    yield


# Khởi tạo ứng dụng FastAPI
app = FastAPI(
    title="SongNhat Support Resolution Copilot API",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/")
def root():
    return {"message": "SongNhat Copilot Backend is running successfully!"}
from routers import tickets, copilot, knowledge
app.include_router(tickets.router)
app.include_router(copilot.router)
app.include_router(knowledge.router)