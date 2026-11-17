"""
WP 02 Ingestion — Tests (DAT 01, DAT 02, DAT 03)

Covers:
  - Happy path: 3 valid CSV files accepted
  - DAT 01: invalid access_label, bad author_role quarantined
  - DAT 02: stale version overwrite rejected; duplicate row rejected
  - DAT 03: conflicted / pending_review links accepted-but-warned, not auto-merged
  - DAT 03: auto_inference approved link quarantined
  - Quarantine store: persist + read + tombstone
  - Reconciliation: accepted + quarantined == total
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from app.ingestion.quarantine_store import QuarantineStore
from app.ingestion.validator import (
    BatchReport,
    QuarantineReason,
    RowStatus,
    VersionRegistry,
    validate_cases_and_events,
    validate_customer_product_links,
    validate_knowledge_passages,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_DIR = Path(__file__).parent.parent / "app" / "ingestion" / "sample_data"


def _csv(header: str, *rows: str) -> str:
    return "\n".join([header, *rows])


CASE_HEADER = (
    "case_key,account_key,product_code,serial_number,event_id,"
    "event_author_role,original_text,event_time,batch_id,record_version,"
    "owner,access_label,permitted_audience,is_customer_report"
)

LINK_HEADER = (
    "link_id,account_key,product_code,serial_number,link_status,"
    "confidence_score,link_source,confirmed_by,confirmed_at,conflict_note,"
    "batch_id,record_version,owner,access_label,permitted_audience"
)

PASSAGE_HEADER = (
    "passage_key,document_title,document_code,revision,effective_status,"
    "section_name,section_number,page_number,owner,product_applicability,"
    "language,approved_audience,risk_class,supersession_link,passage_content,"
    "is_approved,approved_by,approved_at,batch_id,record_version"
)


def _valid_case(event_id: str = "EVT-001", version: int = 1) -> str:
    return (
        f"CASE-001,ACC-001,MOTORS,SN-001,{event_id},support_agent,"
        f'"Motor lỗi rung",2024-01-15T08:30:00+07:00,'
        f"BATCH-001,{version},support_agent,INTERNAL,"
        f"support_agent|technical_approver,false"
    )


def _valid_link(link_id: str = "LNK-001", status: str = "approved") -> str:
    confirmed = "knowledge_steward" if status == "approved" else ""
    confirmed_at = "2024-01-10T09:00:00+07:00" if status == "approved" else ""
    return (
        f"{link_id},ACC-001,MOTORS,SN-001,{status},"
        f"1.0,crm_registration,{confirmed},{confirmed_at},"
        f",BATCH-001,1,knowledge_steward,INTERNAL,knowledge_steward"
    )


def _valid_passage(key: str = "PKG-001") -> str:
    return (
        f"{key},Motor Manual,MAN-001,1,current,"
        f"Installation,2.1,10,knowledge_steward,MOTORS,"
        f"vi,support_agent|technical_approver,LOW,,"
        f'"Hướng dẫn lắp đặt motor đúng cách trong môi trường công nghiệp.",'
        f"true,knowledge_steward,2024-01-05T08:00:00+07:00,BATCH-001,1"
    )

# ===========================================================================
# 1. Happy-path tests
# ===========================================================================

class TestHappyPath:
    def test_valid_cases_accepted(self) -> None:
        csv = _csv(CASE_HEADER, _valid_case("EVT-001"), _valid_case("EVT-002"))
        report = validate_cases_and_events(csv, batch_id="B001")
        assert report.total_rows == 2
        assert report.accepted == 2
        assert report.quarantined == 0
        assert report.reconciliation_ok

    def test_valid_links_accepted(self) -> None:
        csv = _csv(LINK_HEADER, _valid_link("LNK-001"), _valid_link("LNK-002"))
        report = validate_customer_product_links(csv, batch_id="B001")
        assert report.accepted == 2
        assert report.reconciliation_ok

    def test_valid_passages_accepted(self) -> None:
        csv = _csv(PASSAGE_HEADER, _valid_passage("PKG-001"), _valid_passage("PKG-002"))
        report = validate_knowledge_passages(csv, batch_id="B001")
        assert report.accepted == 2
        assert report.reconciliation_ok

    def test_sample_files_exist(self) -> None:
        assert (SAMPLE_DIR / "cases_and_events.csv").exists()
        assert (SAMPLE_DIR / "customer_product_links.csv").exists()
        assert (SAMPLE_DIR / "curated_knowledge_passages.csv").exists()


# ===========================================================================
# 2. DAT 01 — Provenance validation
# ===========================================================================

class TestDAT01Provenance:
    def test_invalid_access_label_quarantined(self) -> None:
        bad_row = _valid_case().replace(",INTERNAL,", ",PUBLIC_WRONG,")
        csv = _csv(CASE_HEADER, bad_row)
        report = validate_cases_and_events(csv, batch_id="B-DAT01")
        assert report.quarantined == 1
        result = report.row_results[0]
        assert result.status == RowStatus.QUARANTINED
        assert result.quarantine_reason in (
            QuarantineReason.SCHEMA_VIOLATION,
            QuarantineReason.INVALID_PROVENANCE,
        )

    def test_invalid_author_role_quarantined(self) -> None:
        bad_row = _valid_case().replace(",support_agent,", ",hacker_role,")
        csv = _csv(CASE_HEADER, bad_row)
        report = validate_cases_and_events(csv, batch_id="B-DAT01b")
        assert report.quarantined == 1

    def test_missing_owner_quarantined(self) -> None:
        # Remove owner (replace with empty string)
        bad_row = _valid_case().replace(",support_agent,INTERNAL,", ",,INTERNAL,")
        csv = _csv(CASE_HEADER, bad_row)
        report = validate_cases_and_events(csv, batch_id="B-DAT01c")
        assert report.quarantined == 1

    def test_invalid_product_code_quarantined(self) -> None:
        bad_row = _valid_case().replace(",MOTORS,", ",UNKNOWN_PRODUCT,")
        csv = _csv(CASE_HEADER, bad_row)
        report = validate_cases_and_events(csv, batch_id="B-DAT01d")
        assert report.quarantined == 1


# ===========================================================================
# 3. DAT 02 — Import integrity
# ===========================================================================

class TestDAT02ImportIntegrity:
    def test_stale_version_quarantined(self) -> None:
        """Late batch with version=1 cannot overwrite accepted version=2."""
        registry = VersionRegistry()
        # First: accept version 2
        csv_v2 = _csv(CASE_HEADER, _valid_case("EVT-001", version=2))
        validate_cases_and_events(csv_v2, registry=registry, batch_id="B-V2")

        # Second: attempt version 1 (older) → must quarantine
        csv_v1 = _csv(CASE_HEADER, _valid_case("EVT-001", version=1))
        report = validate_cases_and_events(csv_v1, registry=registry, batch_id="B-V1-LATE")
        assert report.quarantined == 1
        assert report.row_results[0].quarantine_reason == QuarantineReason.STALE_VERSION

    def test_same_version_idempotent(self) -> None:
        """Same version = idempotent, should be accepted (not stale)."""
        registry = VersionRegistry()
        csv = _csv(CASE_HEADER, _valid_case("EVT-001", version=1))
        validate_cases_and_events(csv, registry=registry, batch_id="B-V1")
        # Replay same batch
        report = validate_cases_and_events(csv, registry=registry, batch_id="B-V1-REPLAY")
        # Version 1 == 1, not stale → accepted
        assert report.accepted == 1

    def test_duplicate_row_in_batch_quarantined(self) -> None:
        """Exact duplicate within one batch → quarantine second occurrence."""
        row = _valid_case("EVT-DUP")
        csv = _csv(CASE_HEADER, row, row)
        report = validate_cases_and_events(csv, batch_id="B-DUP")
        assert report.total_rows == 2
        assert report.accepted == 1
        assert report.quarantined == 1
        assert report.row_results[1].quarantine_reason == QuarantineReason.DUPLICATE_KEY

    def test_reconciliation_always_holds(self) -> None:
        """accepted + quarantined == total_rows for any input."""
        # Use a row with known-bad field (invalid product code)
        bad_row = _valid_case("EVT-RECON").replace(",MOTORS,", ",INVALID_PROD,")
        csv = _csv(CASE_HEADER, _valid_case("EVT-RECON-GOOD"), bad_row)
        report = validate_cases_and_events(csv, batch_id="B-RECON")
        assert report.reconciliation_ok


# ===========================================================================
# 4. DAT 03 — Identity
# ===========================================================================

class TestDAT03Identity:
    def test_pending_review_link_accepted_with_warning(self) -> None:
        """Conflicted/pending links stay visible but are not auto-merged."""
        pending_row = _valid_link("LNK-PEND", status="pending_review").replace(
            "knowledge_steward,2024-01-10T09:00:00+07:00", ","
        )
        csv = _csv(LINK_HEADER, pending_row)
        report = validate_customer_product_links(csv, batch_id="B-DAT03")
        # Must be ACCEPTED (visible) but with warning
        accepted = [r for r in report.row_results if r.status == RowStatus.ACCEPTED]
        assert len(accepted) >= 1
        result = accepted[0]
        assert any("DAT 03" in str(e) for e in result.errors)

    def test_auto_inference_approved_quarantined(self) -> None:
        """auto_inference link cannot be directly marked 'approved' — DAT 03."""
        bad_row = (
            "LNK-AUTO,ACC-001,MOTORS,SN-001,approved,"
            "0.95,auto_inference,knowledge_steward,2024-01-10T09:00:00+07:00,"
            ",BATCH-001,1,knowledge_steward,INTERNAL,knowledge_steward"
        )
        csv = _csv(LINK_HEADER, bad_row)
        report = validate_customer_product_links(csv, batch_id="B-DAT03b")
        assert report.quarantined == 1

    def test_approved_link_requires_confirmed_by(self) -> None:
        """Approved link without confirmed_by violates DAT 03."""
        bad_row = (
            "LNK-NOCONF,ACC-001,MOTORS,SN-001,approved,"
            "1.0,crm_registration,,,,"
            "BATCH-001,1,knowledge_steward,INTERNAL,knowledge_steward"
        )
        csv = _csv(LINK_HEADER, bad_row)
        report = validate_customer_product_links(csv, batch_id="B-DAT03c")
        assert report.quarantined == 1


# ===========================================================================
# 5. Knowledge Passages — DAT 04
# ===========================================================================

class TestKnowledgePassages:
    def test_missing_required_fields_quarantined(self) -> None:
        """document_title, section_name, etc. are mandatory per DAT 04."""
        bad = (
            "PKG-BAD,,,1,current,,,,knowledge_steward,MOTORS,"
            "vi,support_agent,LOW,,"
            '"Some content that is long enough to pass the min check",'
            "false,,,BATCH-001,1"
        )
        csv = _csv(PASSAGE_HEADER, bad)
        report = validate_knowledge_passages(csv, batch_id="B-KP-BAD")
        assert report.quarantined == 1

    def test_superseded_without_link_quarantined(self) -> None:
        """Superseded passage without supersession_link violates DAT 04."""
        bad = _valid_passage("PKG-SUP").replace(",current,", ",superseded,").replace(",,\"", ",,\"")
        csv = _csv(PASSAGE_HEADER, bad)
        report = validate_knowledge_passages(csv, batch_id="B-KP-SUP")
        # superseded but no supersession_link → quarantined
        assert report.quarantined >= 1

    def test_approved_requires_approved_by(self) -> None:
        """is_approved=true without approved_by → DAT 04 violation."""
        bad = _valid_passage("PKG-APR").replace(
            "true,knowledge_steward,2024-01-05T08:00:00+07:00",
            "true,,"
        )
        csv = _csv(PASSAGE_HEADER, bad)
        report = validate_knowledge_passages(csv, batch_id="B-KP-APR")
        assert report.quarantined == 1


# ===========================================================================
# 6. Quarantine store
# ===========================================================================

class TestQuarantineStore:
    def test_persist_and_retrieve(self, tmp_path: Path) -> None:
        store = QuarantineStore(store_dir=tmp_path)
        bad_row = _valid_case().replace(",INTERNAL,", ",BAD_LABEL,")
        csv = _csv(CASE_HEADER, bad_row)
        report = validate_cases_and_events(csv, batch_id="B-Q-STORE")
        written = store.persist_batch(report)
        assert written == 1

        entries = store.get_by_batch("cases_and_events.csv", "B-Q-STORE")
        assert len(entries) == 1
        assert entries[0]["quarantine_reason"] in (
            "SCHEMA_VIOLATION", "INVALID_PROVENANCE", "MISSING_REQUIRED_FIELD"
        )

    def test_tombstone_recorded(self, tmp_path: Path) -> None:
        store = QuarantineStore(store_dir=tmp_path)
        store.add_tombstone(
            source_file="cases_and_events.csv",
            source_key="EVT-001",
            reason="Customer requested deletion under GDPR",
            authorized_by="admin@songnhat.vn",
            batch_id="BATCH-GDPR-2024",
        )
        entries = store.get_by_key("cases_and_events.csv", "EVT-001")
        assert len(entries) == 1
        assert entries[0]["quarantine_reason"] == "TOMBSTONE"
        assert entries[0]["authorized_by"] == "admin@songnhat.vn"

    def test_statistics(self, tmp_path: Path) -> None:
        store = QuarantineStore(store_dir=tmp_path)
        # Add two quarantined records
        for label in ["BAD_LABEL_1", "BAD_LABEL_2"]:
            bad = _valid_case(f"EVT-{label}").replace(",INTERNAL,", f",{label},")
            csv = _csv(CASE_HEADER, bad)
            report = validate_cases_and_events(csv, batch_id="B-STATS")
            store.persist_batch(report)
        stats = store.statistics("cases_and_events.csv")
        assert stats["total_quarantined"] == 2


# ===========================================================================
# 7. Full sample file integration test
# ===========================================================================

class TestSampleFileIntegration:
    """
    Load the actual sample CSVs and verify at least some rows are accepted
    and known-bad rows (the last row in each file) are quarantined.
    """

    def test_cases_sample(self) -> None:
        content = (SAMPLE_DIR / "cases_and_events.csv").read_text(encoding="utf-8")
        report = validate_cases_and_events(content, batch_id="SAMPLE-CASES")
        assert report.total_rows > 0
        assert report.reconciliation_ok
        # The file has 1 intentionally bad row
        assert report.quarantined >= 1
        assert report.accepted >= 1

    def test_links_sample(self) -> None:
        content = (SAMPLE_DIR / "customer_product_links.csv").read_text(encoding="utf-8")
        report = validate_customer_product_links(content, batch_id="SAMPLE-LINKS")
        assert report.total_rows > 0
        assert report.reconciliation_ok

    def test_passages_sample(self) -> None:
        content = (SAMPLE_DIR / "curated_knowledge_passages.csv").read_text(encoding="utf-8")
        report = validate_knowledge_passages(content, batch_id="SAMPLE-PASSAGES")
        assert report.total_rows > 0
        assert report.reconciliation_ok
        assert report.quarantined >= 1  # PKG-KP-BAD row
