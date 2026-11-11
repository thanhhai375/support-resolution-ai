# AI User Support System

Hệ thống hỗ trợ người dùng ứng dụng trí tuệ nhân tạo (AI), được thiết kế
nhằm hỗ trợ nhân viên tiếp nhận, quản lý, phân loại và theo dõi các yêu
cầu hỗ trợ (ticket) trên một giao diện tập trung.

> **Trạng thái dự án:** Bản thiết kế giao diện UI/Wireframe và Prototype
> trên Figma. Dữ liệu hiển thị hiện là dữ liệu minh họa; chưa đại diện
> cho hệ thống backend đang vận hành.

## 1. Giới thiệu

AI User Support System hướng đến việc cải thiện quy trình chăm sóc và hỗ
trợ người dùng thông qua: - Quản lý tập trung các yêu cầu hỗ trợ. - Theo
dõi trạng thái, mức độ ưu tiên và tiến độ xử lý ticket. - Hỗ trợ nhân
viên tra cứu thông tin và phản hồi người dùng. - Đề xuất phân loại và
hướng xử lý ticket bằng AI. - Tổng hợp số liệu để đánh giá hiệu quả hoạt
động hỗ trợ.

## 2. Mục tiêu

-   Xây dựng giao diện trực quan, dễ sử dụng.
-   Rút ngắn thời gian tiếp nhận và phân loại yêu cầu.
-   Giúp nhân viên theo dõi ticket mới, đang xử lý, đã giải quyết và quá
    hạn.
-   Cung cấp thông tin phân tích để hỗ trợ việc ra quyết định.
-   Thể hiện quy trình sử dụng hệ thống thông qua Prototype trên Figma.

## 3. Công cụ sử dụng

  -----------------------------------------------------------------------
  Công cụ                             Mục đích
  ----------------------------------- -----------------------------------
  Figma                               Thiết kế giao diện, wireframe và
                                      prototype

  Git / GitHub                        Quản lý phiên bản và chia sẻ tài
                                      liệu dự án

  AI (định hướng)                     Hỗ trợ phân loại ticket, gợi ý phản
                                      hồi và phân tích dữ liệu
  -----------------------------------------------------------------------

## 4. Các màn hình chính

Dự án gồm 5 màn hình desktop, kích thước thiết kế 1440 × 900 px:

  -----------------------------------------------------------------------
  STT                     Màn hình                Chức năng chính
  ----------------------- ----------------------- -----------------------
  01                      Login                   Đăng nhập vào hệ thống

  02                      Dashboard               Theo dõi tổng quan
                                                  ticket, số liệu thống
                                                  kê và gợi ý từ AI

  03                      Ticket List             Tìm kiếm, lọc và xem
                                                  danh sách ticket

  04                      Ticket Detail           Xem nội dung yêu cầu,
                                                  lịch sử trao đổi, thông
                                                  tin xử lý và gợi ý từ
                                                  AI

  05                      Analytics               Theo dõi hiệu suất hỗ
                                                  trợ, tỷ lệ giải quyết
                                                  và hiệu quả AI
  -----------------------------------------------------------------------

## 5. Luồng sử dụng dự kiến

``` mermaid
flowchart TD
    A[Login] --> B[Dashboard]
    B --> C[Ticket List]
    B --> E[Analytics]
    C --> D[Ticket Detail]
    D --> C
    E --> C
```

**Mô tả luồng:** 1. Người dùng đăng nhập và truy cập Dashboard. 2. Từ
Dashboard, người dùng mở danh sách ticket hoặc trang Analytics. 3. Tại
Ticket List, người dùng chọn một ticket để xem chi tiết. 4. Tại Ticket
Detail, nhân viên xem nội dung, lịch sử trao đổi và tham khảo đề xuất
của AI. 5. Người dùng quay lại danh sách để tiếp tục xử lý ticket khác.

## 6. Định hướng chức năng AI

-   **Phân loại ticket:** dự đoán nhóm vấn đề như tài khoản, thanh toán
    hoặc kỹ thuật.
-   **Đề xuất hướng xử lý:** đưa ra các bước tham khảo cho nhân viên hỗ
    trợ.
-   **Gợi ý phản hồi:** hỗ trợ soạn nội dung trả lời người dùng.
-   **Phân tích xu hướng:** nhận diện nhóm yêu cầu tăng cao và cung cấp
    thông tin tổng quan.

Các đề xuất do AI tạo ra cần được nhân viên kiểm tra và xác nhận trước
khi gửi cho người dùng hoặc áp dụng vào quy trình thực tế.

## 7. Thiết kế Figma

**Figma file:** [AI User Support System --
Wireframes](https://www.figma.com/design/TdNzic5TvynT8OociAhg76)

Để xem hoặc cùng chỉnh sửa: 1. Mở liên kết Figma. 2. Đăng nhập tài khoản
Figma. 3. Nếu cần chỉnh sửa, chủ sở hữu file cần cấp quyền **Can edit**
cho tài khoản của bạn hoặc bật quyền chỉnh sửa bằng liên kết nếu gói và
thiết lập workspace cho phép.

## 8. Phạm vi và giới hạn hiện tại

-   Đây là sản phẩm thiết kế giao diện và mô phỏng luồng tương tác.
-   Dữ liệu ticket, số liệu KPI và nội dung AI trong giao diện là dữ
    liệu mẫu.
-   Prototype mô phỏng thao tác chuyển giữa các màn hình; chưa phải ứng
    dụng web hoàn chỉnh.
-   Chưa tích hợp cơ sở dữ liệu, API, xác thực tài khoản hoặc mô hình AI
    thực tế.
-   Các thao tác như tạo ticket, gửi phản hồi và lọc dữ liệu cần được
    kết nối backend khi triển khai sản phẩm.

## 9. Hướng phát triển tiếp theo

-   Hoàn thiện Prototype cho tất cả thành phần tương tác.
-   Xây dựng frontend cho 5 màn hình.
-   Phát triển backend và API quản lý người dùng, ticket và lịch sử trao
    đổi.
-   Tích hợp cơ sở dữ liệu.
-   Tích hợp AI để phân loại ticket và đề xuất phản hồi.
-   Bổ sung phân quyền, bảo mật, ghi nhận lịch sử thao tác và kiểm thử
    hệ thống.

## 10. Đóng góp

Nếu làm việc theo nhóm: 1. Thống nhất các thay đổi trước khi chỉnh sửa
thiết kế. 2. Đặt tên Frame, Component và Layer rõ ràng. 3. Trao đổi
trước khi thay đổi cấu trúc hoặc luồng Prototype. 4. Kiểm tra lại các
màn hình và liên kết sau mỗi lần cập nhật.

## 11. Thông tin dự án

-   **Tên dự án:** AI User Support System
-   **Mô tả:** Thiết kế giao diện hệ thống hỗ trợ người dùng bằng AI
-   **Công cụ thiết kế:** Figma

------------------------------------------------------------------------

*README giới thiệu mục tiêu, phạm vi, giao diện và định hướng phát triển
của dự án.*
