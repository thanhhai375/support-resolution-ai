"""
WP 02 Ingestion — Quarantine store (DAT 02)

Responsibilities:
  - Persist every QUARANTINED row to a local JSONL file for audit
  - Provide a retrieval API (by batch, by reason, by source_key)
  - Quarantine records are NEVER deleted automatically (Annex C)
  - Support tombstone / correction workflow (DAT 02 §deletion)

JSONL format: one JSON object per line, appended immutably.
In production: replace file I/O with PostgreSQL quarantine_log table.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.ingestion.validator import BatchReport, QuarantineReason, RowResult, RowStatus

# ---------------------------------------------------------------------------
# Default quarantine store location
# ---------------------------------------------------------------------------

_DEFAULT_QUARANTINE_DIR = Path(__file__).parent / "quarantine"


class QuarantineStore:
    """
    Append-only JSONL quarantine log.

    Each entry shape:
    {
        "quarantined_at": "<ISO-8601>",
        "batch_id": "...",
        "source_file": "...",
        "row_index": 3,
        "source_key": "EVT-009",
        "quarantine_reason": "SCHEMA_VIOLATION",
        "errors": [...],
        "raw_row": {...}
    }
    """

    def __init__(self, store_dir: Optional[Path] = None) -> None:
        self.store_dir = store_dir or _DEFAULT_QUARANTINE_DIR
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def _log_path(self, source_file: str) -> Path:
        """One JSONL file per source CSV type."""
        safe_name = source_file.replace(".csv", "").replace(" ", "_")
        return self.store_dir / f"quarantine_{safe_name}.jsonl"

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def persist_batch(self, report: BatchReport) -> int:
        """
        Append all QUARANTINED rows from a BatchReport to the JSONL log.
        Returns number of rows written.
        """
        quarantined = [r for r in report.row_results if r.status == RowStatus.QUARANTINED]
        if not quarantined:
            return 0

        log_path = self._log_path(report.source_file)
        now_iso = datetime.now(tz=timezone.utc).isoformat()

        with log_path.open("a", encoding="utf-8") as fh:
            for row_result in quarantined:
                entry: Dict[str, Any] = {
                    "quarantined_at": now_iso,
                    "batch_id": report.batch_id,
                    "source_file": report.source_file,
                    "import_type": report.import_type,
                    "row_index": row_result.row_index,
                    "source_key": row_result.source_key,
                    "quarantine_reason": (
                        row_result.quarantine_reason.value
                        if row_result.quarantine_reason
                        else QuarantineReason.UNKNOWN.value
                    ),
                    "errors": row_result.errors,
                    "raw_row": row_result.raw_row,
                }
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return len(quarantined)

    # ------------------------------------------------------------------
    # Read / Query
    # ------------------------------------------------------------------

    def _read_all(self, source_file: str) -> List[Dict[str, Any]]:
        log_path = self._log_path(source_file)
        if not log_path.exists():
            return []
        entries = []
        with log_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return entries

    def get_by_batch(self, source_file: str, batch_id: str) -> List[Dict[str, Any]]:
        """Retrieve all quarantine entries for a specific batch."""
        return [e for e in self._read_all(source_file) if e.get("batch_id") == batch_id]

    def get_by_reason(
        self, source_file: str, reason: QuarantineReason
    ) -> List[Dict[str, Any]]:
        """Retrieve all quarantine entries with a specific reason."""
        return [
            e for e in self._read_all(source_file)
            if e.get("quarantine_reason") == reason.value
        ]

    def get_by_key(self, source_file: str, source_key: str) -> List[Dict[str, Any]]:
        """Full history for one source key (may have multiple quarantine events)."""
        return [e for e in self._read_all(source_file) if e.get("source_key") == source_key]

    def get_all(self, source_file: str) -> List[Dict[str, Any]]:
        return self._read_all(source_file)

    def statistics(self, source_file: str) -> Dict[str, Any]:
        """Aggregate counts by quarantine_reason."""
        all_entries = self._read_all(source_file)
        counts: Dict[str, int] = {}
        for entry in all_entries:
            reason = entry.get("quarantine_reason", "UNKNOWN")
            counts[reason] = counts.get(reason, 0) + 1
        return {
            "source_file": source_file,
            "total_quarantined": len(all_entries),
            "by_reason": counts,
        }

    # ------------------------------------------------------------------
    # Tombstone / correction (DAT 02)
    # ------------------------------------------------------------------

    def add_tombstone(
        self,
        source_file: str,
        source_key: str,
        reason: str,
        authorized_by: str,
        batch_id: str,
    ) -> None:
        """
        DAT 02: Explicit deletion requires a tombstone record.
        Never silently absent — always a traceable deletion event.
        """
        log_path = self._log_path(source_file)
        entry: Dict[str, Any] = {
            "quarantined_at": datetime.now(tz=timezone.utc).isoformat(),
            "batch_id": batch_id,
            "source_file": source_file,
            "import_type": "tombstone",
            "source_key": source_key,
            "quarantine_reason": "TOMBSTONE",
            "tombstone_reason": reason,
            "authorized_by": authorized_by,
            "errors": [],
            "raw_row": {},
        }
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
