"""
WP 02 Ingestion — FastAPI Router  (DAT 01–03)

Endpoints:
  POST /api/v1/ingestion/upload          Upload a CSV file → validate + quarantine
  GET  /api/v1/ingestion/batches/{id}    Get batch report JSON
  GET  /api/v1/ingestion/quarantine      List quarantine entries (with filters)
  POST /api/v1/ingestion/tombstone       Record an explicit deletion (DAT 02)
  GET  /api/v1/ingestion/stats           Quarantine statistics
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated, List, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from app.ingestion.ingest_pipeline import _GLOBAL_REGISTRY, _QUARANTINE_STORE, run_ingestion_batch
from app.ingestion.quarantine_store import QuarantineStore
from app.ingestion.validator import BatchReport, QuarantineReason

router = APIRouter(prefix="/api/v1/ingestion", tags=["WP02 Ingestion"])

# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class UploadResponse(BaseModel):
    batch_id: str
    source_file: str
    import_type: str
    total_rows: int
    accepted: int
    quarantined: int
    reconciliation_ok: bool
    message: str


class TombstoneRequest(BaseModel):
    source_file: str          # e.g. "cases_and_events.csv"
    source_key: str           # primary key of the record to delete
    reason: str               # explicit deletion reason (DAT 02)
    authorized_by: str        # must be named person
    batch_id: str             # originating batch


# ---------------------------------------------------------------------------
# Source name ↔ file name mapping
# ---------------------------------------------------------------------------

_KNOWN_SOURCES = {
    "cases_and_events.csv":           "cases_and_events",
    "customer_product_links.csv":     "customer_product_links",
    "curated_knowledge_passages.csv": "curated_knowledge_passages",
}


def _resolve_source(filename: str) -> str:
    source = _KNOWN_SOURCES.get(filename)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Unrecognised file name '{filename}'. "
                f"Expected one of: {list(_KNOWN_SOURCES.keys())}"
            ),
        )
    return source


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Upload CSV for WP02 ingestion (DAT 01–03)",
)
async def upload_csv(
    file: Annotated[UploadFile, File(description="One of the 3 WP02 CSV files")],
    import_type: Annotated[
        Literal["snapshot", "increment"],
        Form(description="'snapshot' = full replace reconciliation; 'increment' = additive"),
    ] = "increment",
    batch_id: Annotated[Optional[str], Form()] = None,
) -> UploadResponse:
    """
    Upload a CSV file and run the full WP 02 ingestion pipeline:
    1. Validate every row (DAT 01 Provenance, DAT 02 Import integrity, DAT 03 Identity)
    2. Quarantine invalid rows with structured error reasons
    3. Return reconciliation report

    Accepted filenames:
    - **cases_and_events.csv**
    - **customer_product_links.csv**
    - **curated_knowledge_passages.csv**
    """
    source_name = _resolve_source(file.filename or "")

    # Write upload to temp file so validator can read it
    content = await file.read()

    with tempfile.NamedTemporaryFile(
        suffix=".csv", delete=False, mode="wb"
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        report: BatchReport = run_ingestion_batch(
            source_name=source_name,
            csv_path=tmp_path,
            import_type=import_type,
            registry=_GLOBAL_REGISTRY,
            quarantine_store=_QUARANTINE_STORE,
            batch_id=batch_id,
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    msg = (
        f"Ingestion complete. {report.accepted} accepted, "
        f"{report.quarantined} quarantined."
    )
    if not report.reconciliation_ok:
        msg += " ⚠ DAT 02 reconciliation FAILED."

    return UploadResponse(
        batch_id=report.batch_id,
        source_file=report.source_file,
        import_type=report.import_type,
        total_rows=report.total_rows,
        accepted=report.accepted,
        quarantined=report.quarantined,
        reconciliation_ok=report.reconciliation_ok,
        message=msg,
    )


@router.get(
    "/quarantine",
    summary="List quarantine entries (DAT 02)",
)
def list_quarantine(
    source_file: Annotated[str, Query(description="e.g. cases_and_events.csv")],
    batch_id: Optional[str] = Query(default=None),
    reason: Optional[QuarantineReason] = Query(default=None),
    source_key: Optional[str] = Query(default=None),
) -> list:
    """
    Retrieve quarantine log entries. All quarantined rows remain permanently
    visible per DAT 02 — unexplained absence is not permitted.
    """
    store: QuarantineStore = _QUARANTINE_STORE

    if source_key:
        return store.get_by_key(source_file, source_key)
    if batch_id:
        return store.get_by_batch(source_file, batch_id)
    if reason:
        return store.get_by_reason(source_file, reason)
    return store.get_all(source_file)


@router.get(
    "/stats",
    summary="Quarantine statistics by source file",
)
def quarantine_stats(
    source_file: Annotated[str, Query(description="e.g. cases_and_events.csv")],
) -> dict:
    """Aggregate quarantine counts by reason for one source file."""
    return _QUARANTINE_STORE.statistics(source_file)


@router.post(
    "/tombstone",
    status_code=status.HTTP_201_CREATED,
    summary="Record explicit deletion tombstone (DAT 02)",
)
def add_tombstone(body: TombstoneRequest) -> dict:
    """
    DAT 02: Deletion requires an explicit tombstone — never unexplained absence.
    Records the deletion event in the quarantine log with authorization metadata.
    """
    _QUARANTINE_STORE.add_tombstone(
        source_file=body.source_file,
        source_key=body.source_key,
        reason=body.reason,
        authorized_by=body.authorized_by,
        batch_id=body.batch_id,
    )
    return {
        "status": "tombstone_recorded",
        "source_key": body.source_key,
        "authorized_by": body.authorized_by,
        "dat02_compliant": True,
    }
