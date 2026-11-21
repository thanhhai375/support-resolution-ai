"""
WP 02 Ingestion — Orchestrator  (CRM-42: DB write integrated)

Ties together:
  1. CSV loading from file path or raw content
  2. Validation (validator.py)
  3. DB write for ACCEPTED rows (db_writer.write_accepted_rows)
  4. DB write for QUARANTINED rows (db_writer.write_quarantine_rows)
     → replaces JSONL file; falls back to QuarantineStore if DB unavailable
  5. Batch reporting

Usage (CLI / test):
    python -m app.ingestion.ingest_pipeline

Usage (from code):
    from app.ingestion.ingest_pipeline import run_ingestion_batch
    report, write_result = run_ingestion_batch(...)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Tuple

from app.ingestion.db_writer import WriteResult, write_batch_to_db
from app.ingestion.quarantine_store import QuarantineStore
from app.ingestion.validator import (
    BatchReport,
    VersionRegistry,
    validate_cases_and_events,
    validate_customer_product_links,
    validate_knowledge_passages,
)

# Shared in-memory registry (in production: persistent DB-backed)
_GLOBAL_REGISTRY = VersionRegistry()
_QUARANTINE_STORE = QuarantineStore()

# Map source name → validator function
_VALIDATORS = {
    "cases_and_events": validate_cases_and_events,
    "customer_product_links": validate_customer_product_links,
    "curated_knowledge_passages": validate_knowledge_passages,
}


def run_ingestion_batch(
    source_name: str,
    csv_path: Path,
    import_type: str = "increment",
    registry: Optional[VersionRegistry] = None,
    quarantine_store: Optional[QuarantineStore] = None,
    batch_id: Optional[str] = None,
    write_to_db: bool = True,
) -> Tuple[BatchReport, WriteResult]:
    """
    Load a CSV file, validate all rows, write to DB, return (report, write_result).

    CRM-42: ACCEPTED rows → INSERT vào bảng tương ứng (knowledge_passages /
    case_events / customer_product_links). QUARANTINED rows → import_quarantine.
    Nếu DB không available, fallback sang JSONL QuarantineStore cho quarantine.

    Args:
        source_name:  one of 'cases_and_events', 'customer_product_links',
                      'curated_knowledge_passages'
        csv_path:     absolute or relative path to the CSV file
        import_type:  'snapshot' | 'increment'
        registry:     version registry (defaults to global singleton)
        quarantine_store: JSONL fallback quarantine backend
        batch_id:     override batch_id (defaults to filename stem)
        write_to_db:  set False in unit tests to skip DB write
    """
    if source_name not in _VALIDATORS:
        raise ValueError(
            f"Unknown source_name '{source_name}'. "
            f"Valid options: {list(_VALIDATORS.keys())}"
        )

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    csv_content = csv_path.read_text(encoding="utf-8")
    effective_batch_id = batch_id or csv_path.stem

    validator_fn = _VALIDATORS[source_name]
    report: BatchReport = validator_fn(
        csv_content=csv_content,
        registry=registry or _GLOBAL_REGISTRY,
        batch_id=effective_batch_id,
        import_type=import_type,
    )

    # --- CRM-42: DB write (ACCEPTED + QUARANTINED) ---
    write_result = WriteResult(batch_id=report.batch_id, source_file=report.source_file)
    if write_to_db:
        write_result = write_batch_to_db(report)

    return report, write_result


def print_report(report: BatchReport, verbose: bool = True) -> None:
    """Pretty-print a BatchReport to stdout."""
    sep = "=" * 65
    print(f"\n{sep}")
    print(f"  BATCH REPORT: {report.source_file}")
    print(sep)
    print(f"  Batch ID     : {report.batch_id}")
    print(f"  Import type  : {report.import_type}")
    print(f"  Total rows   : {report.total_rows}")
    print(f"  ✅ Accepted   : {report.accepted}")
    print(f"  🔴 Quarantined: {report.quarantined}")
    print(f"  DAT 02 Recon : {'✅ OK' if report.reconciliation_ok else '❌ FAIL'}")
    print(sep)

    if verbose and report.quarantined > 0:
        print("\n  QUARANTINED ROWS:")
        for r in report.row_results:
            if r.status.value == "QUARANTINED":
                print(f"\n  Row #{r.row_index} | key={r.source_key}")
                print(f"  Reason: {r.quarantine_reason.value if r.quarantine_reason else 'UNKNOWN'}")
                for err in r.errors:
                    field_info = f"[{err.get('field', '?')}] " if err.get("field") else ""
                    print(f"    ⚠  {field_info}{err.get('message', err)}")

    if verbose and report.accepted > 0:
        print("\n  ACCEPTED ROWS (warnings):")
        for r in report.row_results:
            if r.status.value == "ACCEPTED" and r.errors:
                print(f"\n  Row #{r.row_index} | key={r.source_key}")
                for err in r.errors:
                    print(f"    ℹ  {err.get('message', err)}")

    print()


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sample_dir = Path(__file__).parent / "sample_data"

    files = [
        ("cases_and_events",        sample_dir / "cases_and_events.csv"),
        ("customer_product_links",  sample_dir / "customer_product_links.csv"),
        ("curated_knowledge_passages", sample_dir / "curated_knowledge_passages.csv"),
    ]

    all_ok = True
    for source_name, csv_path in files:
        print(f"\n📂 Processing: {csv_path.name}")
        try:
            report, write_result = run_ingestion_batch(
                source_name, csv_path, import_type="increment"
            )
            print_report(report)
            print(f"  💾 DB inserted : {write_result.inserted_rows}")
            print(f"  🗄  DB quarantine: {write_result.quarantined_rows}")
            if write_result.errors:
                for e in write_result.errors:
                    print(f"  ⚠ DB error: {e}")
            if not report.reconciliation_ok:
                all_ok = False
        except Exception as exc:
            print(f"  ❌ FATAL: {exc}")
            all_ok = False

    sys.exit(0 if all_ok else 1)
