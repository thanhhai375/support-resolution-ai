# ĐỀ XUẤT GIẢI PHÁP

# TỰ ĐỘNG PHÂN LOẠI TICKET BẰNG AI (AI AUTO-CATEGORIZATION)

**\[US-02\] Với vai trò nhân viên hỗ trợ, tôi muốn ticket mới được AI tự
động gán category để giảm thời gian phân loại và chuyển ticket đến đúng
nhóm xử lý.**

------------------------------------------------------------------------

## 1. User Story

**\[US-02\]** Với vai trò nhân viên hỗ trợ, tôi muốn các ticket mới được
AI tự động phân loại dựa trên nội dung yêu cầu, để giảm thao tác phân
loại thủ công và giúp ticket được xử lý bởi đúng nhóm phụ trách.

## 2. Mục tiêu

Thiết kế luồng xử lý trong đó hệ thống tiếp nhận ticket mới, phân tích
nội dung và sử dụng AI để đề xuất category phù hợp theo danh mục phân
loại đã được cấu hình.

Backend chịu trách nhiệm tiếp nhận sự kiện ticket mới, chuẩn hóa dữ
liệu, cung cấp danh mục category hợp lệ cho AI, gọi dịch vụ AI, kiểm tra
kết quả và cập nhật trạng thái phân loại. Với kết quả đủ tin cậy và hợp
lệ, hệ thống có thể tự động gán category. Với kết quả không đủ tin cậy,
không hợp lệ hoặc không thể phân loại, ticket được đưa vào hàng chờ để
nhân viên hỗ trợ xem xét thủ công.

Mục tiêu chính:

-   Giảm thời gian nhân viên phải đọc và phân loại ticket mới.
-   Tăng tính nhất quán trong việc gán category.
-   Hạn chế gán sai category và chuyển nhầm ticket đến nhóm xử lý.
-   Đảm bảo nhân viên có thể kiểm tra và sửa kết quả AI khi cần.
-   Lưu lại kết quả phân loại và quyết định của nhân viên để phục vụ
    kiểm toán, QA và cải tiến có kiểm soát.

**Phạm vi Sprint hiện tại: chỉ nghiên cứu và thiết kế flow/API. Chưa
implement, chưa gọi AI Provider thực tế và chưa tự động thay đổi dữ liệu
trên hệ thống production.**

## 3. Phạm vi MVP đề xuất

### Bao gồm

-   Tiếp nhận sự kiện khi ticket mới được tạo.
-   Kiểm tra tính hợp lệ của dữ liệu ticket trước khi phân loại.
-   Kiểm tra sự kiện trùng lặp để tránh xử lý phân loại nhiều lần ngoài
    ý muốn.
-   Lấy thông tin ticket cần thiết, ví dụ: subject, description và
    conversation history nếu có.
-   Chuẩn hóa nội dung ticket và loại bỏ dữ liệu không cần thiết trước
    khi gửi AI.
-   Sử dụng danh mục category (category taxonomy) đã được cấu hình làm
    tập lựa chọn hợp lệ.
-   Gửi nội dung ticket và danh mục category cho AI Service để dự đoán
    category.
-   Nhận kết quả dự đoán gồm category, lý do/giải thích ngắn và
    confidence score nếu AI Provider hỗ trợ.
-   Kiểm tra cấu trúc phản hồi, category có thuộc danh mục hợp lệ hay
    không và ngưỡng confidence được cấu hình.
-   Tự động gán category khi kết quả hợp lệ và đạt ngưỡng tin cậy đã
    thống nhất.
-   Chuyển ticket sang trạng thái cần nhân viên xem xét khi confidence
    thấp, category không hợp lệ hoặc AI không thể đưa ra kết quả phù
    hợp.
-   Cho phép nhân viên chấp thuận, chỉnh sửa hoặc từ chối category được
    AI đề xuất.
-   Ghi nhận category AI dự đoán, category cuối cùng, nguồn phân loại,
    thời điểm, phiên bản taxonomy/model (nếu có) và quyết định của nhân
    viên.
-   Xử lý lỗi AI/API bằng cơ chế retry có giới hạn; nếu không khôi phục
    được thì chuyển sang quy trình phân loại thủ công.
-   Thiết kế cơ chế cập nhật lại phân loại khi nội dung ticket thay đổi
    đáng kể (phần này cần thống nhất quy tắc trigger).

### Không bao gồm trong MVP

-   AI tự tạo category mới hoặc tự thay đổi danh mục category đã được
    quản trị cấu hình.
-   AI tự động phân công ticket cho một nhân viên cụ thể.
-   AI tự động thực hiện hành động nghiệp vụ như hoàn tiền, cập nhật đơn
    hàng hoặc thay đổi thông tin khách hàng.
-   Tự động huấn luyện/cập nhật mô hình từ phản hồi thô của nhân viên.
-   Tự động thay đổi taxonomy, quy tắc phân loại hoặc ngưỡng confidence
    mà không qua phê duyệt.
-   Triển khai code, kết nối AI Provider hoặc triển khai lên môi trường
    production trong Sprint thiết kế này.

**Lưu ý:** Tự động gán category không đồng nghĩa với tự động
routing/assignment. Việc chuyển ticket đến team hoặc agent phụ trách có
thể sử dụng category làm đầu vào, nhưng nên được xem là bước riêng hoặc
phạm vi mở rộng nếu Jira chưa yêu cầu.

## 4. Quy trình đề xuất

1.  **Tiếp nhận ticket mới:** Khi khách hàng tạo ticket, hệ thống ticket
    phát sinh sự kiện `TicketCreated` hoặc webhook tương đương. Backend
    nhận sự kiện để bắt đầu quy trình phân loại.

2.  **Kiểm tra dữ liệu đầu vào:** Kiểm tra ticket ID, subject,
    description và các trường bắt buộc. Nếu dữ liệu không hợp lệ hoặc
    thiếu nội dung tối thiểu, không gọi AI; ghi nhận lỗi và đưa ticket
    vào hàng chờ xử lý thủ công hoặc yêu cầu bổ sung thông tin.

3.  **Kiểm tra sự kiện trùng lặp:** Kiểm tra event ID/ticket ID và trạng
    thái phân loại hiện tại. Nếu sự kiện đã được xử lý, không tạo thêm
    một lần phân loại ngoài ý muốn. Cơ chế này giúp xử lý webhook theo
    hướng idempotent.

4.  **Lưu trạng thái ban đầu:** Ghi nhận trạng thái phân loại là
    `PENDING` hoặc trạng thái tương đương để có thể theo dõi tiến trình
    và tránh ticket bị bỏ sót.

5.  **Lấy ngữ cảnh ticket:** Lấy subject, description, các trường liên
    quan và lịch sử hội thoại nếu cần thiết. Chỉ lấy dữ liệu cần cho
    việc phân loại và được phép truy cập.

6.  **Chuẩn hóa dữ liệu:** Chuẩn hóa văn bản, xử lý nội dung rỗng/quá
    dài, loại bỏ thông tin không cần thiết và hạn chế dữ liệu cá nhân
    trước khi gửi sang AI. Nội dung do khách hàng cung cấp phải được xem
    là dữ liệu đầu vào không đáng tin cậy.

7.  **Lấy danh mục category:** Lấy danh sách category hợp lệ, mô tả và
    quy tắc phân loại đã được quản trị cấu hình. Ví dụ: `ACCOUNT`,
    `PAYMENT`, `REFUND`, `ORDER`, `TECHNICAL`, `OTHER`. Danh sách thực
    tế phải được thống nhất với nghiệp vụ; đây chỉ là ví dụ minh họa.

8.  **Gửi yêu cầu phân loại cho AI:** Backend gửi ticket context cùng
    danh mục category hợp lệ và yêu cầu AI chọn category phù hợp nhất.
    Có thể yêu cầu AI trả về lý do ngắn, thông tin còn thiếu và
    confidence nếu giải pháp AI hỗ trợ.

9.  **Xử lý lỗi dịch vụ AI:** Nếu AI Service timeout, không khả dụng
    hoặc trả lỗi kỹ thuật, thực hiện retry có giới hạn với backoff. Nếu
    vẫn thất bại, đánh dấu phân loại tạm thời không khả dụng và đưa
    ticket vào quy trình phân loại thủ công. Không xem lỗi kỹ thuật là
    kết quả phân loại.

10. **Kiểm tra cấu trúc kết quả:** Kiểm tra response có đúng schema, có
    ticket ID tương ứng và có trường category hay không. Nếu response
    thiếu trường, sai định dạng hoặc không thể đọc, không sử dụng kết
    quả; ghi nhận lỗi và chuyển xử lý thủ công sau số lần thử được cấu
    hình.

11. **Kiểm tra category hợp lệ:** Đối chiếu category AI trả về với
    taxonomy hiện hành. Nếu category không tồn tại hoặc AI tự tạo nhãn
    ngoài danh sách cho phép, từ chối kết quả và chuyển Agent Review;
    không tự động thêm category mới.

12. **Đánh giá độ tin cậy:** So sánh confidence score (nếu có) với
    ngưỡng đã được nhóm thống nhất và kiểm chứng. Ngưỡng chỉ là tham số
    cấu hình, không nên mặc định một giá trị trước khi đánh giá trên dữ
    liệu thực tế. Nếu AI không cung cấp confidence đáng tin cậy, cần
    thiết kế tiêu chí fallback khác thay vì giả định điểm số.

13. **Tự động gán category:** Nếu response hợp lệ, category nằm trong
    taxonomy và kết quả đạt điều kiện tin cậy, Backend cập nhật category
    cho ticket. Ghi nhận nguồn phân loại là `AI` và trạng thái tương
    ứng, ví dụ `AUTO_CATEGORIZED`.

14. **Chuyển Agent Review:** Nếu confidence thấp, ticket mơ hồ/nhiều chủ
    đề, thiếu thông tin, category không hợp lệ hoặc AI không thể phân
    loại, lưu category đề xuất (nếu có) và đánh dấu `NEEDS_REVIEW`. Hiển
    thị đề xuất cùng lý do để Agent xem xét.

15. **Nhân viên xem xét:** Agent có thể chấp thuận category đề xuất,
    chọn category khác, hoặc từ chối đề xuất và tự phân loại. Nếu cần
    thêm thông tin từ khách hàng, Agent xử lý theo quy trình hỗ trợ hiện
    hành.

16. **Lưu kết quả cuối cùng:** Lưu category cuối cùng, category AI dự
    đoán, nguồn phân loại (`AI` hoặc `AGENT`), quyết định của Agent, lý
    do chỉnh sửa/từ chối và thời điểm cập nhật.

17. **Cập nhật Ticket Lifecycle:** Cập nhật trạng thái phân loại và
    trạng thái ticket phù hợp. Nếu hệ thống có quy tắc routing theo
    category, chỉ kích hoạt routing sau khi category đã được xác nhận và
    trong phạm vi được phê duyệt.

18. **Ghi nhật ký và QA:** Ghi lại event ID, ticket ID, kết quả AI,
    taxonomy/model version (nếu có), thời gian xử lý, lỗi, retry và
    quyết định của Agent. Dữ liệu phản hồi chỉ được sử dụng để đánh giá
    và cải tiến sau quy trình QA/quản trị.

19. **Xử lý ticket được cập nhật:** Nếu subject, description hoặc nội
    dung hội thoại thay đổi đáng kể sau khi phân loại, áp dụng quy tắc
    đã thống nhất để đánh dấu kết quả cũ cần đánh giá lại hoặc tạo yêu
    cầu phân loại mới. Không phân loại lại vô hạn chỉ vì các trường
    không liên quan thay đổi.

## 5. Sơ đồ luồng xử lý

Sơ đồ dưới đây mô tả luồng đề xuất cho MVP. Có thể lưu hình Mermaid được
xuất từ công cụ hỗ trợ Mermaid vào thư mục `images/` của tài liệu khi
nhóm tạo bản tài liệu hoàn chỉnh.

### Sơ đồ Mermaid

``` mermaid
flowchart TD
    A([Ticket mới được tạo]) --> B[Ticket Created Event / Webhook]
    B --> C[Backend tiếp nhận sự kiện]
    C --> D{Dữ liệu ticket hợp lệ?}

    D -- Không --> E[Đánh dấu dữ liệu không hợp lệ]
    E --> F[Đưa vào xử lý thủ công]

    D -- Có --> G[Kiểm tra event trùng lặp / idempotency]
    G --> H{Ticket đã được phân loại?}
    H -- Có --> I[Trả về kết quả hiện có / bỏ qua event trùng]
    H -- Không --> J[Lưu trạng thái PENDING]

    J --> K[Lấy thông tin ticket và hội thoại cần thiết]
    K --> L[Chuẩn hóa ticket context]
    L --> M[Lấy Category Taxonomy và quy tắc phân loại]
    M --> N[Gửi yêu cầu phân loại đến AI Service]

    N --> O{AI Service có lỗi kỹ thuật?}
    O -- Có --> P[Retry có giới hạn và backoff]
    P --> Q{AI Service đã khôi phục?}
    Q -- Không --> R[Đánh dấu AI tạm thời không khả dụng]
    R --> F
    Q -- Có --> N

    O -- Không --> S[Nhận kết quả dự đoán category]
    S --> T{Response đúng schema?}
    T -- Không --> U[Ghi nhận response không hợp lệ]
    U --> F

    T -- Có --> V{Category thuộc taxonomy?}
    V -- Không --> W[Từ chối category ngoài danh mục]
    W --> F

    V -- Có --> X{Đạt điều kiện tin cậy?}
    X -- Có --> Y[Tự động gán category]
    X -- Không --> Z[Lưu đề xuất và đánh dấu NEEDS_REVIEW]

    Z --> AA[Hiển thị đề xuất cho Agent]
    AA --> AB{Agent quyết định}
    AB -- Chấp thuận --> AC[Chấp nhận category AI]
    AB -- Chỉnh sửa --> AD[Chọn category phù hợp]
    AB -- Từ chối --> AE[Ghi nhận lý do và phân loại thủ công]

    AC --> AF[Lưu category cuối cùng]
    AD --> AF
    AE --> AF
    Y --> AG[Cập nhật Ticket Category và Classification Status]
    AF --> AG

    AG --> AH[Ghi Audit Log và kết quả phân loại]
    AH --> AI[Cập nhật Ticket Lifecycle]
    AI --> AJ([Ticket đã được phân loại])

    F --> AK([Ticket chờ nhân viên phân loại])
```

## 6. Các quyết định thiết kế và kiểm soát quan trọng

-   **Taxonomy là nguồn category chuẩn:** AI chỉ được chọn trong danh
    sách category đã cấu hình. Mỗi category nên có mã định danh, tên, mô
    tả, ví dụ và quy tắc phân biệt với category gần nghĩa.

-   **Phân biệt phân loại với routing:** Auto-categorization chỉ xác
    định loại vấn đề. Việc gán team/agent, mức độ ưu tiên hoặc chuyển
    ticket là bước nghiệp vụ riêng, không tự động suy ra nếu chưa có quy
    tắc được phê duyệt.

-   **Tách lỗi kỹ thuật khỏi kết quả nghiệp vụ:** Timeout, lỗi mạng, AI
    Provider không khả dụng hoặc response sai schema là lỗi kỹ thuật.
    Chúng không được diễn giải thành category `OTHER` hoặc một category
    bất kỳ.

-   **Ngưỡng confidence phải được kiểm chứng:** Ngưỡng quyết định tự
    động gán category cần được đánh giá bằng tập dữ liệu ticket đã gán
    nhãn. Cần xem xét precision theo từng category và chi phí của việc
    gán sai, đặc biệt với các category có rủi ro cao.

-   **Fallback khi không chắc chắn:** Nếu nội dung mơ hồ, có nhiều ý
    định hoặc không đủ dữ liệu, ưu tiên chuyển Agent Review thay vì ép
    AI chọn một category không phù hợp.

-   **Không cho AI tự tạo category:** Category ngoài taxonomy phải bị từ
    chối hoặc đưa vào hàng chờ xem xét. Việc thêm/sửa taxonomy cần do
    người có thẩm quyền quản trị.

-   **Idempotency và xử lý event trùng:** Webhook có thể được gửi lại.
    Backend cần dùng event ID hoặc cơ chế khóa/idempotency key để tránh
    phân loại lặp và ghi đè kết quả mới bằng kết quả cũ.

-   **Retry có giới hạn:** Chỉ retry lỗi kỹ thuật có khả năng phục hồi,
    sử dụng backoff và giới hạn số lần thử. Không retry vô hạn và không
    retry lỗi dữ liệu đầu vào không hợp lệ.

-   **Kiểm soát dữ liệu và quyền truy cập:** Chỉ gửi dữ liệu cần thiết
    cho AI. Hạn chế thông tin cá nhân; tuân thủ quyền truy cập, chính
    sách lưu trữ và quy định của AI Provider.

-   **Bảo vệ trước chỉ dẫn không đáng tin cậy:** Nội dung ticket/hội
    thoại là dữ liệu cần phân loại, không phải chỉ dẫn có quyền thay đổi
    prompt hệ thống, taxonomy hoặc quy tắc nghiệp vụ.

-   **Lưu cả dự đoán và kết quả cuối:** Cần phân biệt
    `predicted_category` với `final_category` để đo lường độ chính xác
    và nhận diện trường hợp Agent sửa kết quả AI.

-   **Quản lý phiên bản:** Ghi nhận phiên bản taxonomy, prompt và
    model/provider (nếu có) để có thể giải thích hoặc đối chiếu kết quả
    phân loại tại từng thời điểm.

-   **Phân loại lại khi ticket thay đổi:** Cần định nghĩa trường nào
    được xem là thay đổi có ý nghĩa. Nếu ticket đã được Agent xử lý hoặc
    xác nhận category, không tự ý ghi đè kết quả đó khi có cập nhật
    không liên quan.

-   **Sprint hiện tại chỉ thiết kế:** Các endpoint, schema, trạng thái
    và quy tắc trong tài liệu là đề xuất cần được team thống nhất; chưa
    đại diện cho API hoặc hành vi đã được implement.

## 7. Các trạng thái phân loại đề xuất

Có thể sử dụng các trạng thái riêng cho tiến trình phân loại để không
nhầm lẫn với trạng thái nghiệp vụ của ticket (`OPEN`, `IN_PROGRESS`,
`RESOLVED`, ...).

  -----------------------------------------------------------------------
  Classification Status               Ý nghĩa
  ----------------------------------- -----------------------------------
  `PENDING`                           Ticket đang chờ xử lý phân loại

  `PROCESSING`                        Backend đang thực hiện phân loại

  `AUTO_CATEGORIZED`                  AI đã gán category tự động theo
                                      điều kiện được duyệt

  `NEEDS_REVIEW`                      Kết quả cần Agent xem xét

  `MANUALLY_CLASSIFIED`               Category được Agent xác định hoặc
                                      chỉnh sửa

  `FAILED`                            Quy trình phân loại thất bại; cần
                                      xử lý theo chính sách fallback
  -----------------------------------------------------------------------

Các trạng thái trên là đề xuất. Nhóm cần thống nhất cách chuyển trạng
thái và cách xử lý khi retry thành công sau một lần thất bại.

## 8. API và dữ liệu đề xuất cho giai đoạn thiết kế

Các endpoint dưới đây là API Contract tham khảo để Backend, Frontend và
AI team thống nhất. Không khẳng định đây là endpoint hiện có của hệ
thống.

### 8.1. Tiếp nhận sự kiện ticket mới

**Endpoint đề xuất:** `POST /api/v1/tickets/events`

Mục đích: Nhận webhook/event khi ticket được tạo.

Request minh họa:

``` json
{
  "event_id": "evt-001",
  "event_type": "TICKET_CREATED",
  "ticket_id": "TK-001",
  "occurred_at": "2026-11-03T09:00:00Z"
}
```

Response minh họa:

``` json
{
  "event_id": "evt-001",
  "ticket_id": "TK-001",
  "status": "ACCEPTED"
}
```

Nếu xử lý bất đồng bộ, phản hồi `ACCEPTED` chỉ xác nhận Backend đã tiếp
nhận event, không có nghĩa ticket đã được phân loại xong.

### 8.2. Yêu cầu phân loại ticket

**Endpoint nội bộ đề xuất:** `POST /api/v1/tickets/{ticket_id}/classify`

Request minh họa gửi đến AI Service:

``` json
{
  "ticket": {
    "ticket_id": "TK-001",
    "subject": "Cannot login",
    "description": "I cannot access my account after resetting my password."
  },
  "allowed_categories": [
    {
      "code": "ACCOUNT",
      "description": "Login, password, account access"
    },
    {
      "code": "PAYMENT",
      "description": "Payment and billing issues"
    },
    {
      "code": "REFUND",
      "description": "Refund requests"
    },
    {
      "code": "ORDER",
      "description": "Order status and delivery"
    },
    {
      "code": "TECHNICAL",
      "description": "Technical errors and product bugs"
    },
    {
      "code": "OTHER",
      "description": "Issues not covered by other categories"
    }
  ],
  "response_format": {
    "category": "one_allowed_category",
    "reason": "short_explanation",
    "confidence": "optional_score"
  }
}
```

Response minh họa:

``` json
{
  "ticket_id": "TK-001",
  "predicted_category": "ACCOUNT",
  "reason": "The customer cannot access their account.",
  "confidence": 0.94
}
```

### 8.3. Cập nhật category

**Endpoint đề xuất:** `PATCH /api/v1/tickets/{ticket_id}/category`

Request minh họa:

``` json
{
  "category": "ACCOUNT",
  "classification_source": "AI",
  "classification_status": "AUTO_CATEGORIZED"
}
```

Khi Agent chỉnh sửa:

``` json
{
  "category": "TECHNICAL",
  "classification_source": "AGENT",
  "classification_status": "MANUALLY_CLASSIFIED",
  "reason": "The issue is caused by a login system error."
}
```

### 8.4. Xem kết quả phân loại

**Endpoint đề xuất:** `GET /api/v1/tickets/{ticket_id}/classification`

Response minh họa:

``` json
{
  "ticket_id": "TK-001",
  "predicted_category": "ACCOUNT",
  "final_category": "ACCOUNT",
  "classification_status": "AUTO_CATEGORIZED",
  "classification_source": "AI",
  "reason": "The customer cannot access their account.",
  "taxonomy_version": "v1"
}
```

## 9. Tiêu chí nghiệm thu đề xuất

-   Khi ticket mới được tạo, hệ thống có cơ chế tiếp nhận sự kiện để bắt
    đầu quy trình phân loại.
-   Backend kiểm tra dữ liệu đầu vào và xử lý event trùng lặp theo cơ
    chế idempotency.
-   Dữ liệu gửi cho AI chỉ bao gồm các trường cần thiết và được phép sử
    dụng.
-   AI nhận được danh mục category hợp lệ và chỉ được yêu cầu lựa chọn
    trong danh mục đó.
-   Kết quả AI phải được kiểm tra schema và tính hợp lệ của category
    trước khi sử dụng.
-   Ticket chỉ được tự động gán category khi kết quả đáp ứng điều kiện
    tin cậy đã thống nhất.
-   Kết quả confidence thấp hoặc ticket mơ hồ phải được đưa vào Agent
    Review.
-   AI không được tự tạo category mới hoặc tự thay đổi taxonomy.
-   Nếu AI Service gặp lỗi kỹ thuật, hệ thống retry có giới hạn; nếu vẫn
    thất bại, ticket được chuyển sang quy trình phân loại thủ công.
-   Agent có thể chấp thuận hoặc chỉnh sửa category đề xuất; hệ thống
    lưu category AI dự đoán và category cuối cùng riêng biệt.
-   Hệ thống ghi nhận nguồn phân loại, thời điểm, trạng thái, lý do và
    quyết định của Agent.
-   Việc cập nhật ticket không được làm mất category đã được Agent xác
    nhận nếu không có quy tắc phân loại lại được phê duyệt.
-   Quyền truy cập và dữ liệu cá nhân được kiểm soát trong toàn bộ
    luồng.
-   Tài liệu flowchart, API Contract, trạng thái và các nhánh lỗi được
    team liên quan xem xét và thống nhất.

**Đối với Sprint thiết kế hiện tại:** tiêu chí hoàn thành là tài liệu
flow/API được thống nhất và review; không yêu cầu chứng minh AI đã phân
loại ticket thực tế.

## 10. Chỉ số đánh giá thành công

Các chỉ số dưới đây dùng cho giai đoạn đánh giá sau khi triển khai,
không phải kết quả đã có trong Sprint thiết kế.

-   **Auto-categorization rate:** Tỷ lệ ticket được AI tự động gán
    category mà không cần Agent can thiệp.
-   **Category accuracy:** Tỷ lệ category AI dự đoán trùng với category
    chuẩn do người có thẩm quyền xác nhận.
-   **Precision theo category:** Mức độ chính xác của từng category,
    giúp phát hiện category nào thường bị gán nhầm.
-   **Manual review rate:** Tỷ lệ ticket phải chuyển Agent Review.
-   **Agent correction rate:** Tỷ lệ kết quả AI bị Agent chỉnh sửa hoặc
    từ chối.
-   **Fallback rate:** Tỷ lệ ticket phải phân loại thủ công do lỗi
    AI/API hoặc dữ liệu không đủ.
-   **Classification latency:** Thời gian từ lúc nhận event đến khi có
    kết quả phân loại.
-   **Duplicate processing rate:** Tỷ lệ event trùng gây xử lý lặp; mục
    tiêu là hạn chế tối đa việc ghi nhận trùng.
-   **Routing accuracy (nếu triển khai routing):** Tỷ lệ ticket được
    chuyển đúng nhóm dựa trên category đã xác nhận.

Không nên chỉ tối ưu tỷ lệ tự động phân loại. Cần cân bằng giữa độ chính
xác, tỷ lệ chuyển Agent Review và chi phí của việc gán sai category.

## 11. Phần mở rộng trong giai đoạn sau

Sau khi chức năng auto-categorization hoạt động ổn định, có thể xem xét:

-   **Auto-routing:** Dựa trên category đã xác nhận để chuyển ticket đến
    team/queue phù hợp.
-   **Multi-label classification:** Cho phép một ticket có nhiều
    category nếu nghiệp vụ thực sự cần.
-   **Priority prediction:** AI đề xuất mức độ ưu tiên riêng biệt với
    category.
-   **SLA risk detection:** Phát hiện ticket có nguy cơ vi phạm SLA.
-   **Category suggestion for existing tickets:** Phân loại lại ticket
    cũ theo yêu cầu được kiểm soát.
-   **Taxonomy management:** Giao diện quản trị danh mục, mô tả, ví dụ
    và quy tắc phân loại.
-   **Model evaluation:** Đánh giá mô hình bằng bộ dữ liệu đã gán nhãn,
    theo dõi precision/recall/F1 theo từng category.
-   **Human feedback loop:** Thu thập các trường hợp Agent chỉnh sửa để
    tạo dữ liệu đánh giá; chỉ cập nhật prompt, taxonomy hoặc model sau
    QA và phê duyệt.
-   **Confidence calibration:** Hiệu chuẩn confidence và thiết lập
    ngưỡng riêng cho từng category nếu dữ liệu đánh giá cho thấy cần
    thiết.

Các phần mở rộng cần có phạm vi, quyền hạn và cơ chế kiểm soát riêng;
không mặc định nằm trong MVP.

## 12. Tóm tắt

Giải pháp đề xuất đưa AI vào quy trình phân loại ticket mới: Backend
tiếp nhận sự kiện, lấy và chuẩn hóa nội dung ticket, cung cấp danh mục
category hợp lệ, gọi AI để dự đoán category, sau đó kiểm tra cấu trúc,
tính hợp lệ và điều kiện tin cậy của kết quả.

Nếu kết quả đáp ứng điều kiện đã thống nhất, hệ thống có thể tự động gán
category. Nếu kết quả không chắc chắn, không hợp lệ hoặc AI Service gặp
lỗi không thể khôi phục, ticket được chuyển sang quy trình nhân viên
phân loại thủ công. Hệ thống lưu cả category AI dự đoán và category cuối
cùng, đồng thời ghi nhật ký phục vụ QA và kiểm toán.

Thiết kế này hướng đến giảm thao tác phân loại thủ công, tăng tính nhất
quán và hỗ trợ xử lý ticket hiệu quả hơn, đồng thời duy trì quyền kiểm
soát của nhân viên, bảo mật dữ liệu và khả năng truy vết.

**Phạm vi hiện tại chỉ dừng ở nghiên cứu và thiết kế flow/API. Việc
implement, tích hợp AI Provider, kiểm thử trên dữ liệu thực tế và triển
khai tự động phân loại sẽ được thực hiện ở Sprint phù hợp sau khi thiết
kế được phê duyệt.**
