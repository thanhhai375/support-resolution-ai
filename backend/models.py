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
    Uuid as UUID,
    func,
)

try:
    from main import Base
except ImportError:
    try:
        from backend.main import Base
    except ImportError:
        from sqlalchemy.orm import declarative_base
        Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False, default="user")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="open")
    priority = Column(String(20), nullable=False, default="medium")
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_hazard_escalated = Column(Boolean, nullable=True, default=False)
    hazard_reason = Column(Text, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    sender_type = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    is_internal = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class KnowledgePassage(Base):
    __tablename__ = "knowledge_passages"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), nullable=True)
    document_name = Column(String(255), nullable=False)
    document_code = Column(String(100), nullable=True)
    section_name = Column(String(255), nullable=True)
    section_number = Column(String(100), nullable=True)
    page_number = Column(Integer, nullable=False, default=1)
    passage_content = Column(Text, nullable=False)
    is_approved = Column(Boolean, default=True, nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(String(150), nullable=True)
    passage_metadata = Column("metadata", JSON, default=dict)
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

    def __init__(self, **kwargs: Any) -> None:
        if "document_title" in kwargs and "document_name" not in kwargs:
            kwargs["document_name"] = kwargs.pop("document_title")
        if "content_snippet" in kwargs and "passage_content" not in kwargs:
            kwargs["passage_content"] = kwargs.pop("content_snippet")
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
