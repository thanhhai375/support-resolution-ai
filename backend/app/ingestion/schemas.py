"""
WP 02 Ingestion — DAT 01 (Provenance) schemas
Pydantic models for the 3 CSV sources.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# DAT 01 — Provenance field set (shared mixin)
# ---------------------------------------------------------------------------

VALID_ROLES = {
    "support_agent",
    "technical_approver",
    "knowledge_steward",
    "administrator",
    "customer",
}

VALID_ACCESS_LABELS = {"INTERNAL", "RESTRICTED", "PUBLIC"}

PRODUCT_CODES = {"MOTORS", "DRIVES"}


class ProvenanceMixin(BaseModel):
    """
    DAT 01: Every ingested record must carry immutable provenance metadata.
    - source_key        : stable external identifier
    - batch_id          : identifies the import batch
    - record_version    : monotonically increasing; late batches cannot
                          overwrite a newer version (DAT 02)
    - owner             : responsible party
    - access_label      : visibility class
    - permitted_audience: comma-separated list of roles allowed to read
    """
    batch_id: str = Field(..., min_length=1)
    record_version: int = Field(..., ge=1)
    owner: str = Field(..., min_length=1)
    access_label: str
    permitted_audience: str  # will be parsed to list in validators

    @field_validator("access_label")
    @classmethod
    def validate_access_label(cls, v: str) -> str:
        if v not in VALID_ACCESS_LABELS:
            raise ValueError(f"access_label must be one of {VALID_ACCESS_LABELS}, got '{v}'")
        return v


# ---------------------------------------------------------------------------
# FILE 1 — cases_and_events.csv
# ---------------------------------------------------------------------------

class CaseEventRow(ProvenanceMixin):
    """
    DAT 01: Immutable case/event record.
    DAT 03: account_key + product_code + serial_number form the identity link.
    is_customer_report separates customer reports from staff interpretation.
    """
    case_key: str = Field(..., min_length=1)
    account_key: str = Field(..., min_length=1)
    product_code: str
    serial_number: Optional[str] = None
    event_id: str = Field(..., min_length=1)
    event_author_role: str
    original_text: str = Field(..., min_length=1)
    event_time: datetime
    is_customer_report: bool

    @field_validator("product_code")
    @classmethod
    def validate_product_code(cls, v: str) -> str:
        if v not in PRODUCT_CODES:
            raise ValueError(f"product_code must be one of {PRODUCT_CODES}, got '{v}'")
        return v

    @field_validator("event_author_role")
    @classmethod
    def validate_author_role(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"event_author_role '{v}' not in approved roles {VALID_ROLES}")
        return v

    @field_validator("permitted_audience")
    @classmethod
    def validate_audience(cls, v: str) -> str:
        roles = [r.strip() for r in v.split("|") if r.strip()]
        invalid = set(roles) - VALID_ROLES - {"all"}
        if invalid:
            raise ValueError(f"permitted_audience contains unknown roles: {invalid}")
        return v


# ---------------------------------------------------------------------------
# FILE 2 — customer_product_links.csv
# ---------------------------------------------------------------------------

LINK_STATUSES = {"approved", "pending_review", "conflicted", "rejected"}


class CustomerProductLinkRow(ProvenanceMixin):
    """
    DAT 03 Identity: approved links only; unknown/conflicting remain visible.
    No fuzzy automatic merge — proposed matches require human confirmation.
    """
    link_id: str = Field(..., min_length=1)
    account_key: Optional[str] = None      # may be blank → pending_review
    product_code: str
    serial_number: Optional[str] = None
    link_status: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    link_source: str = Field(..., min_length=1)
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    conflict_note: Optional[str] = None

    @field_validator("product_code")
    @classmethod
    def validate_product_code(cls, v: str) -> str:
        if v not in PRODUCT_CODES:
            raise ValueError(f"product_code must be one of {PRODUCT_CODES}, got '{v}'")
        return v

    @field_validator("link_status")
    @classmethod
    def validate_link_status(cls, v: str) -> str:
        if v not in LINK_STATUSES:
            raise ValueError(f"link_status must be one of {LINK_STATUSES}, got '{v}'")
        return v

    @model_validator(mode="after")
    def approved_requires_confirmed_by(self) -> "CustomerProductLinkRow":
        """DAT 03: approved link must have human confirmation."""
        if self.link_status == "approved" and not self.confirmed_by:
            raise ValueError("approved link must have confirmed_by set (human confirmation required, DAT 03)")
        return self

    @model_validator(mode="after")
    def auto_inference_needs_review(self) -> "CustomerProductLinkRow":
        """DAT 03: auto-inferred links cannot be used without human confirmation."""
        if self.link_source == "auto_inference" and self.link_status == "approved":
            raise ValueError(
                "auto_inference links cannot be directly approved — human confirmation required (DAT 03)"
            )
        return self

    @field_validator("permitted_audience")
    @classmethod
    def validate_audience(cls, v: str) -> str:
        roles = [r.strip() for r in v.split("|") if r.strip()]
        invalid = set(roles) - VALID_ROLES - {"all"}
        if invalid:
            raise ValueError(f"permitted_audience contains unknown roles: {invalid}")
        return v


# ---------------------------------------------------------------------------
# FILE 3 — curated_knowledge_passages.csv
# ---------------------------------------------------------------------------

EFFECTIVE_STATUSES = {"current", "superseded", "withdrawn", "draft"}
RISK_CLASSES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
LANGUAGES = {"vi", "en"}


class KnowledgePassageRow(BaseModel):
    """
    DAT 04 Knowledge authority: requires title, revision, effective_status,
    section, page, owner, product_applicability, language, approved_audience,
    risk_class, supersession_link.
    Only approved + current passages may support recommendations.

    Provenance fields (DAT 01): batch_id, record_version, owner are required.
    access_label defaults to INTERNAL for all knowledge passages.
    approved_audience (column name) = permitted_audience semantics.
    """
    # DAT 01 Provenance
    batch_id: str = Field(..., min_length=1)
    record_version: int = Field(..., ge=1)
    owner: str = Field(..., min_length=1)
    access_label: str = Field(default="INTERNAL")

    # DAT 04 Knowledge authority fields
    passage_key: str = Field(..., min_length=1)
    document_title: str = Field(..., min_length=1)
    document_code: str = Field(..., min_length=1)
    revision: int = Field(..., ge=1)
    effective_status: str
    section_name: str = Field(..., min_length=1)
    section_number: str = Field(..., min_length=1)
    page_number: int = Field(..., ge=1)
    product_applicability: str
    language: str
    approved_audience: str
    risk_class: str
    supersession_link: Optional[str] = None
    passage_content: str = Field(..., min_length=10)
    is_approved: bool
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    @field_validator("effective_status")
    @classmethod
    def validate_effective_status(cls, v: str) -> str:
        if v not in EFFECTIVE_STATUSES:
            raise ValueError(f"effective_status must be one of {EFFECTIVE_STATUSES}")
        return v

    @field_validator("product_applicability")
    @classmethod
    def validate_product(cls, v: str) -> str:
        if v not in PRODUCT_CODES:
            raise ValueError(f"product_applicability must be one of {PRODUCT_CODES}")
        return v

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in LANGUAGES:
            raise ValueError(f"language must be one of {LANGUAGES}")
        return v

    @field_validator("risk_class")
    @classmethod
    def validate_risk(cls, v: str) -> str:
        if v not in RISK_CLASSES:
            raise ValueError(f"risk_class must be one of {RISK_CLASSES}")
        return v

    @field_validator("approved_audience")
    @classmethod
    def validate_audience(cls, v: str) -> str:
        roles = [r.strip() for r in v.split("|") if r.strip()]
        invalid = set(roles) - VALID_ROLES - {"all"}
        if invalid:
            raise ValueError(f"approved_audience contains unknown roles: {invalid}")
        return v

    @model_validator(mode="after")
    def approved_requires_metadata(self) -> "KnowledgePassageRow":
        """DAT 04: approved passage must have approved_by and approved_at."""
        if self.is_approved:
            if not self.approved_by:
                raise ValueError("is_approved=true requires approved_by (DAT 04)")
            if not self.approved_at:
                raise ValueError("is_approved=true requires approved_at (DAT 04)")
        return self

    @model_validator(mode="after")
    def superseded_requires_link(self) -> "KnowledgePassageRow":
        """Superseded passages must point to their replacement."""
        if self.effective_status == "superseded" and not self.supersession_link:
            raise ValueError("superseded passage must have supersession_link (DAT 04)")
        return self
