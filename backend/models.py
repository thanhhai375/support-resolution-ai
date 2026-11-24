import enum
import uuid
from typing import Any
from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Enum as SQLEnum,
    Uuid as UUID,
    func,
)

from app.main import Base


class UserRole(str, enum.Enum):
    STAFF = "STAFF"
    ENGINEER = "ENGINEER"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(150), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    role = Column(
        SQLEnum(UserRole, name="userrole", native_enum=True, validate_strings=True),
        nullable=False,
        default=UserRole.STAFF,
        server_default=UserRole.STAFF.value,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __init__(self, **kwargs: Any) -> None:
        if "role" in kwargs and isinstance(kwargs["role"], str):
            kwargs["role"] = kwargs["role"].upper()
        super().__init__(**kwargs)


class RevokedToken(Base):
    """Bảng lưu trữ các token đã bị thu hồi (Token Blacklist) phục vụ tính năng Logout / Revoke."""
    __tablename__ = "revoked_tokens"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token = Column(String(500), unique=True, nullable=False)
    revoked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(100), unique=True, nullable=False)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_number = Column(String(50), unique=True, nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False)
    subject = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    serial_number = Column(String(150), nullable=True)
    firmware_version = Column(String(100), nullable=True)
    is_hazard_escalated = Column(Boolean, nullable=False, default=False)
    hazard_reason = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="OPEN")
    priority = Column(String(30), nullable=False, default="MEDIUM")
    created_by = Column(String(150), nullable=True)
    assigned_to = Column(String(150), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    @property
    def title(self) -> str:
        """Alias tương thích ngược cho code/test cũ dùng trường title."""
        return self.subject

    def __init__(self, **kwargs: Any) -> None:
        if "title" in kwargs and "subject" not in kwargs:
            kwargs["subject"] = kwargs.pop("title")
        if "status" in kwargs and isinstance(kwargs["status"], str):
            kwargs["status"] = kwargs["status"].upper()
        if "priority" in kwargs and isinstance(kwargs["priority"], str):
            kwargs["priority"] = kwargs["priority"].upper()
        if "created_by" in kwargs and kwargs["created_by"] is not None:
            kwargs["created_by"] = str(kwargs["created_by"])
        if "assigned_to" in kwargs and kwargs["assigned_to"] is not None:
            kwargs["assigned_to"] = str(kwargs["assigned_to"])
        super().__init__(**kwargs)


class KnowledgePassage(Base):
    __tablename__ = "knowledge_passages"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=True)
    document_name = Column(String(255), nullable=False)
    document_code = Column(String(100), nullable=True)
    section_name = Column(String(255), nullable=True)
    section_number = Column(String(100), nullable=True)
    page_number = Column(Integer, nullable=False, default=1)
    passage_content = Column(Text, nullable=False)
    is_approved = Column(Boolean, default=False, nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(String(150), nullable=True)
    passage_metadata = Column("metadata", JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    @property
    def document_title(self) -> str:
        """Alias cho schema / test tương thích ngược."""
        return self.document_name

    @property
    def content_snippet(self) -> str:
        """Alias cho schema / test tương thích ngược."""
        return self.passage_content

    @property
    def section(self) -> str:
        """Alias cho section_name / section_number kết hợp."""
        parts = [p for p in [self.section_number, self.section_name] if p]
        return " - ".join(parts) if parts else (self.section_name or "")

    @property
    def version(self) -> str:
        """Alias lấy version từ metadata."""
        meta = self.passage_metadata if isinstance(self.passage_metadata, dict) else {}
        return str(meta.get("version") or meta.get("doc_version") or "v1.0")

    def __init__(self, **kwargs: Any) -> None:
        if "document_title" in kwargs and "document_name" not in kwargs:
            kwargs["document_name"] = kwargs.pop("document_title")
        if "content_snippet" in kwargs and "passage_content" not in kwargs:
            kwargs["passage_content"] = kwargs.pop("content_snippet")
        if "version" in kwargs:
            v = kwargs.pop("version")
            meta = kwargs.get("passage_metadata") or kwargs.get("metadata") or {}
            if isinstance(meta, dict):
                meta["version"] = v
            kwargs["passage_metadata"] = meta
        if "section" in kwargs and "section_name" not in kwargs:
            kwargs["section_name"] = kwargs.pop("section")
        super().__init__(**kwargs)


class CopilotPackage(Base):
    __tablename__ = "copilot_packages"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    intent = Column(String(50), nullable=True)
    case_summary = Column(Text, nullable=False)
    missing_facts = Column(JSON, default=list, nullable=False)
    citations = Column(JSON, default=list, nullable=False)
    next_step = Column(Text, nullable=True)
    draft = Column(Text, nullable=True)
    draft_response = Column(Text, nullable=True)
    approval_status = Column(String(20), default="Pending", nullable=False)
    reviewed_by = Column(String(150), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)