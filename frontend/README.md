# CRM Frontend – Application Shell (CRM-18)

React 18 + TypeScript + Vite, React Router **v6**, **TailwindCSS 3** và **Lucide React**. Staff Workspace sử dụng sidebar SONGNHAT xanh navy, nền lavender và màu nhấn xanh tím theo ảnh thiết kế.

## Chạy frontend

```bash
npm ci
npm run dev
```

Mở `http://localhost:5173`. Chưa đăng nhập sẽ chuyển về `/login`.

## Routing và layout

### Test giao diện không cần backend

Tạo `frontend/.env.local` với `VITE_ENABLE_DEMO_AUTH=true`, sau đó chạy `npm run dev` (khởi động lại Vite nếu đang chạy). Đăng nhập bằng **demo@supportai.vn / Demo@123**, hoặc bấm **Điền tài khoản demo** trên Login rồi đăng nhập. Demo dùng ticket mẫu trực tiếp, không gọi API đăng nhập/ticket. Phiên hết hạn sau một giờ; Logout và bảo vệ route vẫn hoạt động. Đặt biến về `false` để dùng backend thật.

Chế độ demo chỉ bật khi Vite chạy development; bản build production luôn tắt và từ chối token được đánh dấu demo. Tài khoản này không tồn tại trên backend. Chạy `npm run test:demo` để kiểm tra chế độ không cần API; `npm run test:e2e` kiểm tra luồng thường với demo bị tắt.

`src/router.tsx` khai báo `RouteObject[]` cho `createBrowserRouter`. `ProtectedRoute` bao quanh toàn bộ workspace; `MainLayout` dùng `Outlet` và `NavLink` để chuyển trang qua History API.

| Route | Màn hình | Truy cập |
| --- | --- | --- |
| `/login` | Đăng nhập | Công khai |
| `/register` | Đăng ký tài khoản | Công khai |
| `/` | Chuyển sang `/dashboard` | Cần JWT |
| `/dashboard` | Live Dashboard | Cần JWT |
| `/tickets` | Ticket Feed | Cần JWT |
| `/tickets/:ticketId` | Chi tiết, lịch sử trao đổi và phản hồi ticket | Cần JWT |
| `/knowledge-base` | Thư viện tài liệu (khung giao diện, chưa kết nối API) | Cần JWT |
| `/ai-settings` | Trang chờ triển khai cấu hình AI | Cần JWT |
| `/analytics` | Phân tích dữ liệu hiện có | Cần JWT |
| Đường dẫn khác | Trang không tìm thấy trong workspace | Cần JWT |

Sidebar cố định trên desktop; trên mobile dùng nút mở drawer, backdrop, Escape, khóa cuộn trang và giới hạn focus trong menu. Topbar hiển thị trạng thái kết nối mạng của trình duyệt, avatar theo JWT subject/name và Logout. Trạng thái kết nối này không phải kết quả health check Backend/AI.

`TicketsProvider` giữ dữ liệu ticket khi chuyển trang. Global search chuyển đến `/tickets?search=...`; bảng dùng query string để lọc. Tạo/cập nhật/xóa ticket vẫn dùng hành vi lưu trình duyệt hiện có của CRM-22.

## Đăng nhập và JWT

Tạo `.env` từ `.env.example`:

```env
VITE_API_BASE_URL=
```

Để trống `VITE_API_BASE_URL` để gọi cùng origin; Vite chuyển tiếp `/api` đến `http://127.0.0.1:8080`, tránh lỗi CORS khi chạy local. Với API khác, đặt URL backend và cấu hình CORS tương ứng. Khi deploy production, cấu hình reverse proxy `/api` hoặc đặt URL API công khai.

Trang đăng nhập gửi `POST ${VITE_API_BASE_URL}/api/auth/login` với JSON `{ "email": "...", "password": "..." }`, phù hợp contract Backend CRM-19. Phản hồi cần có `{ "access_token": "<JWT>", "token_type": "bearer" }`.

- JWT chỉ được lưu ở `sessionStorage.access_token`, không đọc token từ localStorage. Cần `sub` và `exp`, kiểm tra thêm `nbf` nếu có.
- Token thiếu, sai định dạng hoặc hết hạn sẽ chuyển về `/login` bằng `replace`, giữ đường dẫn nội bộ để quay lại sau khi đăng nhập.
- Token hết hạn trong lúc sử dụng sẽ kết thúc phiên. Mỗi tab có phiên sessionStorage riêng.
- Logout xóa token và đưa về `/login`; Back không mở lại workspace khi chưa đăng nhập.
- `GET /api/tickets` đính kèm `Authorization: Bearer <token>`. Khi API ticket lỗi, vẫn dùng fallback mock data có sẵn; đăng nhập không tạo token giả hay tự bỏ qua xác thực.

Frontend chỉ kiểm tra phiên và thời hạn JWT, **không xác minh chữ ký**. Backend phải xác minh chữ ký, quyền truy cập và thời hạn token cho từng API. Nhánh CRM-18 không chứa Backend CRM-19; cần chạy backend tương thích ở cổng 8080 để đăng nhập thật.

## Kiểm tra

Trang đăng ký theo cùng bố cục hai cột của Login, gồm họ tên, email, mật khẩu tối thiểu 8 ký tự/tối đa 72 byte, xác nhận mật khẩu và đồng ý điều khoản. Form gửi `POST /api/auth/register` với `{ full_name, email, password }`. Khi API trả thành công sẽ chuyển về `/login`, điền email và hiển thị thông báo; không tự tạo JWT. Backend CRM-19 hiện **chưa có endpoint đăng ký**, cần bổ sung endpoint tương thích để tạo tài khoản thật. Khi gặp HTTP 404/405, frontend hiển thị rõ chức năng máy chủ chưa hỗ trợ; HTTP 409 hiển thị email trùng.

```bash
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e
```

`typecheck` chạy `tsc --noEmit` cho ứng dụng và cấu hình Vite; `build` chạy typecheck rồi build production. Playwright kiểm tra redirect tất cả route nội bộ, token lỗi/hết hạn, đăng nhập thành công/thất bại bằng API giả lập, quay lại route yêu cầu, logout/Back, phạm vi phiên sessionStorage, điều hướng không reload và giữ ticket khi chuyển trang. Kiểm tra responsive ở 320, 390, 768 và 1440 px. Các test dùng API giả lập, không thay thế kiểm thử tích hợp với backend thật.

Khi deploy, cấu hình web server trả `index.html` cho đường dẫn frontend chưa khớp file (SPA fallback), để mở trực tiếp `/dashboard` và `/tickets` hoạt động.

## Thiết kế

Giao diện shell được đối chiếu với ảnh SONGNHAT do người dùng cung cấp: nền lavender, sidebar xanh navy, thẻ viền mảnh, xanh tím làm màu chính; trang Login chia hai cột với phần giới thiệu nền tối. Số liệu Dashboard vẫn tính từ dữ liệu ticket hiện có. Ticket Detail giữ nghiệp vụ hiện có; màn hình AI Evidence Review chưa thuộc phạm vi bộ khung này.

Tailwind được cấu hình tại `tailwind.config.js` và `postcss.config.js`, quét `src/**/*.{js,ts,jsx,tsx}`. Preflight tắt để giữ CSS component hiện có. `src/workspace.css` định nghĩa giao diện SONGNHAT; Knowledge Base dùng utility Tailwind và hiện hiển thị trạng thái rỗng, chưa kết nối API tài liệu.

Chi tiết ticket hỗ trợ phản hồi, dùng gợi ý mẫu, cập nhật trạng thái/mức ưu tiên và xóa ticket; các thay đổi vẫn lưu trên trình duyệt. Gợi ý là mẫu minh họa, chưa gọi dịch vụ AI. Các bộ lọc trạng thái, mức ưu tiên, người phụ trách và phân trang hoạt động trên dữ liệu hiện có.

## Cấu trúc

- `src/auth/`: quản lý phiên JWT, expiry và đồng bộ tab.
- `src/components/ProtectedRoute.tsx`: bảo vệ route và giữ đường dẫn yêu cầu.
- `src/layouts/MainLayout.tsx`: sidebar, topbar, tìm kiếm và outlet.
- `src/router.tsx`: cấu hình route TypeScript.
- `src/context/TicketsProvider.tsx`: dữ liệu và thao tác ticket dùng chung.
- `src/pages/`: Login, Register, Dashboard, TicketList, TicketDetail, AISettings, Analytics.
- `src/layouts/AuthLayout.tsx`: bố cục chung cho Login và Register.
- `src/styles.css`, `src/shell.css`, `src/wireframe.css`: giao diện chung, shell responsive và phong cách theo ảnh thiết kế.
- `tests/shell.spec.ts`: kiểm thử acceptance trên trình duyệt.
