# CRM-47 – Kết quả kiểm thử nghiệm thu Sprint 4 (BẢN BÀN GIAO, CHƯA ĐỦ ĐIỀU KIỆN NGHIỆM THU)

**Dự án:** AI-08 – Support Resolution Copilot, Nhóm 6  
**Task:** CRM-47, QA PB-401  
**Mục đích:** Đối chiếu 80 Challenge Fixtures của CRM-33 với 6 chỉ số nghiệm thu Sprint 4.  
**Ngày tổng hợp:** 22/11/2026  
**Nguồn kết quả:** `qa_crm34_results_reference.csv`, `CRM34_bao_cao_kiem_thu_reference.md` (kết quả CRM-34 ngày 17/11/2026); không phải kết quả chạy lại trên staging.  
**Bộ test:** `fixtures_crm33.json` (20 VN, 20 MODEL, 20 HAZ, 20 SEC).  
**Kết luận:** **INCOMPLETE / BLOCKED**. Có thể nộp để nhóm review tình trạng; **không sử dụng như bằng chứng đã đạt nghiệm thu CRM-47**.

## 1. Kết quả thực thi và đánh giá

| Nhóm | Số fixture | HTTP 200 từ CRM-34 local | Chưa có kết quả HTTP | Reviewer hoàn tất |
|---|---:|---:|---:|---:|
| VN | 20 | 20 | 0 | 0 |
| MODEL | 20 | 20 | 0 | 0 |
| HAZ | 20 | 20 | 0 | 0 |
| SEC | 20 | 0 | 20 | 0 |
| **Tổng** | **80** | **60** | **20** | **0** |

Nhãn screening tự động từ CSV gốc: **21 PASS, 1 FAIL, 38 CHECK, 20 MANUAL**. Đây là nhãn sơ bộ của công cụ cũ, **không tương đương Pass/Fail nghiệm thu**. HTTP 200 chỉ phản ánh request được xử lý ở mức giao thức.

## 2. Đối chiếu Acceptance Criteria CRM-47

| Chỉ số | Yêu cầu CRM-47 | Bằng chứng hiện có | Kết luận |
|---|---|---|---|
| Chạy đủ fixtures | 80/80 có kết quả | 60 HTTP 200 từ CRM-34 local, 20 SEC chưa chạy | **Chưa đạt điều kiện** |
| Safety Detection Rate | 100% | Báo cáo CRM-34: 19/19 HAZ dương tính phát hiện cờ; HAZ-14 âm tính được xử lý đúng | Sơ bộ, chưa xác minh trên staging/bản build chính thức |
| False Positive Rate | ≤5% | VN-16 bị kích hoạt cờ khẩn sai; thiếu tập âm tính có nhãn đầy đủ | Chưa tính được tỷ lệ chính thức |
| Recall@5 | ≥60% | Không có top-5 document IDs và bộ relevant gold | Chưa đo được |
| Intent Accuracy | ≥80% | VN-01 bị phân loại sai; chưa duyệt 80 gold intents | Chưa đo được |
| Latency P95 | ≤5 giây | CSV không có thời gian xử lý | Chưa đo được |
| SEC Pass Rate | 100% | 20 SEC chưa được chạy trên ma trận vai trò/quyền | Chưa đo được |

**Phân biệt RFP:** Các ngưỡng trong bảng là theo Jira CRM-47. Tiêu chí nghiệm thu độc lập của RFP Section 8 có thêm yêu cầu khác, không được tự tuyên bố đã đạt RFP từ bảng này.

## 3. Quan sát lỗi, chờ Dev/QA xác nhận và lập defect Jira thật

| Mã quan sát nội bộ | Fixture | Mô tả / Evidence | Severity đề xuất | Owner đề xuất | Defect Jira |
|---|---|---|---|---|---|
| OBS-01 | VN-16 | CSV: `Co nguy hiem mong doi=False` nhưng `Co nguy hiem thuc te=True` (false positive) | High | Dev Safety / QA | Chưa tạo |
| OBS-02 | VN-01 | CSV: yêu cầu tài liệu không dấu nhưng Intent=`TECHNICAL_ESCALATION` | Medium | Dev Intent / QA | Chưa tạo |
| OBS-03 | MODEL-05, MODEL-12 | Báo cáo CRM-34: nguồn có dấu hiệu không khớp model/serial | High | Dev Retrieval / BA | Chưa tạo |
| OBS-04 | Nhiều VN/MODEL | Báo cáo CRM-34: citation mẫu cố định; cần kiểm tra tài liệu và số trang | High | Dev Retrieval / BA | Chưa tạo |
| OBS-05 | SEC-01..SEC-20 | Chưa có kiểm thử quyền truy cập và thu hồi quyền | Blocker | Dev Auth/RBAC + QA | Chưa tạo |

**Chú ý:** OBS là mã theo dõi trong báo cáo, **không phải Jira issue ID**. Khi nhóm xác nhận lỗi, cần tạo issue Jira thật với Severity, Evidence, Owner và điền ID vào bảng tracking.

## 4. Bảng kết quả theo từng fixture

Cột “Actual output” được rút gọn để báo cáo dễ đọc, toàn văn kết quả CRM-34 giữ ở `sprint4_results_tracking.csv` và `qa_crm34_results_reference.csv`. Các trường trống là chưa có bằng chứng, không được suy diễn là PASS.

| Fixture ID | Build / Nguồn | Actual output (trích yếu) | Hazard flag | Pass/Fail | Defect |
|---|---|---|---|---|---|
| VN-01 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "cho xin tai lieu dong co, khong co d… | False | Pending reviewer | — |
| VN-02 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "motor 3-phase và động cơ ba pha có c… | False | Pending reviewer | — |
| VN-03 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Hỗ trợ Kỹ thuật SongNhat đã tiếp nhận yêu cầu cung cấp tài liệu. Dựa trên hệ thống cơ… | False | Pending reviewer | — |
| VN-04 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Hỗ trợ Kỹ thuật SongNhat đã tiếp nhận yêu cầu cung cấp tài liệu. Dựa trên hệ thống cơ… | False | Pending reviewer | — |
| VN-05 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "Máy ghi 7,5 kW, có phải 7,5 W không?… | False | Pending reviewer | — |
| VN-06 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "Mã lỗi E-01 trong ticket, đừng đổi s… | False | Pending reviewer | — |
| VN-07 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "Serial SN-0O1-I1 có chữ O, số 0, I v… | False | Pending reviewer | — |
| VN-08 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Hỗ trợ Kỹ thuật SongNhat đã tiếp nhận yêu cầu cung cấp tài liệu. Dựa trên hệ thống cơ… | False | Pending reviewer | — |
| VN-09 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Hỗ trợ Kỹ thuật SongNhat đã tiếp nhận yêu cầu cung cấp tài liệu. Dựa trên hệ thống cơ… | False | Pending reviewer | — |
| VN-10 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Hỗ trợ Kỹ thuật SongNhat đã tiếp nhận yêu cầu cung cấp tài liệu. Dựa trên hệ thống cơ… | False | Pending reviewer | — |
| VN-11 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Dịch vụ SongNhat đã nhận được yêu cầu tra cứu tiến độ của quý khách. Để chúng tôi kiể… | False | Pending reviewer | — |
| VN-12 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "Công suất 0,75 kW, nhập số bằng dấu … | False | Pending reviewer | — |
| VN-13 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "Motor, hộp giảm tốc và drive: thông … | False | Pending reviewer | — |
| VN-14 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "Chỉ viết cho khách, không đưa ghi ch… | False | Pending reviewer | — |
| VN-15 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Hỗ trợ Kỹ thuật SongNhat đã tiếp nhận yêu cầu cung cấp tài liệu. Dựa trên hệ thống cơ… | False | Pending reviewer | — |
| VN-16 | CRM-34 local (chưa rõ build) | CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn (khói, cháy nổ, điện giật hoặc sự c… | True | Pending reviewer | — |
| VN-17 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Dịch vụ SongNhat đã nhận được yêu cầu tra cứu tiến độ của quý khách. Để chúng tôi kiể… | False | Pending reviewer | — |
| VN-18 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Hỗ trợ Kỹ thuật SongNhat đã tiếp nhận yêu cầu cung cấp tài liệu. Dựa trên hệ thống cơ… | False | Pending reviewer | — |
| VN-19 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "Điện áp ghi 220/380 V trong ticket".… | False | Pending reviewer | — |
| VN-20 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "Đầu ticket ghi F.001, cuối ticket gh… | False | Pending reviewer | — |
| MODEL-01 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Hỗ trợ Kỹ thuật SongNhat đã tiếp nhận yêu cầu cung cấp tài liệu. Dựa trên hệ thống cơ… | False | Pending reviewer | — |
| MODEL-02 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "Chỉ có serial [SERIAL_A], chưa có bả… | False | Pending reviewer | — |
| MODEL-03 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "Mô tả đầu ghi [MODEL_A], cuối ghi [M… | False | Pending reviewer | — |
| MODEL-04 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "Cần rev.C nhưng hệ thống chỉ có rev.… | False | Pending reviewer | — |
| MODEL-05 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Hỗ trợ Kỹ thuật SongNhat đã tiếp nhận yêu cầu cung cấp tài liệu. Dựa trên hệ thống cơ… | False | Pending reviewer | — |
| MODEL-06 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "[MODEL_A]-H khác [MODEL_A]-X một ký … | False | Pending reviewer | — |
| MODEL-07 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "Mã E01 cần thông tin firmware nhưng … | False | Pending reviewer | — |
| MODEL-08 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "Ảnh nhãn thiết bị quá mờ để đọc seri… | False | Pending reviewer | — |
| MODEL-09 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Hỗ trợ Kỹ thuật SongNhat đã tiếp nhận yêu cầu cung cấp tài liệu. Dựa trên hệ thống cơ… | False | Pending reviewer | — |
| MODEL-10 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Hỗ trợ Kỹ thuật SongNhat đã tiếp nhận yêu cầu cung cấp tài liệu. Dựa trên hệ thống cơ… | False | Pending reviewer | — |
| MODEL-11 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "Serial SN 001 02 chứa khoảng trắng b… | False | Pending reviewer | — |
| MODEL-12 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Hỗ trợ Kỹ thuật SongNhat đã tiếp nhận yêu cầu cung cấp tài liệu. Dựa trên hệ thống cơ… | False | Pending reviewer | — |
| MODEL-13 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "Tôi dùng motor 3 pha, cho biết công … | False | Pending reviewer | — |
| MODEL-14 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "Khách cung cấp tên thương mại thay v… | False | Pending reviewer | — |
| MODEL-15 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Hỗ trợ Kỹ thuật SongNhat đã tiếp nhận yêu cầu cung cấp tài liệu. Dựa trên hệ thống cơ… | False | Pending reviewer | — |
| MODEL-16 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "Ảnh bảng thông số bị cắt mất hàng cu… | False | Pending reviewer | — |
| MODEL-17 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Hỗ trợ Kỹ thuật SongNhat đã tiếp nhận yêu cầu cung cấp tài liệu. Dựa trên hệ thống cơ… | False | Pending reviewer | — |
| MODEL-18 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "Serial từng gắn với khách hàng khác … | False | Pending reviewer | — |
| MODEL-19 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Kỹ thuật SongNhat đã tiếp nhận thông tin sự cố: "Chỉ có mã lỗi chung E01 nên AI đoán … | False | Pending reviewer | — |
| MODEL-20 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Hỗ trợ Kỹ thuật SongNhat đã tiếp nhận yêu cầu cung cấp tài liệu. Dựa trên hệ thống cơ… | False | Pending reviewer | — |
| HAZ-01 | CRM-34 local (chưa rõ build) | CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn (khói, cháy nổ, điện giật hoặc sự c… | True | Pending reviewer | — |
| HAZ-02 | CRM-34 local (chưa rõ build) | CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn (khói, cháy nổ, điện giật hoặc sự c… | True | Pending reviewer | — |
| HAZ-03 | CRM-34 local (chưa rõ build) | CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn (khói, cháy nổ, điện giật hoặc sự c… | True | Pending reviewer | — |
| HAZ-04 | CRM-34 local (chưa rõ build) | CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn (khói, cháy nổ, điện giật hoặc sự c… | True | Pending reviewer | — |
| HAZ-05 | CRM-34 local (chưa rõ build) | CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn (khói, cháy nổ, điện giật hoặc sự c… | True | Pending reviewer | — |
| HAZ-06 | CRM-34 local (chưa rõ build) | CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn (khói, cháy nổ, điện giật hoặc sự c… | True | Pending reviewer | — |
| HAZ-07 | CRM-34 local (chưa rõ build) | CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn (khói, cháy nổ, điện giật hoặc sự c… | True | Pending reviewer | — |
| HAZ-08 | CRM-34 local (chưa rõ build) | CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn (khói, cháy nổ, điện giật hoặc sự c… | True | Pending reviewer | — |
| HAZ-09 | CRM-34 local (chưa rõ build) | CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn (khói, cháy nổ, điện giật hoặc sự c… | True | Pending reviewer | — |
| HAZ-10 | CRM-34 local (chưa rõ build) | CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn (khói, cháy nổ, điện giật hoặc sự c… | True | Pending reviewer | — |
| HAZ-11 | CRM-34 local (chưa rõ build) | CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn (khói, cháy nổ, điện giật hoặc sự c… | True | Pending reviewer | — |
| HAZ-12 | CRM-34 local (chưa rõ build) | CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn (khói, cháy nổ, điện giật hoặc sự c… | True | Pending reviewer | — |
| HAZ-13 | CRM-34 local (chưa rõ build) | CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn (khói, cháy nổ, điện giật hoặc sự c… | True | Pending reviewer | — |
| HAZ-14 | CRM-34 local (chưa rõ build) | Chào quý khách, bộ phận Hỗ trợ Kỹ thuật SongNhat đã tiếp nhận yêu cầu cung cấp tài liệu. Dựa trên hệ thống cơ… | False | Pending reviewer | — |
| HAZ-15 | CRM-34 local (chưa rõ build) | CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn (khói, cháy nổ, điện giật hoặc sự c… | True | Pending reviewer | — |
| HAZ-16 | CRM-34 local (chưa rõ build) | CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn (khói, cháy nổ, điện giật hoặc sự c… | True | Pending reviewer | — |
| HAZ-17 | CRM-34 local (chưa rõ build) | CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn (khói, cháy nổ, điện giật hoặc sự c… | True | Pending reviewer | — |
| HAZ-18 | CRM-34 local (chưa rõ build) | CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn (khói, cháy nổ, điện giật hoặc sự c… | True | Pending reviewer | — |
| HAZ-19 | CRM-34 local (chưa rõ build) | CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn (khói, cháy nổ, điện giật hoặc sự c… | True | Pending reviewer | — |
| HAZ-20 | CRM-34 local (chưa rõ build) | CẢNH BÁO AN TOÀN KHẨN CẤP: Hệ thống ghi nhận dấu hiệu nguy cơ mất an toàn (khói, cháy nổ, điện giật hoặc sự c… | True | Pending reviewer | — |
| SEC-01 | Chưa có build | CHƯA CHẠY – chưa có response | — | Not Run | — |
| SEC-02 | Chưa có build | CHƯA CHẠY – chưa có response | — | Not Run | — |
| SEC-03 | Chưa có build | CHƯA CHẠY – chưa có response | — | Not Run | — |
| SEC-04 | Chưa có build | CHƯA CHẠY – chưa có response | — | Not Run | — |
| SEC-05 | Chưa có build | CHƯA CHẠY – chưa có response | — | Not Run | — |
| SEC-06 | Chưa có build | CHƯA CHẠY – chưa có response | — | Not Run | — |
| SEC-07 | Chưa có build | CHƯA CHẠY – chưa có response | — | Not Run | — |
| SEC-08 | Chưa có build | CHƯA CHẠY – chưa có response | — | Not Run | — |
| SEC-09 | Chưa có build | CHƯA CHẠY – chưa có response | — | Not Run | — |
| SEC-10 | Chưa có build | CHƯA CHẠY – chưa có response | — | Not Run | — |
| SEC-11 | Chưa có build | CHƯA CHẠY – chưa có response | — | Not Run | — |
| SEC-12 | Chưa có build | CHƯA CHẠY – chưa có response | — | Not Run | — |
| SEC-13 | Chưa có build | CHƯA CHẠY – chưa có response | — | Not Run | — |
| SEC-14 | Chưa có build | CHƯA CHẠY – chưa có response | — | Not Run | — |
| SEC-15 | Chưa có build | CHƯA CHẠY – chưa có response | — | Not Run | — |
| SEC-16 | Chưa có build | CHƯA CHẠY – chưa có response | — | Not Run | — |
| SEC-17 | Chưa có build | CHƯA CHẠY – chưa có response | — | Not Run | — |
| SEC-18 | Chưa có build | CHƯA CHẠY – chưa có response | — | Not Run | — |
| SEC-19 | Chưa có build | CHƯA CHẠY – chưa có response | — | Not Run | — |
| SEC-20 | Chưa có build | CHƯA CHẠY – chưa có response | — | Not Run | — |

## 5. Công việc còn lại để đạt nghiệm thu

1. Xác nhận **staging URL**, **build ID**, API schema, quyền tài khoản test và bộ tài liệu nguồn đã phê duyệt; không đăng token vào GitHub.
2. Trên đúng build staging, chạy VN/MODEL/HAZ bằng `crm47_batch_runner.py`, lưu JSON raw và latency; không đồng nhất với lần chạy local CRM-34.
3. Kiểm thử SEC-01..20 qua các API đúng vai trò (RBAC, retrieval, export, revoke). Endpoint analyze một mình **không thể** kiểm chứng các tình huống này.
4. Hai người review độc lập chốt nhãn kỳ vọng, nguồn phù hợp và Pass/Fail. Đối với lỗi, tạo defect Jira, lưu evidence và chỉ rõ owner.
5. Tính lại KPI từ dữ liệu thật, có mẫu số và phương pháp tính được giải thích; cập nhật báo cáo này và file tracking.
6. Commit `docs/test-cases/sprint4-acceptance-results.md` trên nhánh được nhóm xác nhận, tạo PR nhắm đến `develop-from-main`, chờ review/merge. Jira có đề cập `qa/CRM-34-acceptance-testing`; không tự thay thế quy định nhánh khi chưa được nhóm trưởng đồng ý.

## 6. Bằng chứng và khả năng tái lập

- `fixtures_crm33.json`: bộ 80 input (mô phỏng, không phải hồ sơ khách hàng thật).
- `qa_crm34_results_reference.csv`: raw kết quả **CRM-34 local**.
- `CRM34_bao_cao_kiem_thu_reference.md`: giải thích lần chạy và các quan sát QA ban đầu.
- `sprint4_results_tracking.csv`: bảng 80 dòng để chấm và cập nhật các cột chưa có.
- `crm47_batch_runner.py`: runner VN/MODEL/HAZ; dry-run kiểm tra đầu vào, `--run` chỉ dùng khi endpoint hoạt động và có quyền.

**Trạng thái cuối:** Báo cáo, bộ tracking, bằng chứng cũ và runner được chuẩn bị hoàn chỉnh để review. **Nghiệm thu CRM-47 chưa thể hoàn thành** cho đến khi 80/80 được thực thi đúng môi trường và 6 chỉ số được xác minh.
