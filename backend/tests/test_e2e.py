"""CRM-48 — E2E Integration Test: Upload CSV -> Copilot Analyze -> Approve -> Export PDF.

Chạy trên PostgreSQL thật (testcontainers), không mock DB, không phụ thuộc dữ liệu mock cứng.

Chạy local (cần Docker Desktop đang bật), trong thư mục backend/:
    pytest tests/test_e2e.py -v

Flow:
    1  Upload curated_knowledge_passages.csv -> GET /api/knowledge/passages: total tăng
    2  Tạo ticket -> POST /api/copilot/analyze: cờ nguy hiểm đúng + citations không rỗng, từ DB thật
    3  Duyệt bằng token ENGINEER -> RESOLVED; approval_status = APPROVED trong DB (đang xfail do lỗi schema)
    4  Export PDF: documented skip nếu endpoint chưa có
"""
from __future__ import annotations

import uuid

import pytest

from tests.conftest import SAMPLE_CSV

HAZARD_TEXT = "Tủ điện đang bốc khói, có tia lửa"
NORMAL_TEXT = "Biến tần SD700 báo lỗi E001 quá dòng khi tăng tốc"


# ───────────────────────────── helpers ─────────────────────────────

def _knowledge_items(client, headers, size=100):
    res = client.get("/api/knowledge/passages", params={"size": size}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _create_ticket(client, headers, description, title="E2E ticket"):
    res = client.post(
        "/api/tickets",
        json={"title": title, "description": description, "product_code": "DRIVES", "priority": "HIGH"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


@pytest.fixture(scope="module")
def e2e_ingested(e2e_client, e2e_tokens):
    """Upload curated_knowledge_passages.csv đúng 1 lần; trả về số liệu trước/sau và phản hồi.

    Flow 2 và 3 dùng kho tri thức đã được nạp bởi fixture này (dữ liệu thật, không mock).
    """
    staff = e2e_tokens["staff"]
    # Lần GET đầu cũng khởi tạo sản phẩm DRIVES/MOTORS (cần cho khóa ngoại khi ghi CSV).
    before = _knowledge_items(e2e_client, staff)["total"]
    with open(SAMPLE_CSV, "rb") as f:
        res = e2e_client.post(
            "/api/v1/ingestion/upload",
            files={"file": ("curated_knowledge_passages.csv", f, "text/csv")},
            data={"import_type": "increment"},
        )
    after = _knowledge_items(e2e_client, staff)["total"]
    return {"response": res, "before": before, "after": after}


# ───────────────────────────── kiểm tra nền ─────────────────────────────

def test_backend_runs_on_real_postgres(e2e_client, e2e_app):
    """Bảo đảm test chạy trên PostgreSQL thật, không phải SQLite in-memory."""
    assert e2e_app.state.main_module.engine.dialect.name == "postgresql"


# ───────────────────────────── Flow 1 ─────────────────────────────

def test_flow1_upload_csv_increases_knowledge_total(e2e_ingested):
    res = e2e_ingested["response"]
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["db_available"] is True, f"Ingestion không kết nối được DB: {body['message']}"
    assert body["inserted_rows"] > 0, f"Không có dòng nào được ghi vào DB: {body['message']}"

    before, after = e2e_ingested["before"], e2e_ingested["after"]
    assert after > before, f"total không tăng sau khi upload CSV (trước={before}, sau={after})"


def test_flow1_uploaded_rows_are_in_database(e2e_ingested, e2e_sql):
    """Dữ liệu CSV thực sự nằm trong bảng knowledge_passages (kiểm trực tiếp bằng SQL)."""
    rows = e2e_sql("SELECT count(*) FROM knowledge_passages WHERE is_approved = true")
    assert rows[0][0] > 0


# ───────────────────────────── Flow 2 ─────────────────────────────

def test_flow2_normal_ticket_returns_citations_from_real_db(e2e_client, e2e_tokens, e2e_ingested):
    staff = e2e_tokens["staff"]
    _create_ticket(e2e_client, staff, NORMAL_TEXT)

    res = e2e_client.post("/api/copilot/analyze", json={"ticket_description": NORMAL_TEXT}, headers=staff)
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["is_hazard_escalated"] is False
    assert len(body["citations"]) > 0, "citations rỗng cho câu hỏi kỹ thuật thông thường"

    # Citation phải đến từ kho tri thức thật, không phải dữ liệu mock cứng
    db_titles = {
        item["document_title"] for item in _knowledge_items(e2e_client, staff)["items"]
    }
    for cit in body["citations"]:
        assert cit["page_number"] >= 1
        assert cit["document_title"] in db_titles, (
            f"Citation '{cit['document_title']}' không có trong knowledge_passages (có thể là dữ liệu mock)"
        )
    assert len(body["draft"].split()) < 180


def test_flow2_hazard_ticket_is_escalated_without_citations(e2e_client, e2e_tokens):
    staff = e2e_tokens["staff"]
    _create_ticket(e2e_client, staff, HAZARD_TEXT, title="E2E hazard")

    res = e2e_client.post("/api/copilot/analyze", json={"ticket_description": HAZARD_TEXT}, headers=staff)
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["is_hazard_escalated"] is True
    assert body["citations"] == []
    assert body["draft_reply"] == ""
    assert len(body["draft"].split()) < 180


def test_flow2_negated_hazard_is_not_escalated(e2e_client, e2e_tokens):
    """Câu phủ định (HAZ-14 của CRM-33) không được báo nhầm là nguy hiểm."""
    res = e2e_client.post(
        "/api/copilot/analyze",
        json={"ticket_description": "Máy không cháy, không khói, chỉ xin manual"},
        headers=e2e_tokens["staff"],
    )
    assert res.status_code == 200, res.text
    assert res.json()["is_hazard_escalated"] is False


# ───────────────────────────── Flow 3 ─────────────────────────────

def test_flow3_engineer_can_approve_and_staff_cannot(e2e_client, e2e_tokens, e2e_ingested):
    """Phân quyền duyệt: STAFF bị 403, ENGINEER duyệt được và ticket chuyển RESOLVED."""
    staff, engineer = e2e_tokens["staff"], e2e_tokens["engineer"]
    ticket_id = _create_ticket(e2e_client, staff, NORMAL_TEXT, title="E2E approve RBAC")

    denied = e2e_client.patch(f"/api/tickets/{ticket_id}/copilot/approve", headers=staff)
    assert denied.status_code == 403, denied.text

    ok = e2e_client.patch(f"/api/tickets/{ticket_id}/copilot/approve", headers=engineer)
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "RESOLVED"


@pytest.mark.xfail(
    reason=(
        "BUG: duyệt Support Package không lưu được vào DB tạo từ docs/database/schema.sql: "
        "(1) bảng copilot_packages thiếu cột intent/next_step/draft/draft_response nên gói không được lưu; "
        "(2) CHECK chk_copilot_approval_status chỉ cho 'Pending/Approved/Rejected' nhưng code ghi 'APPROVED'. "
        "Bỏ xfail sau khi Dev sửa."
    ),
    strict=True,
)
def test_flow3_approval_status_persisted_as_approved(e2e_client, e2e_tokens, e2e_users, e2e_sql, e2e_ingested):
    """Flow 3 theo CRM-48: sinh Support Package -> ENGINEER duyệt -> approval_status = APPROVED trong DB."""
    staff = e2e_tokens["staff"]
    ticket_id = _create_ticket(e2e_client, staff, NORMAL_TEXT, title="E2E approve persist")

    gen = e2e_client.post(
        f"/api/tickets/{ticket_id}/copilot/generate",
        json={"ticket_description": NORMAL_TEXT},
        headers=staff,
    )
    assert gen.status_code == 200, gen.text

    before = e2e_sql("SELECT approval_status FROM copilot_packages WHERE ticket_id = %s", (ticket_id,))
    assert before and before[0][0].upper() == "PENDING", "Support Package chưa được lưu vào copilot_packages"

    approved = e2e_client.patch(
        f"/api/v1/copilot/{ticket_id}/approve",
        json={"approved_by": e2e_users["engineer"]["email"]},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["approval_status"] == "APPROVED"
    assert approved.json()["persisted"] is True, "Quyết định duyệt không được lưu vào DB"

    after = e2e_sql("SELECT approval_status FROM copilot_packages WHERE ticket_id = %s", (ticket_id,))
    assert after[0][0].upper() == "APPROVED"


@pytest.mark.xfail(
    reason="BUG CANDIDATE: PATCH /api/v1/copilot/{id}/approve chưa yêu cầu đăng nhập/role "
    "(approval_router không có Depends(require_role)). Bỏ xfail khi đã sửa.",
    strict=True,
)
def test_flow3_approve_without_token_should_be_rejected(e2e_client):
    res = e2e_client.patch(
        f"/api/v1/copilot/{uuid.uuid4()}/approve",
        json={"approved_by": "nobody@example.com"},
    )
    assert res.status_code in (401, 403)


# ───────────────────────────── Flow 4 ─────────────────────────────

def test_flow4_export_pdf(e2e_app):
    """Export PDF: documented skip khi endpoint chưa tồn tại (CRM-41 đang In Progress)."""
    export_paths = [
        r.path for r in e2e_app.routes
        if "export" in getattr(r, "path", "") and "access/export-check" not in r.path
    ]
    if not export_paths:
        pytest.skip("Endpoint export PDF chưa implement (CRM-41 In Progress) - documented skip theo CRM-48")
    pytest.fail(f"Đã có endpoint export {export_paths}: hãy viết test cho Flow 4 rồi bỏ skip này")
