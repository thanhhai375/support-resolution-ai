"""
CRM-42 — Ingestion → DB Write

Public API:
  write_accepted_rows(report)   → INSERT/UPSERT ACCEPTED rows vào bảng tương ứng
  write_quarantine_rows(report) → INSERT QUARANTINED rows vào import_quarantine
  write_batch_to_db(report)     → Hàm tổng hợp: accepted + quarantine + batch header

Quarantine ghi vào bảng import_quarantine trong PostgreSQL.
KHÔNG dùng JSONL file nữa (CRM-42 AC#5).

Driver: psycopg2 (sync) — phù hợp với run_ingestion_batch() sync hiện tại.
Nếu psycopg2 chưa install hoặc DB không kết nối được, hàm log warning
và trả về 0/WriteResult(db_available=False) — không raise, không block pipeline.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.ingestion.validator import BatchReport, QuarantineReason, RowResult, RowStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class WriteResult:
    batch_id: str
    source_file: str
    inserted_rows: int = 0        # ACCEPTED rows ghi thành công vào DB
    quarantined_rows: int = 0     # QUARANTINED rows ghi vào import_quarantine (CRM-42: đúng tên)
    db_available: bool = True
    errors: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# DB connection helper
# ---------------------------------------------------------------------------

def _get_conn():
    """
    Mở psycopg2 connection.

    Ưu tiên DATABASE_URL (chuyển asyncpg → psycopg2 DSN nếu cần),
    sau đó fallback sang POSTGRES_* individual vars — đảm bảo hoạt
    đúng cả local lẫn Docker network (host = 'db').

    Trả về None nếu psycopg2 chưa install hoặc DB không kết nối được.
    """
    try:
        import psycopg2  # type: ignore
    except ImportError:
        logger.warning("[CRM-42] psycopg2 not installed – DB write skipped.")
        return None

    # 1. Thử DATABASE_URL trước
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        # Chuyển asyncpg dialect sang psycopg2
        dsn = re.sub(r"^postgresql\+asyncpg://", "postgresql://", db_url)
        dsn = re.sub(r"^postgres://", "postgresql://", dsn)
        try:
            conn = psycopg2.connect(dsn, connect_timeout=5)
            return conn
        except Exception as exc:
            logger.warning("[CRM-42] DATABASE_URL connect failed (%s), trying POSTGRES_* vars.", exc)

    # 2. Fallback: individual POSTGRES_* env vars
    host     = os.getenv("POSTGRES_HOST",     "localhost")
    port     = os.getenv("POSTGRES_PORT",     "5432")
    user     = os.getenv("POSTGRES_USER",     "songnhat")
    password = os.getenv("POSTGRES_PASSWORD", "songnhat_dev")
    dbname   = os.getenv("POSTGRES_DB",       "songnhat_copilot")

    try:
        return psycopg2.connect(
            host=host, port=int(port), user=user,
            password=password, dbname=dbname, connect_timeout=5,
        )
    except Exception as exc:
        logger.warning("[CRM-42] DB connection failed (%s) – DB write skipped.", exc)
        return None


# ---------------------------------------------------------------------------
# Product id lookup (cục bộ per-connection, không cache global)
# ---------------------------------------------------------------------------

def _fetch_product_id(cur, product_code: str, local_cache: Dict[str, str]) -> Optional[str]:
    """
    Tra product_id từ bảng products.
    Cache cục bộ trong local_cache (dict truyền vào) để tránh lỗi FK
    khi test reset bảng products giữa các lần chạy.
    """
    if product_code in local_cache:
        return local_cache[product_code]
    cur.execute("SELECT id FROM products WHERE code = %s", (product_code,))
    row = cur.fetchone()
    if row:
        pid = str(row[0])
        local_cache[product_code] = pid
        return pid
    return None


# ---------------------------------------------------------------------------
# Per-source ACCEPTED writers
# ---------------------------------------------------------------------------

def _insert_knowledge_passages(cur, accepted: List[RowResult]) -> int:
    """
    Upsert vào knowledge_passages.
    Idempotency key: (document_code, section_number, page_number, product_id)
    — UNIQUE NULLS NOT DISTINCT constraint (CRM-42 migration).

    Tuân thủ chk_knowledge_approval:
      is_approved=True  → approved_at phải NOT NULL
      is_approved=False → approved_at phải NULL
    """
    sql = """
        INSERT INTO knowledge_passages (
            product_id, document_name, document_code,
            section_name, section_number, page_number,
            passage_content, is_approved, approved_at, approved_by,
            metadata
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
        ON CONFLICT ON CONSTRAINT uq_knowledge_passage_identity
        DO UPDATE SET
            document_name   = EXCLUDED.document_name,
            section_name    = EXCLUDED.section_name,
            passage_content = EXCLUDED.passage_content,
            is_approved     = EXCLUDED.is_approved,
            approved_at     = EXCLUDED.approved_at,
            approved_by     = EXCLUDED.approved_by,
            metadata        = EXCLUDED.metadata,
            updated_at      = CURRENT_TIMESTAMP
    """
    local_cache: Dict[str, str] = {}
    inserted = 0
    for rr in accepted:
        p = rr.parsed
        product_id = _fetch_product_id(cur, p.product_applicability, local_cache)
        if not product_id:
            logger.warning(
                "[CRM-42] knowledge_passages: unknown product=%r – row skipped.",
                p.product_applicability,
            )
            continue

        # Enforce chk_knowledge_approval
        if p.is_approved:
            approved_at = p.approved_at.isoformat() if p.approved_at else datetime.now(timezone.utc).isoformat()
        else:
            approved_at = None

        meta = json.dumps({
            "passage_key":       p.passage_key,
            "batch_id":          p.batch_id,
            "record_version":    p.record_version,
            "owner":             p.owner,
            "access_label":      getattr(p, "access_label", "INTERNAL"),
            "effective_status":  p.effective_status,
            "language":          p.language,
            "approved_audience": p.approved_audience,
            "risk_class":        p.risk_class,
            "supersession_link": p.supersession_link,
            "revision":          p.revision,
        }, ensure_ascii=False)

        cur.execute(sql, (
            product_id, p.document_title, p.document_code,
            p.section_name, p.section_number, p.page_number,
            p.passage_content, p.is_approved,
            approved_at, p.approved_by, meta,
        ))
        inserted += 1
    return inserted


def _insert_case_events(cur, accepted: List[RowResult]) -> int:
    """
    Upsert vào case_events.
    Idempotency key: event_id (UNIQUE constraint).
    Chỉ UPDATE nếu incoming record_version > version hiện tại.
    """
    sql = """
        INSERT INTO case_events (
            event_id, case_key, account_key, product_code, serial_number,
            event_author_role, original_text, event_time, is_customer_report,
            batch_id, record_version, owner, access_label, permitted_audience
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (event_id) DO UPDATE SET
            original_text      = EXCLUDED.original_text,
            record_version     = EXCLUDED.record_version,
            updated_at         = CURRENT_TIMESTAMP
        WHERE case_events.record_version < EXCLUDED.record_version
    """
    inserted = 0
    for rr in accepted:
        p = rr.parsed
        cur.execute(sql, (
            p.event_id, p.case_key, p.account_key, p.product_code, p.serial_number,
            p.event_author_role, p.original_text,
            p.event_time.isoformat(), p.is_customer_report,
            p.batch_id, p.record_version, p.owner,
            p.access_label, p.permitted_audience,
        ))
        inserted += 1
    return inserted


def _insert_customer_product_links(cur, accepted: List[RowResult]) -> int:
    """
    Upsert vào customer_product_links.
    Idempotency key: link_id (UNIQUE constraint).
    Chỉ UPDATE nếu incoming record_version > version hiện tại.
    """
    sql = """
        INSERT INTO customer_product_links (
            link_id, account_key, product_code, serial_number,
            link_status, confidence_score, link_source,
            confirmed_by, confirmed_at, conflict_note,
            batch_id, record_version, owner, access_label, permitted_audience
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (link_id) DO UPDATE SET
            link_status      = EXCLUDED.link_status,
            confidence_score = EXCLUDED.confidence_score,
            confirmed_by     = EXCLUDED.confirmed_by,
            confirmed_at     = EXCLUDED.confirmed_at,
            conflict_note    = EXCLUDED.conflict_note,
            record_version   = EXCLUDED.record_version,
            updated_at       = CURRENT_TIMESTAMP
        WHERE customer_product_links.record_version < EXCLUDED.record_version
    """
    inserted = 0
    for rr in accepted:
        p = rr.parsed
        cur.execute(sql, (
            p.link_id, p.account_key, p.product_code, p.serial_number,
            p.link_status, p.confidence_score, p.link_source,
            p.confirmed_by,
            p.confirmed_at.isoformat() if p.confirmed_at else None,
            p.conflict_note,
            p.batch_id, p.record_version, p.owner,
            p.access_label, p.permitted_audience,
        ))
        inserted += 1
    return inserted


# Source file → writer function dispatch
_ACCEPTED_WRITERS = {
    "cases_and_events.csv":           _insert_case_events,
    "customer_product_links.csv":     _insert_customer_product_links,
    "curated_knowledge_passages.csv": _insert_knowledge_passages,
}


# ---------------------------------------------------------------------------
# Quarantine writer → import_quarantine table (thay thế JSONL)
# ---------------------------------------------------------------------------

def _insert_quarantine_rows(cur, report: BatchReport) -> int:
    """
    Ghi tất cả QUARANTINED rows vào bảng import_quarantine.
    Idempotency key: (batch_id, source_file, row_index) — ON CONFLICT DO NOTHING.
    """
    sql = """
        INSERT INTO import_quarantine (
            batch_id, source_file, import_type,
            row_index, source_key,
            quarantine_reason, errors, raw_row
        ) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)
        ON CONFLICT (batch_id, source_file, row_index) DO NOTHING
    """
    quarantined = [r for r in report.row_results if r.status == RowStatus.QUARANTINED]
    for rr in quarantined:
        cur.execute(sql, (
            report.batch_id,
            report.source_file,
            report.import_type,
            rr.row_index,
            rr.source_key,
            rr.quarantine_reason.value if rr.quarantine_reason else QuarantineReason.UNKNOWN.value,
            json.dumps(rr.errors, ensure_ascii=False),
            json.dumps(rr.raw_row, ensure_ascii=False),
        ))
    return len(quarantined)


# ---------------------------------------------------------------------------
# Batch header writer
# ---------------------------------------------------------------------------

def _upsert_batch_header(
    cur,
    report: BatchReport,
    inserted_rows: int,
    quarantined_rows: int,  # tên đúng CRM-42
) -> None:
    sql = """
        INSERT INTO run_ingestion_batches (
            batch_id, source_file, import_type,
            started_at, finished_at,
            total_rows, accepted_rows, quarantined_rows, inserted_rows,
            reconciliation_ok
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (batch_id, source_file) DO UPDATE SET
            finished_at       = EXCLUDED.finished_at,
            total_rows        = EXCLUDED.total_rows,
            accepted_rows     = EXCLUDED.accepted_rows,
            quarantined_rows  = EXCLUDED.quarantined_rows,
            inserted_rows     = EXCLUDED.inserted_rows,
            reconciliation_ok = EXCLUDED.reconciliation_ok,
            updated_at        = CURRENT_TIMESTAMP
    """
    cur.execute(sql, (
        report.batch_id, report.source_file, report.import_type,
        report.started_at.isoformat(),
        report.finished_at.isoformat() if report.finished_at else None,
        report.total_rows,
        report.accepted,
        quarantined_rows,   # dùng tham số, không dùng report.quarantined để tránh ghi đè sai
        inserted_rows,
        report.reconciliation_ok,
    ))


# ---------------------------------------------------------------------------
# DB-backed quarantine query helpers (dùng bởi QuarantineStore DB-backed)
# ---------------------------------------------------------------------------

def db_query_quarantine(
    source_file: str,
    batch_id: Optional[str] = None,
    source_key: Optional[str] = None,
    reason: Optional[str] = None,
) -> Optional[List[Dict[str, Any]]]:
    """
    Query import_quarantine từ DB. Dùng bởi GET /api/v1/ingestion/quarantine.
    Trả None nếu DB không available (để caller biết dùng JSONL fallback).
    Trả [] nếu DB available nhưng không có row nào.
    """
    conn = _get_conn()
    if conn is None:
        return None  # DB not available → caller dùng JSONL fallback

    conditions = ["source_file = %s"]
    params: list = [source_file]

    if batch_id:
        conditions.append("batch_id = %s")
        params.append(batch_id)
    if source_key:
        conditions.append("source_key = %s")
        params.append(source_key)
    if reason:
        conditions.append("quarantine_reason = %s")
        params.append(reason)

    where = " AND ".join(conditions)
    sql = f"""
        SELECT batch_id, source_file, import_type, row_index, source_key,
               quarantine_reason, errors, raw_row, quarantined_at,
               tombstone_reason, authorized_by, is_tombstone
        FROM import_quarantine
        WHERE {where}
        ORDER BY quarantined_at DESC
    """
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                cols = [
                    "batch_id", "source_file", "import_type", "row_index", "source_key",
                    "quarantine_reason", "errors", "raw_row", "quarantined_at",
                    "tombstone_reason", "authorized_by", "is_tombstone",
                ]
                return [dict(zip(cols, r)) for r in rows]
    except Exception as exc:
        logger.error("[CRM-42] db_query_quarantine FAILED: %s", exc)
        return []
    finally:
        conn.close()


def db_quarantine_statistics(source_file: str) -> Optional[Dict[str, Any]]:
    """
    Aggregate quarantine counts by reason từ import_quarantine.
    Trả None nếu DB không available (để caller dùng JSONL fallback).
    """
    conn = _get_conn()
    if conn is None:
        return None  # DB not available → caller dùng JSONL fallback

    sql = """
        SELECT quarantine_reason, COUNT(*) as cnt
        FROM import_quarantine
        WHERE source_file = %s
        GROUP BY quarantine_reason
    """
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, (source_file,))
                rows = cur.fetchall()
                by_reason = {r[0]: r[1] for r in rows}
                total = sum(by_reason.values())
                return {
                    "source_file": source_file,
                    "total_quarantined": total,
                    "by_reason": by_reason,
                }
    except Exception as exc:
        logger.error("[CRM-42] db_quarantine_statistics FAILED: %s", exc)
        return {"source_file": source_file, "total_quarantined": 0, "by_reason": {}}
    finally:
        conn.close()


def db_add_tombstone(
    source_file: str,
    source_key: str,
    reason: str,
    authorized_by: str,
    batch_id: str,
) -> bool:
    """
    Ghi tombstone vào bảng import_quarantine (is_tombstone=TRUE).
    Trả True nếu thành công, False nếu DB không available.
    """
    conn = _get_conn()
    if conn is None:
        return False

    # Tombstone dùng row_index=-1 để không xung đột với uq_quarantine_entry
    # (batch_id + source_file + row_index) — mỗi lần tombstone là unique qua id UUID.
    # Ta dùng sequence riêng: lấy count hiện tại * -1 để tránh collision.
    sql_insert = """
        INSERT INTO import_quarantine (
            batch_id, source_file, import_type,
            row_index, source_key,
            quarantine_reason, errors, raw_row,
            tombstone_reason, authorized_by, is_tombstone
        ) VALUES (%s,%s,'tombstone',%s,%s,'TOMBSTONE','[]'::jsonb,'{}'::jsonb,%s,%s,TRUE)
    """
    try:
        with conn:
            with conn.cursor() as cur:
                # row_index âm để không vi phạm uq_quarantine_entry
                cur.execute(
                    "SELECT COALESCE(MIN(row_index), 0) FROM import_quarantine "
                    "WHERE source_file=%s AND batch_id=%s AND is_tombstone=TRUE",
                    (source_file, batch_id),
                )
                row = cur.fetchone()
                min_idx = row[0] if row and row[0] is not None else 0
                tombstone_idx = min_idx - 1

                cur.execute(sql_insert, (
                    batch_id, source_file, tombstone_idx, source_key,
                    reason, authorized_by,
                ))
        return True
    except Exception as exc:
        logger.error("[CRM-42] db_add_tombstone FAILED: %s", exc)
        return False
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_accepted_rows(report: BatchReport) -> int:
    """
    INSERT/UPSERT tất cả ACCEPTED rows từ report vào bảng tương ứng.
    Trả về số rows thực sự ghi được. Trả về 0 nếu DB không available.
    """
    conn = _get_conn()
    if conn is None:
        return 0

    writer_fn = _ACCEPTED_WRITERS.get(report.source_file)
    accepted = [r for r in report.row_results if r.status == RowStatus.ACCEPTED]

    if not writer_fn or not accepted:
        conn.close()
        return 0

    try:
        with conn:
            with conn.cursor() as cur:
                inserted = writer_fn(cur, accepted)
        logger.info(
            "[CRM-42] write_accepted_rows: batch=%s source=%s inserted=%d",
            report.batch_id, report.source_file, inserted,
        )
        return inserted
    except Exception as exc:
        logger.error("[CRM-42] write_accepted_rows FAILED: %s", exc)
        return 0
    finally:
        conn.close()


def write_quarantine_rows(report: BatchReport) -> int:
    """
    INSERT tất cả QUARANTINED rows từ report vào bảng import_quarantine.
    Thay thế JSONL file. Trả về số rows ghi được. Trả về 0 nếu DB không available.
    KHÔNG ghi batch header (chỉ write_batch_to_db mới ghi header đầy đủ).
    """
    conn = _get_conn()
    if conn is None:
        return 0

    quarantined = [r for r in report.row_results if r.status == RowStatus.QUARANTINED]
    if not quarantined:
        conn.close()
        return 0

    try:
        with conn:
            with conn.cursor() as cur:
                written = _insert_quarantine_rows(cur, report)
        logger.info(
            "[CRM-42] write_quarantine_rows: batch=%s source=%s written=%d",
            report.batch_id, report.source_file, written,
        )
        return written
    except Exception as exc:
        logger.error("[CRM-42] write_quarantine_rows FAILED: %s", exc)
        return 0
    finally:
        conn.close()


def write_batch_to_db(report: BatchReport) -> WriteResult:
    """
    Hàm tổng hợp: gọi cả write_accepted_rows + write_quarantine_rows
    trong 1 transaction duy nhất, ghi batch header, trả WriteResult.

    Dùng từ endpoint POST /api/v1/ingestion/upload.
    """
    result = WriteResult(
        batch_id=report.batch_id,
        source_file=report.source_file,
    )

    conn = _get_conn()
    if conn is None:
        result.db_available = False
        result.errors.append("psycopg2 unavailable or DB unreachable – rows not persisted.")
        logger.warning(
            "[CRM-42] write_batch_to_db skipped for batch=%s source=%s: DB unavailable.",
            report.batch_id, report.source_file,
        )
        return result

    writer_fn = _ACCEPTED_WRITERS.get(report.source_file)
    accepted  = [r for r in report.row_results if r.status == RowStatus.ACCEPTED]

    try:
        with conn:
            with conn.cursor() as cur:
                # 1. ACCEPTED rows → target table
                if writer_fn and accepted:
                    result.inserted_rows = writer_fn(cur, accepted)

                # 2. QUARANTINED rows → import_quarantine
                result.quarantined_rows = _insert_quarantine_rows(cur, report)

                # 3. Batch header audit (chỉ gọi đây, không gọi ở write_quarantine_rows)
                _upsert_batch_header(
                    cur, report,
                    result.inserted_rows,
                    result.quarantined_rows,
                )

        logger.info(
            "[CRM-42] write_batch_to_db OK: batch=%s source=%s "
            "inserted=%d quarantined=%d",
            report.batch_id, report.source_file,
            result.inserted_rows, result.quarantined_rows,
        )
    except Exception as exc:
        logger.error("[CRM-42] write_batch_to_db FAILED batch=%s: %s", report.batch_id, exc)
        result.errors.append(str(exc))
    finally:
        conn.close()

    return result
