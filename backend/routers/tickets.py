from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

try:
    from main import get_db
except ImportError:
    from backend.main import get_db

try:
    from models import Ticket, Product, Category
except ImportError:
    from backend.models import Ticket, Product, Category

from app.schemas.copilot import CopilotAnalyzeRequest, SupportPackageOut
from app.services.copilot_engine import run_copilot_pipeline

router = APIRouter(prefix="/api/tickets", tags=["Tickets Management"])

VALID_STATUSES = {"OPEN", "IN_PROGRESS", "PENDING", "RESOLVED", "CLOSED"}
VALID_PRIORITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
PRIORITY_ALIASES = {"URGENT": "CRITICAL"}


class TicketCreateSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ticket_number: Optional[str] = None
    product_id: Optional[UUID] = None
    product_code: Optional[str] = None
    category_id: Optional[UUID] = None
    category_code: Optional[str] = None
    subject: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None
    is_hazard_escalated: bool = False
    hazard_reason: Optional[str] = None
    priority: Optional[str] = "MEDIUM"
    status: Optional[str] = "OPEN"
    created_by: Optional[Any] = None
    assigned_to: Optional[Any] = None


class TicketUpdateSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    subject: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None
    is_hazard_escalated: Optional[bool] = None
    hazard_reason: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    product_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    assigned_to: Optional[Any] = None


def _normalize_status(value: Optional[str], default: str = "OPEN") -> str:
    if not value:
        return default
    upper_val = value.strip().upper()
    if upper_val not in VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status '{value}'. Allowed: {sorted(VALID_STATUSES)}",
        )
    return upper_val


def _normalize_priority(value: Optional[str], default: str = "MEDIUM") -> str:
    if not value:
        return default
    upper_val = value.strip().upper()
    upper_val = PRIORITY_ALIASES.get(upper_val, upper_val)
    if upper_val not in VALID_PRIORITIES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid priority '{value}'. Allowed: {sorted(VALID_PRIORITIES)}",
        )
    return upper_val


def _validate_hazard(is_hazard: bool, reason: Optional[str]) -> tuple[bool, Optional[str]]:
    """Đảm bảo thỏa mãn ràng buộc chk_ticket_hazard_reason của PostgreSQL."""
    if is_hazard:
        clean_reason = (reason or "").strip()
        if not clean_reason:
            raise HTTPException(
                status_code=422,
                detail="hazard_reason is required when is_hazard_escalated is True",
            )
        return True, clean_reason
    return False, reason


def _serialize_ticket(ticket: Ticket) -> dict[str, Any]:
    return {
        "id": str(ticket.id),
        "ticket_number": ticket.ticket_number,
        "product_id": str(ticket.product_id) if ticket.product_id else None,
        "category_id": str(ticket.category_id) if ticket.category_id else None,
        "subject": ticket.subject,
        "title": ticket.subject,
        "description": ticket.description,
        "serial_number": ticket.serial_number,
        "firmware_version": ticket.firmware_version,
        "is_hazard_escalated": ticket.is_hazard_escalated,
        "hazard_reason": ticket.hazard_reason,
        "status": ticket.status,
        "priority": ticket.priority,
        "created_by": ticket.created_by,
        "assigned_to": ticket.assigned_to,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
    }


async def _resolve_product_and_category(
    db: AsyncSession,
    product_id: Optional[UUID] = None,
    product_code: Optional[str] = None,
    category_id: Optional[UUID] = None,
    category_code: Optional[str] = None,
) -> tuple[UUID, UUID]:
    """Lấy product_id & category_id hợp lệ từ bảng products/categories (tự seed theo schema.sql nếu bảng trống)."""
    product = None
    if product_id:
        res = await db.execute(select(Product).where(Product.id == product_id))
        product = res.scalars().first()
    if not product and product_code:
        res = await db.execute(select(Product).where(Product.code == product_code.upper()))
        product = res.scalars().first()
    if not product:
        res = await db.execute(select(Product).order_by(Product.code.asc()))
        product = res.scalars().first()
    if not product:
        product = Product(
            code="MOTORS",
            name="Động cơ (Motors)",
            description="Quản lý thông tin và yêu cầu hỗ trợ kỹ thuật liên quan đến động cơ.",
        )
        db.add(product)
        await db.flush()

    category = None
    if category_id:
        res = await db.execute(select(Category).where(Category.id == category_id))
        category = res.scalars().first()
    if not category and category_code:
        res = await db.execute(select(Category).where(Category.code == category_code.upper()))
        category = res.scalars().first()
    if not category:
        res = await db.execute(select(Category).order_by(Category.code.asc()))
        category = res.scalars().first()
    if not category:
        category = Category(
            code="DOCUMENT_REQUEST",
            name="Yêu cầu tài liệu",
            description="Các yêu cầu cung cấp tài liệu và hướng dẫn kỹ thuật.",
        )
        db.add(category)
        await db.flush()

    return product.id, category.id


# 1. POST /api/tickets: Tạo ticket mới -> 201 Created
@router.post("", status_code=201)
async def create_ticket(payload: TicketCreateSchema, db: AsyncSession = Depends(get_db)):
    resolved_subject = (payload.subject or payload.title or "").strip()
    if not resolved_subject:
        raise HTTPException(status_code=422, detail="Field 'subject' or 'title' is required")

    raw_priority = (payload.priority or "").strip().upper()
    resolved_status = _normalize_status(payload.status, "OPEN")
    resolved_priority = _normalize_priority(payload.priority, "MEDIUM")

    is_hazard_input = payload.is_hazard_escalated or (raw_priority == "URGENT")
    hazard_reason_input = payload.hazard_reason
    if is_hazard_input and not (hazard_reason_input or "").strip() and raw_priority == "URGENT":
        hazard_reason_input = (payload.description or resolved_subject or "Urgent safety hazard escalated").strip()

    is_hazard, hazard_reason = _validate_hazard(
        is_hazard_input, hazard_reason_input
    )

    raw_ticket_number = (payload.ticket_number or "").strip()
    resolved_ticket_number = (
        raw_ticket_number
        if raw_ticket_number and raw_ticket_number.lower() != "string"
        else f"TK-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    )

    valid_product_id, valid_category_id = await _resolve_product_and_category(
        db=db,
        product_id=payload.product_id,
        product_code=payload.product_code,
        category_id=payload.category_id,
        category_code=payload.category_code,
    )

    new_ticket = Ticket(
        ticket_number=resolved_ticket_number,
        product_id=valid_product_id,
        category_id=valid_category_id,
        subject=resolved_subject,
        description=payload.description,
        serial_number=payload.serial_number,
        firmware_version=payload.firmware_version,
        is_hazard_escalated=is_hazard,
        hazard_reason=hazard_reason,
        status=resolved_status,
        priority=resolved_priority,
        created_by=str(payload.created_by) if payload.created_by is not None else None,
        assigned_to=str(payload.assigned_to) if payload.assigned_to is not None else None,
    )

    db.add(new_ticket)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Ticket number '{resolved_ticket_number}' already exists",
        )
    await db.refresh(new_ticket)

    serialized = _serialize_ticket(new_ticket)
    return {
        **serialized,
        "message": "Ticket created successfully",
        "data": serialized,
    }


# 2. GET /api/tickets: Lấy danh sách ticket -> 200 OK
@router.get("", status_code=200)
async def get_tickets(
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    product_id: Optional[UUID] = None,
    category_id: Optional[UUID] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    is_hazard_escalated: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Ticket)
    if product_id:
        query = query.where(Ticket.product_id == product_id)
    if category_id:
        query = query.where(Ticket.category_id == category_id)
    if status:
        query = query.where(Ticket.status == _normalize_status(status))
    if priority:
        query = query.where(Ticket.priority == _normalize_priority(priority))
    if is_hazard_escalated is not None:
        query = query.where(Ticket.is_hazard_escalated == is_hazard_escalated)

    query = query.order_by(Ticket.created_at.desc()).offset(page * size).limit(size)
    result = await db.execute(query)
    tickets = result.scalars().all()
    items = [_serialize_ticket(t) for t in tickets]

    return {
        "page": page,
        "size": size,
        "total": len(items),
        "items": items,
    }


# 3. GET /api/tickets/{ticket_id}: Lấy chi tiết ticket -> 200 OK
@router.get("/{ticket_id}", status_code=200)
async def get_ticket_detail(ticket_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalars().first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return _serialize_ticket(ticket)


# 4. PUT & PATCH /api/tickets/{ticket_id}: Cập nhật ticket -> 200 OK
@router.put("/{ticket_id}", status_code=200)
@router.patch("/{ticket_id}", status_code=200)
async def update_ticket(
    ticket_id: UUID,
    payload: TicketUpdateSchema,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalars().first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    new_subject = payload.subject or payload.title
    if new_subject is not None:
        clean_subject = new_subject.strip()
        if not clean_subject:
            raise HTTPException(status_code=422, detail="Subject cannot be empty")
        ticket.subject = clean_subject

    if payload.description is not None:
        ticket.description = payload.description
    if payload.serial_number is not None:
        ticket.serial_number = payload.serial_number
    if payload.firmware_version is not None:
        ticket.firmware_version = payload.firmware_version
    if payload.priority is not None:
        ticket.priority = _normalize_priority(payload.priority)
    if payload.status is not None:
        ticket.status = _normalize_status(payload.status)
    if payload.assigned_to is not None:
        ticket.assigned_to = str(payload.assigned_to)

    if payload.is_hazard_escalated is not None or payload.hazard_reason is not None:
        target_hazard = (
            payload.is_hazard_escalated
            if payload.is_hazard_escalated is not None
            else ticket.is_hazard_escalated
        )
        target_reason = (
            payload.hazard_reason
            if payload.hazard_reason is not None
            else ticket.hazard_reason
        )
        is_hazard, hazard_reason = _validate_hazard(target_hazard, target_reason)
        ticket.is_hazard_escalated = is_hazard
        ticket.hazard_reason = hazard_reason

    if payload.product_id is not None or payload.category_id is not None:
        valid_prod, valid_cat = await _resolve_product_and_category(
            db=db,
            product_id=payload.product_id or ticket.product_id,
            category_id=payload.category_id or ticket.category_id,
        )
        ticket.product_id = valid_prod
        ticket.category_id = valid_cat

    ticket.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(ticket)

    serialized = _serialize_ticket(ticket)
    return {
        **serialized,
        "message": "Ticket updated successfully",
        "data": serialized,
    }


# 5. PATCH /api/tickets/{ticket_id}/approve: Duyệt ticket -> 200 OK
@router.patch("/{ticket_id}/approve", status_code=200)
async def approve_ticket_response(
    ticket_id: UUID,
    payload: Optional[dict[str, Any]] = Body(default=None),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalars().first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.status = "RESOLVED"
    if payload:
        approver = payload.get("approver_id") or payload.get("approverId")
        if approver:
            ticket.assigned_to = str(approver)
    ticket.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(ticket)

    serialized = _serialize_ticket(ticket)
    return {
        **serialized,
        "message": "Ticket response approved successfully.",
        "data": serialized,
    }


# 6. DELETE /api/tickets/{ticket_id}: Xóa ticket -> 204 No Content
@router.delete("/{ticket_id}", status_code=204)
async def delete_ticket(ticket_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalars().first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    await db.delete(ticket)
    await db.commit()
    return Response(status_code=204)


# 7. POST /api/tickets/{ticket_id}/copilot/generate: Sinh Support Package cho ticket (Task CRM-28)
@router.post("/{ticket_id}/copilot/generate", response_model=SupportPackageOut)
async def generate_ticket_copilot_package(
    ticket_id: UUID,
    payload: Optional[CopilotAnalyzeRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """Sinh Support Package hoàn chỉnh cho ticket (SUP-01 - SUP-08)."""
    description = ""
    if payload and payload.ticket_description and payload.ticket_description.strip():
        description = payload.ticket_description
    else:
        try:
            ticket_result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
            ticket = ticket_result.scalars().first()
            if ticket:
                description = (
                    f"{ticket.subject}\n{ticket.description}"
                    if ticket.description
                    else ticket.subject
                )
            else:
                raise HTTPException(status_code=404, detail="Ticket not found")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=404, detail="Ticket not found or database not initialized"
            )

    package = await run_copilot_pipeline(
        ticket_description=description,
        ticket_id=ticket_id,
        db=db,
    )
    return package