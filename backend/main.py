import os
from pathlib import Path
from fastapi import FastAPI
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

# Đăng ký router ở cuối file để tránh vòng lặp import
from routers import tickets, copilot
app.include_router(tickets.router)
app.include_router(copilot.router)

@app.get("/")
def root():
    return {"message": "SongNhat Copilot Backend is running successfully!"}