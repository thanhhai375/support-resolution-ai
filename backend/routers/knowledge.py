from enum import Enum
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional

from main import get_db, PassageListResponse, PassageResponse, CitationResponse
from models import KnowledgePassage, Product

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge & Citations"])

class ProductFilter(str, Enum):
    MOTORS = "MOTORS"
    DRIVES = "DRIVES"

    @classmethod
    def _missing_(cls, value: object):
        # Tự động chuẩn hóa mọi biến thể chữ hoa/thường ('motors', 'Motors' -> 'MOTORS')
        if isinstance(value, str):
            upper_val = value.strip().upper()
            for member in cls:
                if member.value == upper_val:
                    return member
        return None

@router.get("/passages", response_model=PassageListResponse)
async def get_approved_passages(
    product: Optional[ProductFilter] = Query(
        None, description="Lọc theo dòng sản phẩm: MOTORS hoặc DRIVES"
    ),
    q: Optional[str] = Query(
        None, description="Từ khóa tìm kiếm trong nội dung đoạn trích"
    ),
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(KnowledgePassage, Product)
        .join(Product, KnowledgePassage.product_id == Product.id)
        .where(KnowledgePassage.is_approved == True)
    )

    if product:
        stmt = stmt.where(Product.code == product.value)

    if q:
        stmt = stmt.where(KnowledgePassage.passage_content.ilike(f"%{q}%"))

    stmt = stmt.offset(page * size).limit(size)
    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for passage, prod in rows:
        section_parts = [p for p in [passage.section_number, passage.section_name] if p]
        formatted_section = " - ".join(section_parts) if section_parts else "N/A"

        meta = passage.metadata_ or {}
        doc_version = meta.get("version") or passage.document_code or "v1.0"

        items.append(
            PassageResponse(
                id=passage.id,
                product_code=prod.code,
                product_name=prod.name,
                content=passage.passage_content,
                is_approved=passage.is_approved,
                citation=CitationResponse(
                    document_title=passage.document_name,
                    version=doc_version,
                    section=formatted_section,
                    page_number=passage.page_number
                )
            )
        )

    return PassageListResponse(total=len(items), items=items)