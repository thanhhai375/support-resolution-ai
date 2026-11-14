from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Cấu hình Database PostgreSQL
DATABASE_URL = "postgresql+asyncpg://songnhat:songnhat_dev@127.0.0.1:5432/songnhat_copilot"

engine = create_async_engine(DATABASE_URL, echo=True, future=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# Pydantic Schemas
class TicketCreateRequest(BaseModel):
    subject: str
    description: Optional[str] = None
    product_id: UUID
    category_id: UUID
    priority: Optional[str] = "MEDIUM"
    created_by: Optional[str] = None
    is_hazard_escalated: bool = False
    hazard_reason: Optional[str] = None

class TicketApprovalRequest(BaseModel):
    approver_id: str = Field(..., alias="approverId")
    approved_text: str = Field(..., alias="approvedText")

    class Config:
        populate_by_name = True

# Khởi tạo ứng dụng FastAPI
app = FastAPI(
    title="SongNhat Support Resolution Copilot API",
    version="2.0.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký router ở cuối file để tránh vòng lặp import
from routers import tickets
app.include_router(tickets.router)

@app.get("/")
def root():
    return {"message": "SongNhat Copilot Backend is running successfully!"}