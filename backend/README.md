# SongNhat Copilot - Backend & Database Environment

## 1. Yêu cầu hệ thống
- Đã cài đặt Doc và Docker Compose trên máy tính.
- Đã cài đặt ứng dụng quản lý database

## 2. Cấu trúc thư mục

```text
backend/
├── docker-compose.yml
├── .env
├── .env.example
├── .gitignore
└── README.md
```

File cấu trúc cơ sở dữ liệu (Database Schema):

```text
../docs/database/schema.sql
```

## 3. Yêu cầu trước khi cài đặt

Cần cài đặt các công cụ sau:

- Docker Desktop
- pgAdmin 4 (không bắt buộc, dùng để quản lý cơ sở dữ liệu bằng giao diện đồ họa).

## 4. Cấu hình môi trường

Sao chép file cấu hình mẫu:

```bash
cp .env.example .env
```

**Cấu hình mặc định:**

- Tên cơ sở dữ liệu (Database): `songnhat_copilot`
- Tên người dùng (Username): `songnhat`
- Mật khẩu (Password): `songnhat_dev`
- Cổng kết nối (Port): `5432`

## 5. Khởi chạy PostgreSQL

Mở Terminal tại thư mục `backend` và chạy lệnh:

```bash
docker compose up -d
```

Docker Compose sẽ khởi chạy 2 dịch vụ:

1. **PostgreSQL Database:** Khởi tạo và vận hành cơ sở dữ liệu PostgreSQL.
2. **Database Initialization:** Thực hiện khởi tạo cơ sở dữ liệu và nạp cấu trúc bảng.

File cấu trúc cơ sở dữ liệu được sử dụng tại:

```text
../docs/database/schema.sql
```

## 6. Kiểm tra các Container

Kiểm tra trạng thái của các container:

```bash
docker compose ps -a
```

Lệnh này giúp kiểm tra các container đang chạy, đã dừng hoặc gặp lỗi.

## 7. Xem nhật ký hoạt động (Logs)

**Xem logs của PostgreSQL:**

```bash
docker compose logs -f db
```

**Xem logs của dịch vụ khởi tạo cơ sở dữ liệu:**

```bash
docker compose logs db-init
```

Các lệnh này giúp theo dõi quá trình hoạt động và phát hiện lỗi nếu có.

## 8. Kết nối bằng pgAdmin 4

Nếu sử dụng pgAdmin 4, hãy nhập các thông tin kết nối sau:

| Thông tin | Giá trị |
|---|---|
| Host | `localhost` |
| Port | `5432` |
| Database | `songnhat_copilot` |
| Username | `songnhat` |
| Password | `songnhat_dev` |

## 9. Kiểm tra các bảng trong cơ sở dữ liệu

Chạy lệnh sau để kiểm tra danh sách các bảng đã được tạo:

```bash
docker compose exec db psql -U songnhat -d songnhat_copilot -c "\dt"
```

**Các bảng dự kiến:**

- `products`: Lưu trữ thông tin sản phẩm.
- `categories`: Lưu trữ danh mục sản phẩm.
- `knowledge_passages`: Lưu trữ các đoạn dữ liệu kiến thức.
- `tickets`: Lưu trữ thông tin yêu cầu hỗ trợ.
- `copilot_packages`: Lưu trữ thông tin các gói Copilot.

## 10. Dừng môi trường

Để dừng các container đang chạy, sử dụng lệnh:

```bash
docker compose down
```

Lệnh này sẽ dừng và xóa các container nhưng vẫn giữ lại dữ liệu trong Docker Volume.

## 11. Khởi tạo lại cơ sở dữ liệu (Reset Database)

**CẢNH BÁO:** Thao tác này sẽ xóa toàn bộ dữ liệu cơ sở dữ liệu hiện tại trong Docker Volume. Hãy sao lưu dữ liệu quan trọng trước khi thực hiện.

Chạy lệnh:

```bash
docker compose down -v
docker compose up -d
```

Sau khi thực hiện, Docker Compose sẽ tạo lại môi trường PostgreSQL và khởi tạo cơ sở dữ liệu từ đầu theo cấu hình hiện tại.