from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional
from uuid import UUID
from datetime import datetime

from main import get_db, TicketCreateRequest, TicketApprovalRequest
from models import Ticket, Message

router = APIRouter(prefix="/api/tickets", tags=["Tickets Management"])

# 1. POST /api/tickets: Tạo ticket mới
@router.post("", status_code=201)
async def create_ticket(payload: TicketCreateRequest, db: AsyncSession = Depends(get_db)):
    new_ticket = Ticket(
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        category_id=payload.category_id,
        created_by=payload.created_by,
        status="open"
    )
    
    db.add(new_ticket)
    await db.commit()
    await db.refresh(new_ticket)
    
    # Tạo bản ghi message khởi tạo
    initial_message = Message(
        ticket_id=new_ticket.id,
        sender_id=payload.created_by,
        sender_type="user",
        content=payload.description,
        is_internal=False
    )
    db.add(initial_message)
    await db.commit()
    
    return {"message": "Ticket created successfully", "data": new_ticket}

# 2. GET /api/tickets: Lấy danh sách ticket
@router.get("")
async def get_tickets(
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    category_id: Optional[UUID] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Ticket)
    if category_id:
        query = query.where(Ticket.category_id == category_id)
    if status:
        query = query.where(Ticket.status == status)
        
    query = query.offset(page * size).limit(size)
    result = await db.execute(query)
    tickets = result.scalars().all()
    
    return {
        "page": page,
        "size": size,
        "total": len(tickets),
        "items": tickets
    }

# 3. GET /api/tickets/{id}: Lấy chi tiết ticket kèm messages
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