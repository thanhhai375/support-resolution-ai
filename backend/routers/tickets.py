from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy import func

from main import get_db, TicketCreateRequest, TicketApprovalRequest
from models import Ticket, Product, Category
from uuid import uuid4

router = APIRouter(prefix="/api/tickets", tags=["Tickets Management"])

# 1. POST /api/tickets: Tạo ticket mới
@router.post("", status_code=201)
async def create_ticket(
    payload: TicketCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    # Kiểm tra sản phẩm
    product_result = await db.execute(
        select(Product).where(Product.id == payload.product_id)
    )
    product = product_result.scalars().first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Kiểm tra danh mục
    category_result = await db.execute(
        select(Category).where(Category.id == payload.category_id)
    )
    category = category_result.scalars().first()

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Chuẩn hóa mức ưu tiên
    priority = (payload.priority or "MEDIUM").upper()
    if priority == "URGENT":
        priority = "CRITICAL"

    if priority not in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
        raise HTTPException(status_code=400, detail="Invalid priority")

    # Tạo ticket
    new_ticket = Ticket(
    ticket_number=f"TK-{uuid4().hex[:8].upper()}",
    subject=payload.subject,
    description=payload.description,
    product_id=payload.product_id,
    category_id=payload.category_id,
    priority=priority,
    created_by=payload.created_by,
    status="OPEN",
    is_hazard_escalated=payload.is_hazard_escalated,
    hazard_reason=(
        payload.hazard_reason
        if payload.is_hazard_escalated
        else None
    )
)

    db.add(new_ticket)
    await db.commit()
    await db.refresh(new_ticket)

    return {
        "message": "Ticket created successfully",
        "data": {
            "id": str(new_ticket.id),
            "ticket_number": new_ticket.ticket_number,
            "subject": new_ticket.subject,
            "description": new_ticket.description,
            "product_id": str(new_ticket.product_id),
            "product_name": product.name,
            "category_id": str(new_ticket.category_id),
            "status": new_ticket.status,
            "priority": new_ticket.priority,
            "created_by": new_ticket.created_by,
            "created_at": new_ticket.created_at.isoformat(),    
            "is_hazard_escalated": new_ticket.is_hazard_escalated,
            "hazard_reason": new_ticket.hazard_reason,
        }
    }

# 2. GET /api/tickets: Lấy danh sách ticket

@router.get("")
async def get_tickets(
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    category_id: Optional[UUID] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Ticket, Product.name.label("product_name")).join(
    Product, Ticket.product_id == Product.id
)

    if category_id:
        query = query.where(Ticket.category_id == category_id)

    if status:
        query = query.where(Ticket.status == status.upper())

    # Đếm tổng số ticket trước khi phân trang
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Lấy danh sách ticket
    query = query.order_by(Ticket.created_at.desc())
    query = query.offset(page * size).limit(size)

    result = await db.execute(query)
    tickets = result.all()

    return {
        "page": page,
        "size": size,
        "total": total,
        "items": [
            {
                "id": str(ticket.id),
                "ticket_number": ticket.ticket_number,
                "subject": ticket.subject,
                "description": ticket.description,
                "product_id": str(ticket.product_id),
                "product_name": product_name,
                "category_id": str(ticket.category_id),
                "serial_number": ticket.serial_number,
                "firmware_version": ticket.firmware_version,
                "status": ticket.status,
                "priority": ticket.priority,
                "is_hazard_escalated": ticket.is_hazard_escalated,
                "hazard_reason": ticket.hazard_reason,
                "created_by": ticket.created_by,
                "assigned_to": ticket.assigned_to,
                "created_at": ticket.created_at.isoformat(),
                "updated_at": ticket.updated_at.isoformat()
            }
            for ticket, product_name in tickets
        ]
    }


# 3. GET /api/tickets/{id}: Lấy chi tiết ticket kèm messages
# GET /api/tickets/options: Lấy danh sách sản phẩm và danh mục
@router.get("/options")
async def get_ticket_options(db: AsyncSession = Depends(get_db)):
    product_result = await db.execute(
        select(Product).order_by(Product.name)
    )
    products = product_result.scalars().all()

    category_result = await db.execute(
        select(Category).order_by(Category.name)
    )
    categories = category_result.scalars().all()

    return {
        "products": [
            {
                "id": str(product.id),
                "name": product.name
            }
            for product in products
        ],
        "categories": [
            {
                "id": str(category.id),
                "name": category.name
            }
            for category in categories
        ]
    }
@router.get("/{ticket_id}")
async def get_ticket_detail(ticket_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalars().first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    msg_result = await db.execute(select(Message).where(Message.ticket_id == ticket_id))
    messages = msg_result.scalars().all()
    
    return {
        "id": ticket.id,
        "title": ticket.title,
        "description": ticket.description,
        "status": ticket.status,
        "priority": ticket.priority,
        "created_by": ticket.created_by,
        "messages": messages
    }
@router.patch("/{ticket_id}/safety")
async def update_ticket_safety(
    ticket_id: UUID,
    is_hazard_escalated: bool = Query(...),
    hazard_reason: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id)
    )
    ticket = result.scalars().first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.is_hazard_escalated = is_hazard_escalated
    ticket.hazard_reason = hazard_reason if is_hazard_escalated else None
    ticket.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(ticket)

    return {
        "message": "Safety information updated successfully",
        "data": {
            "id": str(ticket.id),
            "is_hazard_escalated": ticket.is_hazard_escalated,
            "hazard_reason": ticket.hazard_reason
        }
    }

# 4. PATCH /api/tickets/{id}/approve: Duyệt ticket
@router.patch("/{ticket_id}/approve")
async def approve_ticket_response(
    ticket_id: UUID, 
    payload: TicketApprovalRequest, 
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalars().first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    ticket.status = "resolved"
    ticket.assigned_to = payload.approver_id
    ticket.resolved_at = datetime.utcnow()
    ticket.updated_at = datetime.utcnow()
    
    approved_message = Message(
        ticket_id=ticket.id,
        sender_id=payload.approver_id,
        sender_type="agent",
        content=payload.approved_text,
        is_internal=False
    )
    db.add(approved_message)
    
    await db.commit()
    await db.refresh(ticket)
    
    return {
        "message": "Ticket response approved and exported successfully.",
        "data": {
            "id": ticket.id,
            "status": ticket.status,
            "resolvedAt": ticket.resolved_at,
            "approvedText": payload.approved_text
        }
    }