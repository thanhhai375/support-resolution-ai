# US-02 – Auto-categorize Ticket: Test Cases

**Dự án:** AI-08 Support Resolution Copilot  
**Jira User Story:** CRM-2  
**Jira QA Subtask:** CRM-16  
**Người phụ trách:** QA/Tester (PB-401)  
**Sprint:** Sprint 1 – Foundation  
**Tình trạng tài liệu:** Bản nháp, chờ review và xác nhận Acceptance Criteria  

## Tài liệu Test Cases

**[Mở Google Sheets – CRM16_US02_TestCases](https://docs.google.com/spreadsheets/d/16JSLV_XBuRo7mG9N97xztYN2flblv1q5mcjRLervfNw/edit?gid=44334945#gid=44334945)**

Bảng Google Sheets chứa các trường hợp kiểm thử (TC-US02-01 đến TC-US02-25) theo sơ đồ luồng đính kèm ở Jira CRM-2 (`CRM-2-flowchart.png`).

## Phạm vi kiểm thử dự kiến

- Tiếp nhận sự kiện tạo ticket, kiểm tra dữ liệu và xử lý trùng lặp.
- Kiểm tra trạng thái phân loại hiện tại của ticket.
- Chuẩn bị dữ liệu, danh mục category và gửi yêu cầu phân loại đến AI.
- Xử lý lỗi AI và retry, chuyển sang phân loại thủ công khi cần.
- Kiểm tra phản hồi AI, category hợp lệ và ngưỡng confidence.
- Lưu kết quả tự động hoặc chuyển nhân viên duyệt / chỉnh sửa / từ chối.
- Cập nhật trạng thái ticket và ghi nhận kết quả phân loại.

## Lưu ý và các mục cần xác nhận

- Sprint 1 mới **thiết kế flow**, chưa triển khai chức năng nên các Test Cases có trạng thái **Not Run**.
- CRM-2 chưa thể hiện Acceptance Criteria riêng trong phần Description đã được cung cấp. Bảng được xây dựng theo flowchart và **không thay thế Acceptance Criteria chính thức**.
- Cần xác nhận các trường bắt buộc của ticket, danh sách category hợp lệ, ngưỡng confidence, số lần retry/backoff và quy tắc xử lý các nhánh chưa rõ.
- Nhờ nhóm trưởng/BA/Dev review và xác nhận trước khi chốt bản chính thức.

## Nguồn tham chiếu

- [CRM-2 – US-02](https://support-copilot-team.atlassian.net/browse/CRM-2)
- [CRM-16 – Subtask 2 Test Cases US-02](https://support-copilot-team.atlassian.net/browse/CRM-16)
- [CRM-8 – Task Test Cases US-01 & US-02](https://support-copilot-team.atlassian.net/browse/CRM-8)
