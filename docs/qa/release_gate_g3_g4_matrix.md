# Ma trận nghiệm thu Release Gate G3 (Pilot Acceptance) và G4 (Handover Readiness)

Ngày: 28/11/2026 | QA/Tester | Căn cứ: RFP mục 9 (Release gates), mục 8 (tiêu chí chất lượng), Annex D (OPS 01 đến OPS 08)
Nhánh: develop-from-main (commit 5afa4e3)

## Cách đọc

| Trạng thái | Ý nghĩa |
|---|---|
| **Có bằng chứng** | Đã có kết quả kiểm thử, có tài liệu dẫn chứng |
| **Một phần** | Có bằng chứng sơ bộ hoặc chỉ một phần yêu cầu |
| **Chưa có** | Chưa có bằng chứng; không suy diễn là đạt |
| **Không áp dụng** | Điều kiện không tồn tại ở phạm vi dự án này |

**Kết luận tổng:** G3 **chưa đạt** và G4 **chưa đạt**. Bảng này liệt kê khoảng trống còn lại, không phải xác nhận nghiệm thu. Theo RFP mục 9, chưa đạt một chỉ tiêu thì phải nêu nguyên nhân gốc, phạm vi ảnh hưởng và cách khắc phục; ngưỡng không được hạ sau khi thấy kết quả.

## 1. Gate G3: Pilot acceptance

Yêu cầu RFP: 20 ngày làm việc quan sát, báo cáo tổng công sức và mức sử dụng, không còn lỗi nghiêm trọng, cập nhật bài toán giá trị với chi phí thực tế. Dừng hoặc thu hẹp nếu chất lượng hoặc giá trị không đạt.

| # | Yêu cầu G3 | Trạng thái | Bằng chứng hiện có | Khoảng trống / hành động |
|---|---|---|---|---|
| G3-1 | Quan sát 20 ngày làm việc với người dùng thật | **Không áp dụng** | Không có pilot vận hành thật trong dự án | Ghi nhận là ngoài phạm vi môn học; cần quyết định của khách hàng nếu muốn pilot thật |
| G3-2 | Báo cáo tổng công sức và mức sử dụng (Effort and use, mục 8) | **Chưa có** | Không có dữ liệu đo công sức nhân viên | Cần pilot thật (G3-1) |
| G3-3 | Không còn lỗi nghiêm trọng chưa xử lý | **Một phần** | Xem mục 3 (lỗi nghiêm trọng theo định nghĩa RFP) | CRM-67, CRM-68 còn To Do; CRM-69 cần xác nhận lại trên bản build mới |
| G3-4 | Cập nhật bài toán giá trị với chi phí thực tế | **Chưa có** | Không có chi phí vận hành thật; backend chưa gọi AI nên chưa có chi phí gọi mô hình | Cần chi phí thực tế khi gắn AI thật |
| G3-5 | Chất lượng đạt các tiêu chí mục 8 (G2 là điều kiện trước) | **Một phần** | Xem mục 2 | Chưa đo được phần lớn tiêu chí độc lập |

## 2. Tiêu chí chất lượng RFP mục 8 (điều kiện cho G2 và G3)

Nguồn: báo cáo CRM-34 (80 fixture), `docs/test-cases/sprint4-acceptance-results.md` (CRM-47, ghi rõ "INCOMPLETE / BLOCKED"). Hai nguồn này chạy trước khi CRM-43 (Retriever thật) được merge, nên cần chạy lại.

| Tiêu chí (mục 8) | Ngưỡng RFP | Trạng thái | Bằng chứng / khoảng trống |
|---|---|---|---|
| Critical controls | 0 lỗi nghiêm trọng; mọi fixture bắt buộc chặn | **Một phần** | HAZ: 19/19 câu nguy hiểm thật được báo cờ; 1 báo nhầm (VN-16). 20 fixture SEC (quyền, thu hồi) chưa kiểm |
| Case facts | ≥ 95% đúng và ghi nguồn; ≥ 90% sự kiện bắt buộc | **Chưa có** | Chưa có bộ 100 ca sealed, chưa có hai reviewer |
| Retrieval Recall@5 | ≥ 90% | **Chưa có** | Chưa có đáp án chuẩn; kết quả CRM-34 dùng retriever mẫu cũ |
| Grounding | ≥ 95%, 0 trích dẫn bịa | **Chưa có** | Sơ bộ CRM-34: 22 câu nêu nguyên nhân không liên quan; cần chạy lại sau CRM-43 |
| Unanswerable cases | ≤ 5% trả lời sai | **Chưa có** | Sơ bộ CRM-34: hệ thống không bao giờ nói "không có nguồn"; cần chạy lại |
| Useful assistance | ≥ 80% | **Chưa có** | Cần reviewer chấm |
| Effort and use | ≥ 20% giảm công sức, 20 ngày | **Không áp dụng** | Cần pilot thật |
| Độ dài trả lời < 180 từ | 100% | **Có bằng chứng** | CRM-34: 60/60 câu; CRM-48 kiểm lại trên PostgreSQL thật (test flow 2) |

## 3. Lỗi nghiêm trọng (định nghĩa RFP: rò rỉ dữ liệu, hướng dẫn nguy hiểm, bỏ qua duyệt, báo cáo sai việc đã thực hiện)

| Mã | Mô tả | Trạng thái Jira | Phân loại đề xuất | Ghi chú |
|---|---|---|---|---|
| CRM-69 | `PATCH /api/v1/copilot/{id}/approve` không yêu cầu đăng nhập/phân quyền | Done | Ứng viên "bỏ qua duyệt" | Test CRM-48 (`test_flow3_approve_without_token_should_be_rejected`) vẫn xfail trên commit 5afa4e3. Cần chạy lại sau khi bản sửa được merge và bỏ xfail |
| CRM-67 | `schema.sql` thiếu cột của `copilot_packages`, gói hỗ trợ không được lưu | To Do | Lỗi chức năng, ảnh hưởng truy vết duyệt | Chưa sửa |
| CRM-68 | CHECK `approval_status` ('Approved') khác code ('APPROVED'), quyết định duyệt không lưu | To Do | Lỗi chức năng, ảnh hưởng truy vết duyệt | Chưa sửa |
| Quan sát | VN-16 báo nhầm nguy hiểm; "quá nhiệt" bị giữ lại (cần Dev/BA xác nhận) | Chưa tạo ticket | Cần xác nhận | Xem CRM-34 và báo cáo tải mục 5 |

## 4. Gate G4: Handover

Yêu cầu RFP: kiểm thử khôi phục và xóa dữ liệu, tài liệu, cấu hình, bàn giao mã nguồn, xác nhận export thoát, đào tạo chủ sở hữu, chấp nhận nghĩa vụ hỗ trợ.

| # | Yêu cầu G4 | Trạng thái | Bằng chứng hiện có | Khoảng trống / hành động |
|---|---|---|---|---|
| G4-1 | Kiểm thử khôi phục (restore) và xóa dữ liệu | **Chưa có** | Không có kịch bản sao lưu/khôi phục (OPS 04) hay xóa dữ liệu | Cần kịch bản restore trên bản sao lưu thật, RTO 4 giờ / RPO 24 giờ |
| G4-2 | Tài liệu | **Một phần** | Có: đặc tả chức năng US-01, tài liệu CRM-2, README Camunda, `schema.sql`, ERD, bộ Postman, test case sprint 1 đến 4 | Chưa có tài liệu vận hành, cấu hình triển khai, runbook khôi phục, hướng dẫn quản trị |
| G4-3 | Cấu hình và mã nguồn bàn giao | **Một phần** | Mã nguồn trên GitHub, Dockerfile và docker-compose, CI chạy test (có E2E trên PostgreSQL thật) | Chưa có quy trình bàn giao quyền sở hữu, chưa dọn: `backend/support_resolution.db` (SQLite) đang bị commit |
| G4-4 | Export thoát (OPS 08): xuất ca, tham chiếu tri thức, mapping, phiên bản, audit ở định dạng mở | **Chưa có** | Chỉ có export PDF phản hồi đã duyệt (CRM-59/60) | Chưa có export dữ liệu hàng loạt |
| G4-5 | Đào tạo chủ sở hữu | **Chưa có** | Không có tài liệu đào tạo | Cần tài liệu và buổi bàn giao |
| G4-6 | Chấp nhận nghĩa vụ hỗ trợ | **Chưa có** | Không có thỏa thuận hỗ trợ | Ngoài phạm vi kiểm thử QA |

## 5. Kiểm thử vận hành Annex D (OPS 01 đến OPS 08)

| ID | Yêu cầu | Trạng thái | Bằng chứng hiện có |
|---|---|---|---|
| OPS 01 Import | 1.000 dòng đổi mỗi ngày trong 30 phút; báo dòng bị loại | **Một phần** | Ingestion CSV chạy trên PostgreSQL thật (CRM-42, CRM-48 flow 1); chưa thử với 1.000 dòng, trùng lặp, lô trễ, tombstone |
| OPS 02 Response | 5 người dùng đồng thời, P95 ≤ 30 giây, 100 request | **Có bằng chứng, có giới hạn** | `docs/qa/load_test_p95_report.md`: P95 47 ms (toàn bộ) và 51 ms (phân tích Copilot) trên máy QA, chưa có AI thật |
| OPS 03 Reliability | Sẵn sàng 99,5% | **Chưa có** | Chưa có giám sát vận hành |
| OPS 04 Recovery | RTO 4 giờ, RPO 24 giờ | **Chưa có** | Chưa kiểm khôi phục |
| OPS 05 Revocation | Thu hồi quyền khi đang sinh nội dung; dọn cache 5 phút | **Một phần** | Có thu hồi token (CRM-32, test RBAC); chưa kiểm luồng "đang sinh thì thu hồi nguồn/quyền" và dọn cache |
| OPS 06 Limits | Hết ngân sách call/token/chi phí | **Không áp dụng (hiện tại)** | Backend chưa gọi AI thật |
| OPS 07 Export | Kiểm nội dung export; đổi người nhận/bằng chứng sau duyệt thì chặn | **Một phần** | Export PDF làm sạch nội dung (CRM-59/60, 9 unit test); chưa kiểm "đổi người nhận sau duyệt" |
| OPS 08 Exit | Xuất dữ liệu ở định dạng mở và nạp lại | **Chưa có** | Xem G4-4 |

## 6. Việc cần làm để đóng khoảng trống (theo mức ưu tiên cho dự án hiện tại)

1. Sửa và xác nhận CRM-67, CRM-68, CRM-69; bỏ `xfail` trong `backend/tests/test_e2e.py` rồi chạy lại.
2. Chạy lại 80 challenge fixture trên bản build có Retriever thật (CRM-43), và chạy 20 fixture SEC bằng tài khoản có vai trò.
3. Chạy lại kiểm thử tải trên môi trường docker compose của nhóm và khi có AI thật.
4. Bổ sung kịch bản restore (OPS 04) và export dữ liệu (OPS 08) nếu muốn đưa vào hồ sơ G4.
5. Dọn `backend/support_resolution.db` khỏi repo; viết tài liệu vận hành và hướng dẫn bàn giao.
6. G3-1, G3-2, G3-4 và các tiêu chí Effort cần pilot thật; ghi vào hồ sơ là ngoài phạm vi môn học.

## 7. Nguồn dẫn chứng

- RFP `SongNhat_Vietnam_Support_Resolution_Copilot_RFP.pdf`: mục 8, mục 9, Annex D.
- `docs/CRM-34_bao_cao_kiem_thu.md`, `docs/qa_crm34_results.csv`
- `docs/test-cases/sprint4-acceptance-results.md` (CRM-47)
- `backend/tests/test_e2e.py`, `backend/tests/conftest.py` (CRM-48, PR #40); `backend/tests/test_crm60_export_and_audit.py`
- `docs/qa/load_test_p95_report.md` (CRM-66)
- Jira: CRM-34, CRM-47, CRM-48, CRM-59, CRM-60, CRM-65, CRM-67, CRM-68, CRM-69
