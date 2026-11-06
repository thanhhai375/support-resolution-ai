# CRM-22 – Dashboard & Ticket Live Feed

Giao diện CRM-22 được dựng theo mẫu Figma người dùng cung cấp: tông xanh/trắng, thanh điều hướng bên trái, Dashboard và Ticket List.

## Chức năng
- Dashboard: tổng số ticket, AI Resolution Rate, thời gian phản hồi trung bình, ticket cần chú ý, biểu đồ xu hướng, phân bố trạng thái, AI Insight.
- Ticket List: bảng ticket, trạng thái AI Solved / Processing / Escalated, tìm kiếm theo tiêu đề/mã/khách hàng, lọc trạng thái, loading skeleton.
- Điều hướng giữa Tổng quan, Danh sách ticket và Phân tích dữ liệu.
- Gọi `GET /api/tickets`; khi API lỗi hoặc backend chưa chạy, hiển thị mock data để demo.

## Chạy dự án
Cài Node.js LTS, mở thư mục bằng VS Code rồi chạy:

```bash
npm install
npm run dev
```

Mở `http://localhost:5173`.

## Cấu hình Backend
Tạo file `.env` tại thư mục gốc:

```env
VITE_API_BASE_URL=http://localhost:8080
```

Frontend gọi `${VITE_API_BASE_URL}/api/tickets`. API hiện giả định trả về mảng ticket hoặc `{ "data": [...] }`. Nếu Backend có DTO khác, điều chỉnh `src/services/ticketService.ts`.

## Build kiểm tra
```bash
npm run build
```

## Cấu trúc
- `src/types/ticket.ts`: kiểu dữ liệu Ticket.
- `src/services/ticketService.ts`: API và mock data.
- `src/components/StatCard.tsx`: thẻ thống kê.
- `src/components/TicketLiveFeedTable.tsx`: bảng, tìm kiếm, lọc và skeleton.
- `src/App.tsx`: Dashboard và điều hướng.
- `src/styles.css`: CSS responsive.
