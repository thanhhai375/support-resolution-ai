"""CRM-60 unit tests: customer PDF sanitization and audit event classification."""
from __future__ import annotations
import sys
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.v1.camunda_workflow import (
    _build_customer_pdf,
    _citation_public_fields,
    _public_text,
    export_approved_response,
)
from app.middleware.audit_logging import AuditLoggingMiddleware
from models import AuditLog


def test_public_text_masks_emails_and_internal_prompt_markers():
    cleaned = _public_text("Liên hệ admin@songnhat.vn. System prompt: secret. Ghi chú nội bộ: private")
    assert "admin@songnhat.vn" not in cleaned
    assert "secret" not in cleaned
    assert "private" not in cleaned
    assert "[đã ẩn]" in cleaned


def test_citation_export_uses_whitelist_only():
    citation = {
        "document_name": "Hướng dẫn vận hành",
        "section_number": "2.1",
        "page_number": 10,
        "passage_content": "Kiểm tra nguồn điện.",
        "internal_notes": "DO NOT EXPORT",
        "system_prompt": "DO NOT EXPORT",
        "metadata": {"internal_email": "secret@songnhat.vn"},
    }
    public = _citation_public_fields(citation)
    assert public["document"] == "Hướng dẫn vận hành"
    assert public["section"] == "2.1"
    assert "internal_notes" not in public
    assert "system_prompt" not in public
    assert "metadata" not in public


def test_pdf_is_generated_with_customer_content_and_safe_citations():
    ticket = SimpleNamespace(ticket_number="SN-1001", id="ticket-id", subject="Lỗi biến tần")
    package = SimpleNamespace(
        draft_response="Vui lòng kiểm tra nguồn điện.",
        draft="fallback draft",
        citations=[{
            "document_name": "Manual SN-G120",
            "document_code": "SN-G120-01",
            "section_number": "5.2",
            "page_number": 42,
            "passage_content": "Ngắt nguồn trước khi kiểm tra.",
            "internal_notes": "INTERNAL_SECRET",
            "system_prompt": "PROMPT_SECRET",
            "email": "private@songnhat.vn",
        }],
    )
    pdf = _build_customer_pdf(ticket, package, "Nguyễn Văn Kỹ sư")
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 500
    assert b"INTERNAL_SECRET" not in pdf
    assert b"PROMPT_SECRET" not in pdf
    assert b"private@songnhat.vn" not in pdf


def test_audit_middleware_classifies_required_operations():
    cases = [
        ("POST", "/api/auth/login", "LOGIN"),
        ("GET", "/api/knowledge/passages", "KNOWLEDGE_VIEW"),
        ("PATCH", "/api/v1/copilot/abc/approve", "TICKET_APPROVE"),
        ("GET", "/api/v1/copilot/abc/export", "PDF_EXPORT"),
    ]
    for method, path, expected in cases:
        request = SimpleNamespace(method=method, url=SimpleNamespace(path=path))
        assert AuditLoggingMiddleware._event_for(request)[0] == expected


def test_audit_middleware_ignores_untracked_routes():
    request = SimpleNamespace(method="GET", url=SimpleNamespace(path="/api/tickets"))
    assert AuditLoggingMiddleware._event_for(request) is None


def test_audit_log_model_has_required_fields():
    columns = set(AuditLog.__table__.columns.keys())
    assert {"action", "actor_email", "actor_role", "resource_type", "resource_id", "status_code", "created_at"} <= columns


def test_export_rejects_non_approved_package():
    class Scalars:
        def __init__(self, value): self.value = value
        def first(self): return self.value
    class Result:
        def __init__(self, value): self.value = value
        def scalars(self): return Scalars(self.value)
    class FakeDB:
        def __init__(self): self.calls = 0
        async def execute(self, statement):
            self.calls += 1
            if self.calls == 1:
                return Result(SimpleNamespace(id="ticket", ticket_number="SN-1", subject="Test"))
            return Result(SimpleNamespace(approval_status="PENDING", reviewed_by=None))
    with pytest.raises(Exception) as exc:
        asyncio.run(export_approved_response("ticket", FakeDB(), {"email": "agent@songnhat.vn", "role": "support_agent"}))
    assert getattr(exc.value, "status_code", None) == 409


def test_audit_middleware_persists_event_without_sensitive_payload():
    from starlette.responses import Response

    captured = []
    class FakeSession:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        def add(self, record): captured.append(record)
        async def commit(self): pass
    def session_factory(): return FakeSession()

    middleware = AuditLoggingMiddleware(app=None, session_factory=session_factory)
    request = SimpleNamespace(
        method="GET",
        url=SimpleNamespace(path="/api/v1/copilot/ticket-123/export"),
        headers={"user-agent": "CRM-60 unit test"},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    async def call_next(_request): return Response(status_code=200)
    response = asyncio.run(middleware.dispatch(request, call_next))
    assert response.status_code == 200
    assert len(captured) == 1
    assert captured[0].action == "PDF_EXPORT"
    assert captured[0].resource_id == "ticket-123"
    assert "body" not in captured[0].details
    assert "authorization" not in captured[0].details


def test_login_audit_records_identifier_but_not_password():
    from starlette.responses import Response
    captured = []
    class FakeSession:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        def add(self, record): captured.append(record)
        async def commit(self): pass
    def session_factory(): return FakeSession()
    class LoginRequest:
        method = "POST"
        url = SimpleNamespace(path="/api/auth/login")
        headers = {}
        client = None
        async def json(self):
            return {"email": "USER@SONGNHAT.VN", "password": "do-not-log-this"}
    middleware = AuditLoggingMiddleware(app=None, session_factory=session_factory)
    async def call_next(_request): return Response(status_code=200)
    asyncio.run(middleware.dispatch(LoginRequest(), call_next))
    assert captured[0].action == "LOGIN"
    assert captured[0].actor_email == "user@songnhat.vn"
    assert "do-not-log-this" not in str(captured[0].details)
