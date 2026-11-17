"""End-to-End Test Suite for Task CRM-28: [WP 04] Tích hợp Copilot Pipeline & Support Package."""

import asyncio
import sys
import uuid
from pathlib import Path

# Đảm bảo đường dẫn import cho backend/ và backend/app/
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.schemas.copilot import (
    CopilotPackageResponse,
    IntentEnum,
    SupportPackageOut,
)
from app.services.copilot_engine import CopilotEngineService, run_copilot_pipeline
from main import app
from models import Base, CopilotPackage, KnowledgePassage


async def run_crm28_tests() -> None:
    """Chạy toàn bộ 3 kịch bản chính và các kiểm thử tích hợp mở rộng cho CRM-28."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 80)
    print("BẮT ĐẦU KIỂM THỬ TASK CRM-28: TÍCH HỢP COPILOT PIPELINE & SUPPORT PACKAGE")
    print("=" * 80)

    engine_service = CopilotEngineService()

    # =========================================================================
    # KỊCH BẢN 1: SỰ CỐ KỸ THUẬT (Biến tần lỗi F0022 khi tăng tốc)
    # =========================================================================
    ticket_1 = "Biến tần báo lỗi F0022 khi tăng tốc"
    print("\n" + "-" * 80)
    print(f"KỊCH BẢN 1: Sự cố kỹ thuật thường: '{ticket_1}'")
    print("-" * 80)

    res_1: CopilotPackageResponse = await run_copilot_pipeline(ticket_1)
    print(res_1.model_dump_json(indent=2))

    # Xác minh các trường bắt buộc
    assert res_1.intent == IntentEnum.TECHNICAL_ESCALATION, f"Intent sai: {res_1.intent}"
    assert res_1.summary is not None, "Summary không được None"
    assert res_1.summary.reported_symptom == ticket_1, "reported_symptom không khớp"
    assert bool(res_1.summary.confirmed_observation), "confirmed_observation thiếu nội dung"
    assert bool(res_1.summary.outstanding_questions), "outstanding_questions thiếu nội dung"

    assert len(res_1.missing_facts) > 0, "missing_facts không được rỗng"
    assert any("Serial" in f or "S/N" in f for f in res_1.missing_facts), "missing_facts phải có Serial/S/N"

    assert len(res_1.citations) >= 1, "citations phải có ít nhất 1 trích dẫn kỹ thuật"
    assert bool(res_1.citations[0].document_title), "document_title của citation không được rỗng"
    assert res_1.citations[0].page_number > 0, "page_number phải > 0"
    assert bool(res_1.citations[0].content_snippet), "content_snippet của citation không được rỗng"

    assert bool(res_1.next_step), "next_step không được rỗng"
    assert "chuyên trách" in res_1.next_step or "kiểm tra" in res_1.next_step or "Thu thập" in res_1.next_step

    assert bool(res_1.draft), "draft không được rỗng"
    word_count_1 = len(res_1.draft.split())
    assert word_count_1 < 180, f"Độ dài draft vượt quá 180 từ: {word_count_1} từ"

    assert res_1.is_hazard_escalated is False, "is_hazard_escalated phải là False"
    assert res_1.draft_response == res_1.draft, "draft_response phải đồng bộ với draft"
    print(f"-> KỊCH BẢN 1 ĐẠT CHUẨN! (Độ dài draft: {word_count_1} từ < 180 từ, cờ an toàn: {res_1.is_hazard_escalated})")

    # =========================================================================
    # KỊCH BẢN 2: YÊU CẦU TÀI LIỆU KỸ THUẬT (DOCUMENT_REQUEST)
    # =========================================================================
    ticket_2 = "Khách hàng yêu cầu cung cấp tài liệu hướng dẫn vận hành và sơ đồ đấu nối biến tần SongNhat SN-G120"
    print("\n" + "-" * 80)
    print(f"KỊCH BẢN 2: Yêu cầu tài liệu kỹ thuật: '{ticket_2}'")
    print("-" * 80)

    res_2: CopilotPackageResponse = await run_copilot_pipeline(ticket_2)
    print(res_2.model_dump_json(indent=2))

    assert res_2.intent == IntentEnum.DOCUMENT_REQUEST, f"Intent phải là DOCUMENT_REQUEST: {res_2.intent}"
    assert res_2.summary is not None, "Summary không được None"
    assert len(res_2.missing_facts) > 0, "missing_facts không được rỗng"
    assert len(res_2.citations) >= 1, "citations phải có trích dẫn tài liệu liên quan"
    assert bool(res_2.next_step), "next_step không được rỗng"
    assert "tài liệu" in res_2.next_step.lower() or "đính kèm" in res_2.next_step.lower()

    assert bool(res_2.draft), "draft không được rỗng"
    word_count_2 = len(res_2.draft.split())
    assert word_count_2 < 180, f"Độ dài draft vượt quá 180 từ: {word_count_2} từ"
    assert res_2.is_hazard_escalated is False, "is_hazard_escalated phải là False"
    print(f"-> KỊCH BẢN 2 ĐẠT CHUẨN! (Intent: {res_2.intent}, Độ dài draft: {word_count_2} từ < 180 từ)")

    # =========================================================================
    # KỊCH BẢN 3: SỰ CỐ NGUY HIỂM (Mùi khét, rò điện và tia lửa)
    # =========================================================================
    ticket_3 = "Tủ điện có mùi khét, rò điện và tia lửa"
    print("\n" + "-" * 80)
    print(f"KỊCH BẢN 3: Sự cố nguy hiểm: '{ticket_3}'")
    print("-" * 80)

    res_3: CopilotPackageResponse = await run_copilot_pipeline(ticket_3)
    print(res_3.model_dump_json(indent=2))

    assert res_3.is_hazard_escalated is True, "is_hazard_escalated bắt buộc phải là True"
    assert res_3.citations == [], f"citations khi có nguy hiểm bắt buộc phải rỗng ([]), hiện tại: {res_3.citations}"
    assert bool(res_3.next_step), "next_step không được rỗng"
    assert "ngắt" in res_3.next_step.lower() or "an toàn" in res_3.next_step.lower(), "next_step phải có cảnh báo ngắt nguồn/an toàn"

    assert bool(res_3.draft), "draft an toàn không được rỗng"
    word_count_3 = len(res_3.draft.split())
    assert word_count_3 < 180, f"Độ dài draft an toàn vượt quá 180 từ: {word_count_3} từ"
    assert res_3.draft_reply == "", "draft_reply cho Postman TC-25 phải là chuỗi rỗng khi nguy hiểm"
    print(f"-> KỊCH BẢN 3 ĐẠT CHUẨN! (is_hazard_escalated: True, citations: [], next_step chứa cảnh báo khẩn cấp)")

    # =========================================================================
    # KỊCH BẢN 4: TÍCH HỢP CƠ SỞ DỮ LIỆU (Database Session & Bảng copilot_packages)
    # =========================================================================
    print("\n" + "-" * 80)
    print("KỊCH BẢN 4: Kiểm tra truy vấn KnowledgePassage & lưu bảng copilot_packages")
    print("-" * 80)

    test_engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(test_engine)
    TestSession = sessionmaker(bind=test_engine)
    db_session = TestSession()

    # Nạp 1 bản ghi vào bảng knowledge_passages
    custom_doc = KnowledgePassage(
        document_name="Sổ tay Biến tần SongNhat SN-G120",
        page_number=88,
        passage_content="Mã lỗi F0022 xảy ra khi dòng tải vượt ngưỡng cho phép.",
        is_approved=True,
    )
    db_session.add(custom_doc)
    db_session.commit()

    test_ticket_id = uuid.uuid4()
    res_db = await run_copilot_pipeline(
        ticket_description="Biến tần báo lỗi F0022 khi tăng tốc",
        ticket_id=test_ticket_id,
        db=db_session,
    )

    assert len(res_db.citations) >= 1, "Retriever phải lấy được bản ghi từ bảng knowledge_passages"
    assert res_db.citations[0].document_title == "Sổ tay Biến tần SongNhat SN-G120"
    assert res_db.citations[0].page_number == 88

    # Kiểm tra bản ghi đã được tự động lưu vào copilot_packages
    saved_pkg = db_session.query(CopilotPackage).filter_by(ticket_id=test_ticket_id).first()
    assert saved_pkg is not None, "Bản ghi copilot_packages chưa được lưu vào DB"
    assert saved_pkg.intent == IntentEnum.TECHNICAL_ESCALATION.value
    assert saved_pkg.approval_status == "Pending"
    assert bool(saved_pkg.draft)
    assert bool(saved_pkg.next_step)
    print(f"-> KỊCH BẢN 4 ĐẠT CHUẨN! (Retriever lấy từ DB và lưu copilot_packages thành công: ID {saved_pkg.id})")

    # =========================================================================
    # KỊCH BẢN 5: KIỂM THỬ API ENDPOINTS (FastAPI Router Integration)
    # =========================================================================
    print("\n" + "-" * 80)
    print("KỊCH BẢN 5: Kiểm tra API Endpoints (/api/copilot/analyze & /api/tickets/{id}/copilot/generate)")
    print("-" * 80)

    client = TestClient(app)

    # 5.1 POST /api/copilot/analyze (Standard ticket)
    api_resp_1 = client.post("/api/copilot/analyze", json={"ticket_description": "Biến tần báo lỗi F0022 khi tăng tốc"})
    assert api_resp_1.status_code == 200, f"API 1 trả về mã lỗi: {api_resp_1.status_code}"
    body_1 = api_resp_1.json()
    assert body_1["is_hazard_escalated"] is False
    assert len(body_1["draft"]) > 0
    assert len(body_1["citations"]) > 0

    # 5.2 POST /api/copilot/analyze (Hazard ticket)
    api_resp_2 = client.post("/api/copilot/analyze", json={"ticket_description": "Tủ điện có mùi khét, rò điện và tia lửa"})
    assert api_resp_2.status_code == 200, f"API 2 trả về mã lỗi: {api_resp_2.status_code}"
    body_2 = api_resp_2.json()
    assert body_2["is_hazard_escalated"] is True
    assert body_2["citations"] == []
    assert body_2.get("draft_reply") == ""

    # 5.3 POST /api/tickets/{ticket_id}/copilot/generate
    random_ticket_id = str(uuid.uuid4())
    api_resp_3 = client.post(
        f"/api/tickets/{random_ticket_id}/copilot/generate",
        json={"ticket_description": "Biến tần báo lỗi F0022 khi tăng tốc"},
    )
    assert api_resp_3.status_code == 200, f"API 3 trả về mã lỗi: {api_resp_3.status_code}"
    body_3 = api_resp_3.json()
    assert body_3["intent"] == "TECHNICAL_ESCALATION"
    assert bool(body_3["next_step"])

    print("-> KỊCH BẢN 5 ĐẠT CHUẨN! (Tất cả endpoint API hoạt động hoàn hảo và trả về mã 200 OK)")

    print("\n" + "=" * 80)
    print("TẤT CẢ 5 KỊCH BẢN KIỂM THỬ CRM-28 ĐÃ CHẠY VÀ VƯỢT QUA 100%!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_crm28_tests())
