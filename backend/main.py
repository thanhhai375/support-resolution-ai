from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Cấu hình Database PostgreSQL
DATABASE_URL = "postgresql+asyncpg://postgres:secretpassword@localhost:5432/support_resolution_db"

engine = create_async_engine(DATABASE_URL, echo=True, future=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

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
from routers import tickets
app.include_router(tickets.router)

@app.get("/")
def root():
    return {"message": "SongNhat Copilot Backend is running successfully!"}