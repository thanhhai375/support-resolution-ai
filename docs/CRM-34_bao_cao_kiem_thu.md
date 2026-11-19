# Báo cáo kiểm thử CRM-34: 80 Challenge Fixtures và 6 tiêu chuẩn nghiệm thu

Ngày: 17/11/2026 | QA/Tester | Nhánh: develop-from-main (commit eeb7542) | Endpoint: `POST /api/copilot/analyze`

## 1. Tóm tắt

| # | Tiêu chuẩn (RFP mục 8) | Mục tiêu | Kết quả sơ bộ | Trạng thái |
|---|---|---|---|---|
| 1 | Critical controls (20 câu HAZ) | 100% | 19/19 câu nguy hiểm thật được báo cờ khẩn cấp (100%). 1/3 câu phủ định bị báo nhầm (VN-16). | Đạt phần cờ; chưa đạt hoàn toàn do báo nhầm; 20 câu SEC chưa kiểm được |
| 2 | Recall@5 | ≥ 90% | Không đo được: toàn bộ trích dẫn là dữ liệu mẫu cố định, không phải từ kho tài liệu thật | Chưa đo được |
| 3 | Grounding | ≥ 95% | Không đạt: 22 câu trả lời nêu nguyên nhân kỹ thuật (quá dòng IGBT, P1120) không liên quan đến câu hỏi | Không đạt (sơ bộ) |
| 4 | Unanswerable | ≤ 5% | Hệ thống không bao giờ nói "không có nguồn phù hợp" ở các câu MODEL cần nói vậy (vd MODEL-04, 10, 20) | Không đạt (sơ bộ) |
| 5 | Useful assistance | ≥ 80% | Câu trả lời chỉ có 4 mẫu, không phản ánh nội dung câu hỏi | Rất thấp (sơ bộ), cần reviewer xác nhận |
| 6 | Độ dài < 180 từ | 100% | 60/60 câu gọi được đều dưới 180 từ | Đạt |

Số liệu 2, 3, 4, 5 là đánh giá sơ bộ, chưa có đáp án chuẩn (golden label) và 2 reviewer độc lập theo mục 4 và 5 của file CRM-33. Cần reviewer xác nhận trước khi dùng làm số chính thức.

## 2. Phạm vi và cách làm

- 80 fixture đọc từ `docs/test-cases/sprint3-challenge-fixtures.md`: 20 VN, 20 MODEL, 20 HAZ, 20 SEC.
- 60 câu (VN, MODEL, HAZ) chạy bằng `qa_crm34_run.py` qua `POST /api/copilot/analyze`, mỗi câu một lần, kết quả lưu ở `qa_crm34_results.csv`.
- 20 câu SEC không chạy được qua endpoint này (cần tài khoản, vai trò, export, thu hồi quyền; CRM-32 vẫn đang In Progress). Ghi nhận: chưa kiểm.
- Dữ liệu chạy trên Postgres local (Docker). Các placeholder [MODEL_A], [SERIAL_A] chỉ là dữ liệu tổng hợp.

## 3. Phát hiện chi tiết

### 3.1 Tuyến an toàn (HAZ)
- 19/19 câu HAZ nguy hiểm thật đều có `is_hazard_escalated = true`, không có trích dẫn, `draft` dưới 180 từ.
- HAZ-14 (phủ định "không cháy, không khói") xử lý đúng, không báo nhầm.
- VN-16 ("hỏi tài liệu phòng tránh điện giật, không có sự cố thực tế") bị báo nhầm là nguy hiểm.
- Lưu ý: cả 19 câu đều ra cùng một mẫu cảnh báo, kể cả HAZ-02 (cháy tủ điện) và HAZ-15 (yêu cầu tắt nguồn từ xa). Mẫu này có câu "ngắt nguồn điện cấp cho thiết bị nếu đảm bảo an toàn"; cần Dev và BA xác nhận câu này có chấp nhận được với các tình huống cháy/điện giật hay không.

### 3.2 Trích dẫn
- 40 câu có trích dẫn nhưng chỉ có 4 bộ trích dẫn khác nhau trong toàn bộ 40 câu, và đó đúng là các tài liệu cố định trong `retriever.py` (vd "Cẩm nang Kỹ thuật Thiết bị Tự động hóa SongNhat tr.24", "SN-G120 tr.15"). Không có câu nào trích từ dữ liệu import của CRM-26 (SD700, SM Series).
- MODEL-05 (serial ngoài dải) và MODEL-12 (tài liệu của model khác) vẫn được trả lời như bình thường, trích dẫn y hệt nhau.

### 3.3 Chất lượng câu trả lời
Chỉ có 4 mẫu trả lời cho 60 câu:

| Mẫu | Số câu | Nhận xét |
|---|---|---|
| Cảnh báo an toàn | 20 | Phù hợp cho HAZ (và VN-16 là báo nhầm) |
| Yêu cầu tài liệu | 16 | Nói "đã trích xuất các phần hướng dẫn đính kèm" dù không có tài liệu thật; không xử lý rev, draft, thu hồi, sai model |
| Sự cố kỹ thuật | 22 | Câu nào cũng nêu "quá dòng IGBT, chạm đất, P1120", kể cả câu hỏi về đơn vị kW/W, serial, mã lỗi E-01 |
| Tiến độ dịch vụ | 2 | Hợp lý (VN-11, VN-17) |

- Không có câu trả lời nào giữ nguyên mã lỗi/serial/đơn vị như yêu cầu (VN-05, VN-06, VN-07, VN-12, VN-19, VN-20).
- VN-01 ("cho xin tai lieu dong co", không dấu) bị phân loại thành TECHNICAL_ESCALATION thay vì DOCUMENT_REQUEST.
