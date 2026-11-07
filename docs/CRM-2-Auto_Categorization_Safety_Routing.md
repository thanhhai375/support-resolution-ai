# ĐỀ XUẤT GIẢI PHÁP

# TỰ ĐỘNG PHÂN LOẠI TICKET VÀ QUÉT AN TOÀN KHẨN CẤP (AI AUTO-CATEGORIZATION & MANDATORY SAFETY ROUTING)

**\[US-02\] Là nhân viên hỗ trợ, tôi muốn ticket được tự động phân loại
theo 3 danh mục SongNhat và quét an toàn khẩn cấp.**

------------------------------------------------------------------------

## 1. User Story

**\[US-02\]** Với vai trò nhân viên hỗ trợ, tôi muốn ticket mới được hệ
thống tự động phân loại vào một trong ba danh mục SongNhat, đồng thời
nội dung ticket được quét các dấu hiệu nguy hiểm để kích hoạt quy trình
chuyển cấp an toàn khẩn cấp khi cần thiết.

Mục tiêu là giảm thao tác phân loại thủ công, giúp ticket đi đúng luồng
xử lý và đảm bảo các tình huống có nguy cơ mất an toàn được ưu tiên xử
lý ngay lập tức.

## 2. Mục tiêu

Thiết kế luồng xử lý ticket mới gồm hai nhiệm vụ chính:

1.  **Tự động phân loại ticket:** phân tích nội dung yêu cầu và gán một
    trong ba category đã xác định.
2.  **Quét an toàn bắt buộc (Mandatory Safety Routing):** phát hiện từ
    khóa hoặc dấu hiệu nguy hiểm và chuyển ticket khẩn cấp đến kỹ sư phụ
    trách an toàn.

Các mục tiêu cụ thể:

-   Tự động phân loại ticket theo đúng ba danh mục SongNhat.
-   Giảm thời gian nhân viên hỗ trợ phải đọc và phân loại ticket bằng
    tay.
-   Phát hiện sớm nội dung có dấu hiệu khói, lửa/cháy, điện giật, nổ
    hoặc chuyển động bất thường.
-   Đảm bảo quy trình an toàn được ưu tiên hơn quy trình AI đề xuất sửa
    chữa thông thường.
-   Không để AI tiếp tục đề xuất hướng dẫn sửa chữa khi ticket đã được
    xác định có nguy cơ an toàn.
-   Ghi nhận trạng thái, kết quả phân loại và lịch sử chuyển cấp để phục
    vụ theo dõi, kiểm toán và QA.

## 3. Phạm vi chức năng

### 3.1. Ba danh mục khởi tạo (Initial Categories - RFP Section 1)

Hệ thống phân loại ticket vào một trong ba danh mục sau:

  ------------------------------------------------------------------------
  Mã danh mục              Mô tả                   Ví dụ nội dung ticket
  ------------------------ ----------------------- -----------------------
  `DOCUMENT_REQUEST`       Yêu cầu tài liệu kỹ     Khách hàng yêu cầu
                           thuật, manual, sơ đồ    manual, tài liệu kỹ
                           chân đấu nối biến       thuật hoặc sơ đồ đấu
                           tần/động cơ SongNhat.   nối.

  `SERVICE_PROGRESS`       Tra cứu tiến độ dịch vụ Khách hàng hỏi tình
                           sửa chữa, bảo dưỡng     trạng sửa chữa, lịch
                           hoặc giao nhận linh     bảo dưỡng hoặc tiến độ
                           kiện.                   giao linh kiện.

  `TECHNICAL_ESCALATION`   Thu thập dữ kiện sự cố  Ticket mô tả lỗi kỹ
                           kỹ thuật phức tạp để    thuật phức tạp cần kỹ
                           chuyển kỹ sư chuyên     sư chuyên trách đánh
                           trách.                  giá.
  ------------------------------------------------------------------------

AI chỉ được lựa chọn một trong ba danh mục đã cấu hình. Không tự tạo
category mới hoặc tự thay đổi danh mục.

### 3.2. Quét an toàn bắt buộc (Mandatory Safety Routing - SUP-04)

Hệ thống phải quét nội dung ticket để phát hiện các dấu hiệu nguy cơ
sau:

  Nhóm nguy cơ             Từ khóa nhận diện
  ------------------------ ---------------------------------------------
  Khói                     `smoke`, khói
  Lửa/Cháy                 `fire`, lửa, cháy
  Điện giật                `electric shock`, điện giật
  Nổ                       `explosion`, nổ
  Chuyển động bất thường   `unexpected motion`, chuyển động bất thường

**Hành vi bắt buộc khi phát hiện nguy cơ:**

-   Ngay lập tức ngắt luồng AI đề xuất sửa chữa.
-   Kích hoạt cờ `is_hazard_escalated = TRUE`.
-   Chuyển ticket khẩn cấp cho Kỹ sư phụ trách an toàn.
-   Không tiếp tục luồng đề xuất sửa chữa thông thường trong khi ticket
    đang được xử lý theo nhánh an toàn.

### 3.3. Ngoài phạm vi được mô tả

Các nội dung sau chưa được xác định trong yêu cầu US-02, do đó cần được
thống nhất thêm trước khi triển khai:

-   Tự động tạo category mới ngoài ba danh mục SongNhat.
-   Tự động phân công cho một cá nhân cụ thể ngoài quy tắc chuyển đến Kỹ
    sư phụ trách an toàn.
-   Tự động đưa ra hướng dẫn sửa chữa cho ticket đã kích hoạt cờ nguy
    hiểm.
-   Tự động chẩn đoán hoặc xác nhận nguyên nhân kỹ thuật chỉ dựa trên từ
    khóa.
-   Các cơ chế confidence score, ngưỡng tin cậy hoặc retry AI chi tiết
    nếu chưa có đặc tả bổ sung.

## 4. Quy trình xử lý đề xuất

1.  **Tiếp nhận ticket mới:** hệ thống nhận ticket mới từ khách hàng
    hoặc từ hệ thống ticket hiện có.

2.  **Kiểm tra dữ liệu đầu vào:** kiểm tra các thông tin cần thiết như
    ticket ID, subject và description. Ticket thiếu dữ liệu được ghi
    nhận để nhân viên hỗ trợ kiểm tra/bổ sung.

3.  **Chuẩn hóa nội dung ticket:** tổng hợp nội dung cần phân tích, bao
    gồm tiêu đề và mô tả ticket. Nội dung được chuẩn hóa để phục vụ việc
    quét an toàn và phân loại.

4.  **Quét an toàn bắt buộc:** kiểm tra nội dung ticket với các nhóm từ
    khóa nguy cơ: khói, lửa/cháy, điện giật, nổ và chuyển động bất
    thường.

5.  **Kiểm tra có dấu hiệu nguy hiểm không:**

    -   Nếu **Có**, dừng luồng AI đề xuất sửa chữa, đặt
        `is_hazard_escalated = TRUE` và chuyển khẩn cấp đến Kỹ sư phụ
        trách an toàn.
    -   Nếu **Không**, tiếp tục quy trình phân loại ticket thông thường.

6.  **Phân tích nội dung bằng AI:** AI đọc nội dung ticket và xác định
    mục đích chính của yêu cầu.

7.  **Phân loại theo ba danh mục SongNhat:** AI lựa chọn một trong các
    category `DOCUMENT_REQUEST`, `SERVICE_PROGRESS` hoặc
    `TECHNICAL_ESCALATION`.

8.  **Kiểm tra category:** hệ thống xác nhận kết quả AI trả về thuộc một
    trong ba danh mục hợp lệ. Nếu kết quả không hợp lệ hoặc không rõ
    ràng, ticket được chuyển nhân viên hỗ trợ xem xét thủ công.

9.  **Lưu kết quả phân loại:** lưu category được xác định cùng trạng
    thái xử lý của ticket.

10. **Cập nhật ticket và chuyển luồng xử lý:** ticket được cập nhật
    category để phục vụ quy trình hỗ trợ tiếp theo. Việc phân công nhóm
    xử lý chi tiết cần tuân theo quy tắc nghiệp vụ được cấu hình.

11. **Ghi nhật ký:** lưu lại kết quả quét an toàn, category, thời điểm
    xử lý và thông tin chuyển cấp nếu có.

## 5. Sơ đồ luồng xử lý

Sơ đồ dưới đây mô tả luồng chính của US-02. Nhánh quét an toàn được đặt
trước nhánh phân loại thông thường để đảm bảo mọi ticket mới đều được
kiểm tra nguy cơ trước khi AI đưa ra đề xuất xử lý.

### Sơ đồ Mermaid

``` mermaid
flowchart TD
    A([Incoming Support Ticket]) --> B[Receive New Ticket]
    B --> C[Validate Ticket Data]
    C --> D{Ticket Data Valid?}

    D -- No --> E[Mark Ticket for Agent Review]
    E --> F[Request Missing Information / Manual Handling]

    D -- Yes --> G[Preprocess Ticket Content]
    G --> H[Mandatory Safety Scan]
    H --> I[Scan Keywords: Smoke, Fire, Electric Shock, Explosion, Unexpected Motion]
    I --> J{Hazard Detected?}

    J -- Yes --> K[Stop AI Repair Suggestion Flow]
    K --> L[Set is_hazard_escalated = TRUE]
    L --> M[Urgent Handoff to Safety Engineer]
    M --> N[Safety Engineer Review]
    N --> O[Update Hazard Ticket Status]
    O --> P[Record Safety Audit Log]

    J -- No --> Q[AI Analyzes Ticket Intent]
    Q --> R[Classify into SongNhat Categories]
    R --> S{Category Result Valid?}

    S -- No --> T[Mark as Needs Manual Classification]
    T --> U[Agent Reviews and Selects Category]

    S -- Yes --> V{Selected Category}
    V --> W[DOCUMENT_REQUEST]
    V --> X[SERVICE_PROGRESS]
    V --> Y[TECHNICAL_ESCALATION]

    W --> Z[Save Ticket Category]
    X --> Z
    Y --> Z
    U --> Z

    Z --> AA[Update Ticket Lifecycle]
    AA --> AB[Route to Relevant Support Process]
    AB --> AC[Record Classification Audit Log]
    AC --> AD([Ticket Categorization Completed])

    P --> AE([Emergency Safety Routing Completed])
```

## 6. Các quyết định thiết kế và kiểm soát quan trọng

-   **Safety Scan phải được ưu tiên:** mọi ticket mới phải đi qua bước
    quét an toàn trước khi tiếp tục luồng AI phân loại/đề xuất xử lý
    thông thường.

-   **Dừng AI đề xuất sửa chữa khi có nguy cơ:** khi phát hiện dấu hiệu
    nguy hiểm, hệ thống phải ngắt luồng AI đề xuất sửa chữa. Không được
    để nhánh phân loại thông thường làm chậm việc chuyển cấp an toàn.

-   **Cờ nguy hiểm phải được ghi nhận rõ ràng:** khi phát hiện nguy cơ,
    cập nhật `is_hazard_escalated = TRUE` để các thành phần khác của hệ
    thống nhận biết ticket đang ở nhánh xử lý khẩn cấp.

-   **Chuyển cấp đúng người phụ trách:** ticket có nguy cơ phải được
    chuyển khẩn cấp đến Kỹ sư phụ trách an toàn, không chỉ đưa vào hàng
    chờ hỗ trợ thông thường.

-   **Taxonomy chỉ gồm ba danh mục đã thống nhất:** AI chỉ được phân
    loại vào `DOCUMENT_REQUEST`, `SERVICE_PROGRESS` hoặc
    `TECHNICAL_ESCALATION`.

-   **Không nhầm lẫn category với assignment:** category xác định loại
    yêu cầu; việc chuyển ticket đến nhóm hoặc cá nhân phụ trách là bước
    xử lý tiếp theo theo quy tắc nghiệp vụ.

-   **Xử lý kết quả không hợp lệ:** nếu AI trả về category nằm ngoài ba
    danh mục hoặc không xác định được category phù hợp, cần chuyển nhân
    viên hỗ trợ xem xét thay vì tự tạo danh mục mới.

-   **Ghi nhận lịch sử:** cần lưu category đã gán, kết quả quét nguy cơ,
    cờ `is_hazard_escalated`, thời điểm xử lý và thông tin chuyển cấp để
    phục vụ kiểm tra.

-   **Từ khóa là tín hiệu phát hiện:** việc phát hiện từ khóa là điều
    kiện kích hoạt luồng kiểm tra/chuyển cấp theo yêu cầu; không nên xem
    riêng từ khóa là kết luận kỹ thuật về nguyên nhân sự cố.

## 7. Trạng thái xử lý đề xuất

Các trạng thái dưới đây là gợi ý để nhóm thống nhất khi thiết kế hệ
thống. Chúng không khẳng định là các trạng thái đã tồn tại trong ứng
dụng.

  -----------------------------------------------------------------------
  Trạng thái                          Ý nghĩa
  ----------------------------------- -----------------------------------
  `NEW`                               Ticket mới được tiếp nhận.

  `SAFETY_SCANNING`                   Ticket đang được quét các dấu hiệu
                                      nguy hiểm.

  `HAZARD_ESCALATED`                  Đã phát hiện nguy cơ, cờ
                                      `is_hazard_escalated = TRUE` và
                                      ticket được chuyển cấp an toàn.

  `SAFETY_REVIEW`                     Ticket đang chờ Kỹ sư phụ trách an
                                      toàn xem xét.

  `CLASSIFYING`                       Ticket đang được AI phân loại sau
                                      khi không phát hiện nguy cơ.

  `AUTO_CATEGORIZED`                  Ticket đã được gán một trong ba
                                      category hợp lệ.

  `NEEDS_REVIEW`                      Kết quả phân loại cần nhân viên hỗ
                                      trợ kiểm tra thủ công.

  `MANUALLY_CATEGORIZED`              Nhân viên hỗ trợ đã xác định
                                      category.
  -----------------------------------------------------------------------

## 8. Dữ liệu và API đề xuất cho giai đoạn thiết kế

Các trường và endpoint dưới đây chỉ là đề xuất để Backend, Frontend và
nhóm AI thống nhất; không khẳng định là API hiện có.

### 8.1. Dữ liệu ticket đầu vào

Ví dụ dữ liệu đầu vào:

``` json
{
  "ticket_id": "TK-001",
  "subject": "Motor has unexpected motion",
  "description": "The motor moves unexpectedly during operation."
}
```

### 8.2. Danh mục category hợp lệ

``` json
{
  "allowed_categories": [
    {
      "code": "DOCUMENT_REQUEST",
      "description": "Yêu cầu tài liệu kỹ thuật, manual, sơ đồ chân đấu nối biến tần/động cơ SongNhat."
    },
    {
      "code": "SERVICE_PROGRESS",
      "description": "Tra cứu tiến độ dịch vụ sửa chữa, bảo dưỡng hoặc giao nhận linh kiện."
    },
    {
      "code": "TECHNICAL_ESCALATION",
      "description": "Thu thập dữ kiện sự cố kỹ thuật phức tạp để chuyển kỹ sư chuyên trách."
    }
  ]
}
```

### 8.3. Kết quả quét an toàn

Ví dụ ticket phát hiện dấu hiệu nguy hiểm:

``` json
{
  "ticket_id": "TK-001",
  "hazard_detected": true,
  "matched_keywords": [
    "unexpected motion"
  ],
  "is_hazard_escalated": true,
  "next_action": "URGENT_SAFETY_ENGINEER_HANDOFF"
}
```

### 8.4. Kết quả phân loại ticket

Ví dụ ticket không phát hiện nguy cơ và được phân loại:

``` json
{
  "ticket_id": "TK-002",
  "hazard_detected": false,
  "is_hazard_escalated": false,
  "category": "DOCUMENT_REQUEST",
  "classification_status": "AUTO_CATEGORIZED"
}
```

## 9. Tiêu chí nghiệm thu đề xuất

-   Khi ticket mới được tạo, hệ thống tiếp nhận và bắt đầu quy trình xử
    lý US-02.
-   Ticket được quét các từ khóa nguy cơ: khói (`smoke`), lửa/cháy
    (`fire`), điện giật (`electric shock`), nổ (`explosion`) và chuyển
    động bất thường (`unexpected motion`).
-   Khi phát hiện dấu hiệu nguy hiểm, hệ thống dừng luồng AI đề xuất sửa
    chữa.
-   Khi phát hiện nguy hiểm, hệ thống kích hoạt
    `is_hazard_escalated = TRUE`.
-   Ticket nguy hiểm được chuyển khẩn cấp đến Kỹ sư phụ trách an toàn.
-   Ticket không phát hiện nguy cơ tiếp tục được AI phân loại.
-   AI chỉ được chọn một trong ba category: `DOCUMENT_REQUEST`,
    `SERVICE_PROGRESS`, `TECHNICAL_ESCALATION`.
-   Kết quả phân loại ngoài danh sách ba category phải được xem là không
    hợp lệ và chuyển nhân viên hỗ trợ xem xét.
-   Category và trạng thái xử lý được cập nhật vào ticket.
-   Hệ thống ghi nhận kết quả quét an toàn, category và lịch sử chuyển
    cấp/phân loại.
-   Nhánh xử lý nguy hiểm không bị chuyển nhầm sang luồng phân loại và
    đề xuất sửa chữa thông thường.

## 10. Chỉ số đánh giá thành công

Các chỉ số sau có thể được sử dụng để đánh giá sau khi chức năng được
triển khai:

-   **Category accuracy:** tỷ lệ category AI gán trùng với category được
    xác nhận.
-   **Auto-categorization rate:** tỷ lệ ticket được tự động phân loại
    thành công.
-   **Manual review rate:** tỷ lệ ticket cần nhân viên hỗ trợ phân loại
    thủ công.
-   **Hazard detection coverage:** tỷ lệ ticket có dấu hiệu nguy cơ được
    phát hiện và đưa vào nhánh an toàn.
-   **Safety escalation latency:** thời gian từ lúc tiếp nhận ticket đến
    lúc kích hoạt cờ nguy hiểm và chuyển cấp.
-   **Safety routing completion rate:** tỷ lệ ticket nguy hiểm được
    chuyển đến đúng Kỹ sư phụ trách an toàn.
-   **Incorrect categorization rate:** tỷ lệ ticket bị gán sai một trong
    ba category.
-   **Audit completeness:** tỷ lệ ticket có đầy đủ thông tin log về phân
    loại và quét an toàn.

## 11. Các điểm cần thống nhất trước khi triển khai

-   Danh sách từ khóa nguy cơ chính thức, bao gồm từ đồng nghĩa, cách
    viết khác nhau và ngôn ngữ cần hỗ trợ.
-   Quy tắc xác định dấu hiệu nguy hiểm: chỉ dựa trên từ khóa hay kết
    hợp thêm ngữ cảnh.
-   Cách xử lý khi một ticket đồng thời có nội dung thuộc nhiều
    category.
-   Quy tắc xử lý khi ticket có cả dấu hiệu nguy hiểm và yêu cầu tài
    liệu/tiến độ dịch vụ.
-   Kênh thông báo và SLA cho Kỹ sư phụ trách an toàn.
-   Người có quyền đóng hoặc gỡ cờ `is_hazard_escalated`.
-   Các trường dữ liệu, API và trạng thái thực tế sẽ được sử dụng trong
    hệ thống.
-   Cơ chế lưu audit log và quyền truy cập dữ liệu ticket.

## 12. Tóm tắt

US-02 đề xuất một quy trình tự động xử lý ticket mới gồm hai phần: quét
an toàn bắt buộc và phân loại ticket theo ba danh mục SongNhat.

Điểm quan trọng nhất là **Mandatory Safety Routing được ưu tiên trước
luồng AI thông thường**. Nếu nội dung ticket có dấu hiệu khói, lửa/cháy,
điện giật, nổ hoặc chuyển động bất thường, hệ thống phải dừng luồng AI
đề xuất sửa chữa, đặt `is_hazard_escalated = TRUE` và chuyển khẩn cấp
đến Kỹ sư phụ trách an toàn.

Nếu không phát hiện nguy cơ, AI tiếp tục phân loại ticket vào một trong
ba danh mục `DOCUMENT_REQUEST`, `SERVICE_PROGRESS` hoặc
`TECHNICAL_ESCALATION`. Kết quả được cập nhật vào ticket và lưu nhật ký
để phục vụ theo dõi.

Thiết kế này giúp giảm thao tác phân loại thủ công, đồng thời đảm bảo
các ticket có dấu hiệu nguy hiểm được ưu tiên chuyển đến đúng người phụ
trách an toàn.

**Phạm vi tài liệu:** mô tả đề xuất nghiệp vụ và flow xử lý cho US-02.
Các API, trường dữ liệu và trạng thái cần được nhóm kỹ thuật/nghiệp vụ
thống nhất trước khi implement.
