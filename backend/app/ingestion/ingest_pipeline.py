"""
WP 02 Ingestion — Orchestrator

Ties together:
  1. CSV loading from file path or raw content
  2. Validation (validator.py)
  3. Quarantine persistence (quarantine_store.py)
  4. Batch reporting

Usage (CLI / test):
    python -m app.ingestion.ingest_pipeline

Usage (from code):
    from app.ingestion.ingest_pipeline import run_ingestion_batch
    report = run_ingestion_batch("cases_and_events", Path("data/cases_and_events.csv"))
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

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
) -> BatchReport:
    """
    Load a CSV file, validate all rows, quarantine failures, return report.

    Args:
        source_name:  one of 'cases_and_events', 'customer_product_links',
                      'curated_knowledge_passages'
        csv_path:     absolute or relative path to the CSV file
        import_type:  'snapshot' | 'increment'
        registry:     version registry (defaults to global singleton)
        quarantine_store: quarantine backend (defaults to global singleton)
        batch_id:     override batch_id (defaults to filename stem)
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

    # Persist quarantined rows
    q_store = quarantine_store or _QUARANTINE_STORE
    written = q_store.persist_batch(report)

    return report


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
            report = run_ingestion_batch(source_name, csv_path, import_type="increment")
            print_report(report)
            if not report.reconciliation_ok:
                all_ok = False
        except Exception as exc:
            print(f"  ❌ FATAL: {exc}")
            all_ok = False

    # Quarantine statistics
    print("\n" + "=" * 65)
    print("  QUARANTINE STORE STATISTICS")
    print("=" * 65)
    for source_name, csv_path in files:
        stats = _QUARANTINE_STORE.statistics(csv_path.name)
        print(f"\n  {csv_path.name}")
        print(f"    Total quarantined ever: {stats['total_quarantined']}")
        for reason, count in stats["by_reason"].items():
            print(f"    {reason}: {count}")

    sys.exit(0 if all_ok else 1)
