"""
WP 02 Ingestion — Validator (DAT 01, DAT 02, DAT 03)

Responsibilities:
  - Parse each CSV row through its Pydantic schema
  - Enforce DAT 02: snapshot/increment reconciliation + idempotency
    (late batches cannot overwrite newer record versions)
  - Classify rows as ACCEPTED or QUARANTINED with structured error reasons
  - Return a BatchReport with full audit trail
"""
from __future__ import annotations

import csv
import io
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type

from pydantic import BaseModel, ValidationError

from app.ingestion.schemas import (
    CaseEventRow,
    CustomerProductLinkRow,
    KnowledgePassageRow,
)


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

class RowStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    QUARANTINED = "QUARANTINED"


class QuarantineReason(str, Enum):
    SCHEMA_VIOLATION = "SCHEMA_VIOLATION"           # Pydantic validation failed
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    STALE_VERSION = "STALE_VERSION"                 # DAT 02: late batch overwrite attempt
    DUPLICATE_KEY = "DUPLICATE_KEY"                 # exact duplicate within same batch
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"         # DAT 03: unresolved identity conflict
    INVALID_PROVENANCE = "INVALID_PROVENANCE"       # DAT 01: bad owner/role/label
    UNKNOWN = "UNKNOWN"


@dataclass
class RowResult:
    """Outcome for a single CSV row."""
    row_index: int                          # 1-based (header = 0)
    source_key: str                         # primary key from the row
    status: RowStatus
    parsed: Optional[BaseModel] = None      # None if quarantined
    errors: List[Dict[str, Any]] = field(default_factory=list)
    quarantine_reason: Optional[QuarantineReason] = None
    raw_row: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "row_index": self.row_index,
            "source_key": self.source_key,
            "status": self.status.value,
            "quarantine_reason": self.quarantine_reason.value if self.quarantine_reason else None,
            "errors": self.errors,
        }


@dataclass
class BatchReport:
    """
    DAT 02: full reconciliation report for one ingestion batch.
    accepted + quarantined == expected (total rows in file).
    """
    batch_id: str
    source_file: str
    import_type: str                    # "snapshot" | "increment"
    started_at: datetime
    finished_at: Optional[datetime] = None

    total_rows: int = 0
    accepted: int = 0
    quarantined: int = 0

    row_results: List[RowResult] = field(default_factory=list)

    @property
    def reconciliation_ok(self) -> bool:
        """DAT 02: accepted + quarantined must equal total_rows."""
        return (self.accepted + self.quarantined) == self.total_rows

    def summary(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "source_file": self.source_file,
            "import_type": self.import_type,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "total_rows": self.total_rows,
            "accepted": self.accepted,
            "quarantined": self.quarantined,
            "reconciliation_ok": self.reconciliation_ok,
            "quarantined_rows": [r.to_dict() for r in self.row_results if r.status == RowStatus.QUARANTINED],
        }


# ---------------------------------------------------------------------------
# Version registry — DAT 02 idempotency / stale-version guard
# ---------------------------------------------------------------------------

class VersionRegistry:
    """
    In-memory registry of the highest accepted record_version per source_key.
    In production this would be backed by a persistent store (DB / Redis).
    """
    def __init__(self) -> None:
        self._store: Dict[str, int] = {}

    def is_stale(self, source_key: str, incoming_version: int) -> bool:
        """
        Returns True if incoming version is OLDER than what we already have.
        DAT 02: late batches cannot overwrite newer versions.
        """
        current = self._store.get(source_key)
        return current is not None and incoming_version < current

    def register(self, source_key: str, version: int) -> None:
        """Accept this version if it is >= current."""
        current = self._store.get(source_key, 0)
        if version >= current:
            self._store[source_key] = version

    def get_version(self, source_key: str) -> Optional[int]:
        return self._store.get(source_key)


# ---------------------------------------------------------------------------
# Shared validator core
# ---------------------------------------------------------------------------

def _extract_pydantic_errors(exc: ValidationError) -> Tuple[List[Dict[str, Any]], QuarantineReason]:
    """Convert Pydantic v2 ValidationError to structured error list."""
    errors = []
    reason = QuarantineReason.SCHEMA_VIOLATION

    for err in exc.errors():
        field_path = " → ".join(str(loc) for loc in err["loc"])
        msg = err["msg"]
        errors.append({"field": field_path, "message": msg, "type": err["type"]})

        if "missing" in err["type"].lower():
            reason = QuarantineReason.MISSING_REQUIRED_FIELD
        if "provenance" in msg.lower() or "access_label" in field_path or "owner" in field_path:
            reason = QuarantineReason.INVALID_PROVENANCE

    return errors, reason


def _row_fingerprint(row: Dict[str, str]) -> str:
    """SHA-256 of sorted row values for duplicate detection."""
    content = json.dumps(row, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode()).hexdigest()


def _coerce_bool(value: str) -> str:
    """Normalize 'true'/'false' strings for Pydantic bool fields."""
    return value.strip().lower()


def _clean_row(row: Dict[str, str]) -> Dict[str, Any]:
    """Strip whitespace and coerce common types. Handle None values from CSV."""
    cleaned: Dict[str, Any] = {}
    for k, v in row.items():
        if v is None:
            cleaned[k] = None
            continue
        v = v.strip()
        if v == "":
            cleaned[k] = None
        elif v.lower() in ("true", "false"):
            cleaned[k] = v.lower()
        else:
            cleaned[k] = v
    return cleaned


# ---------------------------------------------------------------------------
# Generic CSV → validated rows
# ---------------------------------------------------------------------------

def _validate_csv(
    csv_content: str,
    schema_cls: Type[BaseModel],
    primary_key_field: str,
    registry: VersionRegistry,
    import_type: str = "increment",
    batch_id: str = "UNKNOWN",
    source_file: str = "",
) -> BatchReport:
    """
    Core validation loop for one CSV file.
    Returns a BatchReport with per-row RowResult entries.
    """
    report = BatchReport(
        batch_id=batch_id,
        source_file=source_file,
        import_type=import_type,
        started_at=datetime.now(tz=timezone.utc),
    )

    seen_fingerprints: set[str] = set()

    reader = csv.DictReader(io.StringIO(csv_content))
    rows = list(reader)
    report.total_rows = len(rows)

    for idx, raw_row in enumerate(rows, start=1):
        source_key = raw_row.get(primary_key_field, f"<row_{idx}>") or f"<row_{idx}>"
        fingerprint = _row_fingerprint(raw_row)

        # --- DAT 02: Duplicate detection within batch ---
        if fingerprint in seen_fingerprints:
            result = RowResult(
                row_index=idx,
                source_key=source_key,
                status=RowStatus.QUARANTINED,
                quarantine_reason=QuarantineReason.DUPLICATE_KEY,
                errors=[{"message": "Exact duplicate row within same batch (DAT 02)"}],
                raw_row=raw_row,
            )
            report.quarantined += 1
            report.row_results.append(result)
            continue
        seen_fingerprints.add(fingerprint)

        # --- Pydantic schema validation ---
        cleaned = _clean_row(raw_row)
        try:
            parsed = schema_cls(**cleaned)
        except ValidationError as exc:
            errors, reason = _extract_pydantic_errors(exc)
            result = RowResult(
                row_index=idx,
                source_key=source_key,
                status=RowStatus.QUARANTINED,
                quarantine_reason=reason,
                errors=errors,
                raw_row=raw_row,
            )
            report.quarantined += 1
            report.row_results.append(result)
            continue
        except Exception as exc:
            result = RowResult(
                row_index=idx,
                source_key=source_key,
                status=RowStatus.QUARANTINED,
                quarantine_reason=QuarantineReason.UNKNOWN,
                errors=[{"message": str(exc)}],
                raw_row=raw_row,
            )
            report.quarantined += 1
            report.row_results.append(result)
            continue

        # --- DAT 02: Stale-version guard ---
        record_version: int = getattr(parsed, "record_version", 1)
        if registry.is_stale(source_key, record_version):
            current_ver = registry.get_version(source_key)
            result = RowResult(
                row_index=idx,
                source_key=source_key,
                status=RowStatus.QUARANTINED,
                quarantine_reason=QuarantineReason.STALE_VERSION,
                errors=[{
                    "message": (
                        f"DAT 02: incoming record_version={record_version} is older than "
                        f"accepted version={current_ver}. Late batch overwrite rejected."
                    )
                }],
                raw_row=raw_row,
            )
            report.quarantined += 1
            report.row_results.append(result)
            continue

        # --- DAT 03: Identity conflict still visible (not auto-merged) ---
        link_status = getattr(parsed, "link_status", None)
        if link_status in ("conflicted", "pending_review"):
            # Row is ACCEPTED but flagged — it stays visible per DAT 03.
            # It will not be used for recommendations until human confirms.
            result = RowResult(
                row_index=idx,
                source_key=source_key,
                status=RowStatus.ACCEPTED,
                parsed=parsed,
                errors=[{
                    "message": (
                        f"DAT 03: link_status='{link_status}' — row accepted but held for "
                        "human confirmation before use in recommendations."
                    ),
                    "severity": "WARNING",
                }],
                raw_row=raw_row,
            )
            registry.register(source_key, record_version)
            report.accepted += 1
            report.row_results.append(result)
            continue

        # --- ACCEPTED ---
        registry.register(source_key, record_version)
        result = RowResult(
            row_index=idx,
            source_key=source_key,
            status=RowStatus.ACCEPTED,
            parsed=parsed,
            raw_row=raw_row,
        )
        report.accepted += 1
        report.row_results.append(result)

    report.finished_at = datetime.now(tz=timezone.utc)
    return report


# ---------------------------------------------------------------------------
# Public API — one function per CSV type
# ---------------------------------------------------------------------------

def validate_cases_and_events(
    csv_content: str,
    registry: Optional[VersionRegistry] = None,
    batch_id: str = "UNKNOWN",
    import_type: str = "increment",
) -> BatchReport:
    return _validate_csv(
        csv_content=csv_content,
        schema_cls=CaseEventRow,
        primary_key_field="event_id",
        registry=registry or VersionRegistry(),
        import_type=import_type,
        batch_id=batch_id,
        source_file="cases_and_events.csv",
    )


def validate_customer_product_links(
    csv_content: str,
    registry: Optional[VersionRegistry] = None,
    batch_id: str = "UNKNOWN",
    import_type: str = "increment",
) -> BatchReport:
    return _validate_csv(
        csv_content=csv_content,
        schema_cls=CustomerProductLinkRow,
        primary_key_field="link_id",
        registry=registry or VersionRegistry(),
        import_type=import_type,
        batch_id=batch_id,
        source_file="customer_product_links.csv",
    )


def validate_knowledge_passages(
    csv_content: str,
    registry: Optional[VersionRegistry] = None,
    batch_id: str = "UNKNOWN",
    import_type: str = "increment",
) -> BatchReport:
    return _validate_csv(
        csv_content=csv_content,
        schema_cls=KnowledgePassageRow,
        primary_key_field="passage_key",
        registry=registry or VersionRegistry(),
        import_type=import_type,
        batch_id=batch_id,
        source_file="curated_knowledge_passages.csv",
    )
