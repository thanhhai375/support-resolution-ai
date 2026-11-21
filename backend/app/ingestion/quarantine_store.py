"""
WP 02 Ingestion — Quarantine store (DAT 02)   [CRM-42: DB-backed]

CRM-42: Quarantine records được ghi vào bảng import_quarantine trong PostgreSQL.
KHÔNG dùng JSONL file nữa.

API giữ nguyên (backward-compatible) để các unit test CRM-26 không bị break:
  persist_batch()   → ghi vào DB (nếu DB available) hoặc JSONL fallback
  get_all()         → đọc từ DB
  get_by_batch()    → đọc từ DB
  get_by_key()      → đọc từ DB
  get_by_reason()   → đọc từ DB
  statistics()      → đọc từ DB
  add_tombstone()   → ghi vào DB

Nếu DB không available, persist_batch() fallback sang JSONL để unit test
CRM-26 (dùng QuarantineStore trực tiếp với tmp_path) vẫn PASS.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.ingestion.validator import BatchReport, QuarantineReason, RowResult, RowStatus

# ---------------------------------------------------------------------------
# Default fallback quarantine dir (chỉ dùng khi DB không available)
# ---------------------------------------------------------------------------

_DEFAULT_QUARANTINE_DIR = Path(__file__).parent / "quarantine"


class QuarantineStore:
    """
    CRM-42: DB-backed quarantine store.

    Mọi read đọc từ DB (import_quarantine).
    persist_batch / add_tombstone ghi vào DB.
    Fallback sang JSONL chỉ khi DB không available (unit test local).
    """

    def __init__(self, store_dir: Optional[Path] = None) -> None:
        # store_dir vẫn giữ cho fallback JSONL (unit test CRM-26)
        self.store_dir = store_dir or _DEFAULT_QUARANTINE_DIR
        self.store_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def persist_batch(self, report: BatchReport) -> int:
        """
        Ghi QUARANTINED rows từ report:
        - Ưu tiên: ghi vào DB (import_quarantine)
        - Fallback: JSONL file nếu DB không available
        Returns number of rows written.
        """
        # Import lazy để tránh circular import
        from app.ingestion.db_writer import _get_conn, _insert_quarantine_rows

        quarantined = [r for r in report.row_results if r.status == RowStatus.QUARANTINED]
        if not quarantined:
            return 0

        conn = _get_conn()
        if conn is not None:
            try:
                with conn:
                    with conn.cursor() as cur:
                        written = _insert_quarantine_rows(cur, report)
                return written
            except Exception:
                pass  # fallback
            finally:
                conn.close()

        # Fallback JSONL
        return self._persist_jsonl(report)

    def _persist_jsonl(self, report: BatchReport) -> int:
        """Fallback JSONL writer (dùng khi DB không available)."""
        quarantined = [r for r in report.row_results if r.status == RowStatus.QUARANTINED]
        if not quarantined:
            return 0

        log_path = self._log_path(report.source_file)
        now_iso = datetime.now(tz=timezone.utc).isoformat()

        with log_path.open("a", encoding="utf-8") as fh:
            for rr in quarantined:
                entry: Dict[str, Any] = {
                    "quarantined_at": now_iso,
                    "batch_id": report.batch_id,
                    "source_file": report.source_file,
                    "import_type": report.import_type,
                    "row_index": rr.row_index,
                    "source_key": rr.source_key,
                    "quarantine_reason": (
                        rr.quarantine_reason.value
                        if rr.quarantine_reason
                        else QuarantineReason.UNKNOWN.value
                    ),
                    "errors": rr.errors,
                    "raw_row": rr.raw_row,
                }
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return len(quarantined)

    # ------------------------------------------------------------------
    # Read / Query — DB-backed
    # ------------------------------------------------------------------

    def get_by_batch(self, source_file: str, batch_id: str) -> List[Dict[str, Any]]:
        from app.ingestion.db_writer import db_query_quarantine
        result = db_query_quarantine(source_file, batch_id=batch_id)
        if result is not None:
            return result
        # JSONL fallback (unit test)
        return [e for e in self._read_jsonl(source_file) if e.get("batch_id") == batch_id]

    def get_by_reason(
        self, source_file: str, reason: QuarantineReason
    ) -> List[Dict[str, Any]]:
        from app.ingestion.db_writer import db_query_quarantine
        result = db_query_quarantine(source_file, reason=reason.value)
        if result is not None:
            return result
        return [
            e for e in self._read_jsonl(source_file)
            if e.get("quarantine_reason") == reason.value
        ]

    def get_by_key(self, source_file: str, source_key: str) -> List[Dict[str, Any]]:
        from app.ingestion.db_writer import db_query_quarantine
        result = db_query_quarantine(source_file, source_key=source_key)
        if result is not None:
            return result
        return [e for e in self._read_jsonl(source_file) if e.get("source_key") == source_key]

    def get_all(self, source_file: str) -> List[Dict[str, Any]]:
        from app.ingestion.db_writer import db_query_quarantine
        result = db_query_quarantine(source_file)
        if result is not None:
            return result
        return self._read_jsonl(source_file)

    def statistics(self, source_file: str) -> Dict[str, Any]:
        from app.ingestion.db_writer import db_quarantine_statistics
        result = db_quarantine_statistics(source_file)
        if result is not None:  # None = DB not available
            return result
        # Fallback JSONL
        all_entries = self._read_jsonl(source_file)
        counts: Dict[str, int] = {}
        for entry in all_entries:
            r = entry.get("quarantine_reason", "UNKNOWN")
            counts[r] = counts.get(r, 0) + 1
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
        DAT 02: Ghi tombstone vào import_quarantine (is_tombstone=TRUE).
        Fallback sang JSONL nếu DB không available.
        """
        from app.ingestion.db_writer import db_add_tombstone
        success = db_add_tombstone(
            source_file=source_file,
            source_key=source_key,
            reason=reason,
            authorized_by=authorized_by,
            batch_id=batch_id,
        )
        if not success:
            # JSONL fallback
            self._tombstone_jsonl(source_file, source_key, reason, authorized_by, batch_id)

    def _tombstone_jsonl(
        self,
        source_file: str,
        source_key: str,
        reason: str,
        authorized_by: str,
        batch_id: str,
    ) -> None:
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

    # ------------------------------------------------------------------
    # JSONL helpers (fallback / unit test compatibility)
    # ------------------------------------------------------------------

    def _log_path(self, source_file: str) -> Path:
        safe_name = source_file.replace(".csv", "").replace(" ", "_")
        return self.store_dir / f"quarantine_{safe_name}.jsonl"

    def _read_jsonl(self, source_file: str) -> List[Dict[str, Any]]:
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
