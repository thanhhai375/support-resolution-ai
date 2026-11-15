"""API router cho Copilot Engine độc lập (Task CRM-28 & Postman TC-21 - TC-25)."""

from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from main import get_db
except ImportError:
    from backend.main import get_db

from app.schemas.copilot import CopilotAnalyzeRequest, SupportPackageOut
from app.services.copilot_engine import run_copilot_pipeline

router = APIRouter(prefix="/api/copilot", tags=["Copilot Engine"])


@router.post("/analyze", response_model=SupportPackageOut)
async def analyze_copilot_request(
    payload: CopilotAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Phân tích nội dung ticket độc lập và sinh Support Package chuẩn SongNhat RFP.

    Hỗ trợ kiểm thử Postman TC-21, TC-22, TC-23, TC-24, TC-25.
    """
    return await run_copilot_pipeline(
        ticket_description=payload.ticket_description,
        db=db,
    )
