# Camunda 7 BPMN Workflow — Ticket Triage (`CRM-44`)

Tài liệu hướng dẫn khởi chạy nhanh **Camunda 7 BPM Platform**, triển khai quy trình **`ticket-triage.bpmn`** và chạy **Python External Task Worker** định tuyến 3 luồng Intent trong vòng **5 phút**.

---

## 1. Kiến trúc Quy trình `camunda/ticket-triage.bpmn`

Quy trình `ticket-triage` (`SongNhat Copilot Ticket Triage Workflow`) thực thi điều phối tự động thông qua 2 cổng quyết định (Gateway) và 3 External Service Task:

1. **Safety Gateway (`Gateway_SafetyCheck`):**
   - Kiểm tra biến `${is_hazard_escalated == true}`.
   - Nếu **Nguy hiểm** (khói, cháy nổ, điện giật, chuyển động bất ngờ): Chuyển thẳng tới `Task_HazardEscalation` (`Chuyển khẩn cấp cho Kỹ sư An toàn`) $\rightarrow$ `EndEvent_HazardEscalated`. Tuyệt đối không sinh hướng dẫn vận hành tự động.
2. **Intent Routing Gateway (`Gateway_IntentRouting`):**
   - Định tuyến các ticket an toàn sang 3 External Task Topic dựa trên biến `intent`:
     - `DOCUMENT_REQUEST` $\rightarrow$ `Task_DocumentRequest` (Topic: `triage.document_request`)
     - `SERVICE_PROGRESS` $\rightarrow$ `Task_ServiceProgress` (Topic: `triage.service_progress`)
     - `TECHNICAL_ESCALATION` (default) $\rightarrow$ `Task_TechnicalEscalation` (Topic: `triage.technical_escalation`)
3. **Human Approval (`Task_HumanApproval`):**
   - Sau khi Python External Task Worker hoàn tất xử lý topic tương ứng, tiến trình chuyển sang User Task chờ nhân viên kỹ thuật duyệt / chỉnh sửa bản nháp trước khi hoàn tất (`EndEvent_TriageCompleted`).

---

## 2. Hướng dẫn Setup & Chạy trong 5 phút

### Bước 1: Khởi động Camunda 7 bằng Docker Compose

Từ thư mục gốc dự án, chạy lệnh:

```powershell
docker compose -f camunda/docker-compose.camunda.yml up -d
```

* File `camunda/ticket-triage.bpmn` được mount tự động vào `/camunda/configuration/resources/ticket-triage.bpmn` và tự động deploy ngay khi container khởi động.
* Mặc định Camunda chạy tại cổng `8080` (`CAMUNDA_PORT=8080`). Nếu bạn chạy chung với FastAPI trên cùng máy ở cổng `8080`, có thể đổi cổng Camunda sang `8088`:
  ```powershell
  $env:CAMUNDA_PORT="8088"; docker compose -f camunda/docker-compose.camunda.yml up -d
  ```

### Bước 2: Kiểm tra Camunda REST API & Đăng nhập Cockpit

1. **Kiểm tra REST API trả về JSON:**
   ```powershell
   curl http://localhost:8080/engine-rest/engine
   # Kết quả: [{"name":"default"}]
   ```
2. **Đăng nhập Camunda Cockpit:**
   - Mở trình duyệt tại: `http://localhost:8080/camunda/app/cockpit/default/`
   - Tài khoản mặc định: **`demo` / `demo`**
   - Vào mục **Processes** $\rightarrow$ xác nhận quy trình **`SongNhat Copilot Ticket Triage Workflow` (`ticket-triage`)** đã hiển thị trên Cockpit.

### Bước 3: Deploy thủ công `ticket-triage.bpmn` qua REST API (nếu cần)

```powershell
curl -X POST http://localhost:8080/engine-rest/deployment/create `
  -F "deployment-name=songnhat-ticket-triage" `
  -F "enable-duplicate-filtering=true" `
  -F "ticket-triage.bpmn=@../camunda/ticket-triage.bpmn"
```

Hoặc gọi hàm Python có sẵn trong `backend/app/camunda/worker.py`:
```python
import asyncio
from app.camunda.worker import deploy_bpmn_to_camunda

asyncio.run(deploy_bpmn_to_camunda(camunda_url="http://localhost:8080"))
```

---

## 3. Tích hợp với Backend FastAPI & Cơ chế Fallback

### 3.1. Chế độ kích hoạt Camunda (`CAMUNDA_URL` được thiết lập)

```powershell
cd backend
$env:CAMUNDA_URL="http://localhost:8080"
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

1. **Khởi chạy phân tích & tạo Process Instance:**
   ```http
   POST /api/copilot/analyze
   Content-Type: application/json

   {
     "ticket_id": "TCK-101",
     "ticket_description": "Cho tôi xin tài liệu hướng dẫn lắp đặt biến tần SINAMICS G120"
   }
   ```
   - Hệ thống phân loại `intent = DOCUMENT_REQUEST`, khởi tạo process instance `ticket-triage` với `businessKey = "TCK-101"`, và định tuyến qua External Task Worker topic `triage.document_request`.

2. **Kiểm tra trạng thái Process Instance của Ticket:**
   ```http
   GET /api/copilot/process/TCK-101/status
   ```
   - Trả về JSON gồm `process_instance_id`, `process_definition_key` (`ticket-triage`), `status` (`WAITING_HUMAN_APPROVAL` hoặc `ESCALATED_HAZARD`), `intent`, `routed_topic`, `current_activity_id`, và `worker_result`.

### 3.2. Approval API (bổ sung từ CRM-41)

Sau khi process dừng ở `Task_HumanApproval`, FE gọi 1 trong 2 API (chạy bằng `app.main:app`):

```http
PATCH /api/v1/copilot/{ticket_id}/approve
{ "approved_by": "engineer@example.com" }

PATCH /api/v1/copilot/{ticket_id}/reject
{ "rejection_reason": "Thiếu số serial", "rejected_by": "manager@example.com" }
```

- `approve` → `approval_status = APPROVED`, lưu `approved_by`, hoàn tất user task trên Camunda (process `COMPLETED`), ticket → `RESOLVED`.
- `reject` → `approval_status = REJECTED`, lưu `rejection_reason`, process `REJECTED`, ticket → `IN_PROGRESS`.
- DB: `approved_by` → `copilot_packages.reviewed_by`, `rejection_reason` → `copilot_packages.review_note` (ghi best-effort; response có cờ `persisted`).
- Duyệt lần 2 cho cùng ticket → `409`; thiếu `approved_by` / `rejection_reason` → `422`.

### 3.3. Chế độ Fallback tương thích ngược (Không đặt `CAMUNDA_URL`)

Khi biến môi trường `CAMUNDA_URL` không được thiết lập:
- `POST /api/copilot/analyze` và `run_copilot_pipeline()` tự động chạy luồng in-process cũ 100%, không phát sinh lỗi kết nối mạng và giữ nguyên toàn bộ kết quả cho các bài kiểm thử cũ (`test_crm24.py`, `test_crm28.py`).

---

## 4. Chạy Kiểm thử Tự động (Pytest)

```powershell
cd backend
.venv\Scripts\python -m pytest tests/test_crm44_camunda_workflow.py -v
```
