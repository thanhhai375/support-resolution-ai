# CRM-1 · US-01 Đặc tả Chức năng và Đề xuất Giải pháp

## 1. Tổng quan và Đề xuất Giải pháp

US-01 biến Copilot thành trợ lý chuẩn bị hồ sơ cho nhân viên hỗ trợ kỹ thuật: với mỗi ticket về động cơ (Motors) và biến tần (Drives), hệ thống tạo một gói hỗ trợ gồm 5 thành phần có kiểm chứng, còn nhân viên giữ toàn quyền chẩn đoán, cam kết và gửi khách.

* **User story:** Là nhân viên hỗ trợ kỹ thuật, tôi muốn xem câu trả lời do AI gợi ý kèm trích dẫn tài liệu để xử lý ticket nhanh và chính xác hơn.
* **Tác nhân:** 
  * **Nhân viên hỗ trợ** (người dùng chính)
  * **Người duyệt kỹ thuật** (duyệt nội dung kỹ thuật)
  * **Quản lý tri thức** (duyệt đoạn tài liệu và danh sách trắng)
* **Nguyên tắc thiết kế:** Mô hình AI chỉ soạn và gợi ý; mọi kiểm soát quyền, an toàn và chính sách chạy bằng mã xác định, nằm ngoài prompt.

### Đề xuất giải pháp theo 5 bước xử lý một gói hỗ trợ

1. **Nạp ngữ cảnh ca:** Đọc ticket và sự kiện từ dữ liệu CSV đã được cấp quyền, kiểm tra quyền truy cập tài khoản và ca.
2. **Định tuyến an toàn:** Bộ quy tắc xác định quét dấu hiệu nguy hiểm; nếu khớp thì chuyển cấp ngay, bỏ qua mọi bước sinh nội dung.
3. **Truy xuất tri thức:** Tìm tối đa 10 đoạn tài liệu đã duyệt, còn hiệu lực, lọc theo model và đối tượng.
4. **Sinh gói hỗ trợ:** Mô hình tạo tóm tắt, danh sách thiếu và bản nháp; mỗi gói gọi mô hình tối đa 2 lần.
5. **Kiểm tra và trình nhân viên:** Kiểm tra trích dẫn, điều kiện áp dụng, rồi hiển thị để nhân viên xem, sửa hoặc duyệt.

### Bảng truy vết mục tiêu, chức năng và thành phần

| Mục tiêu | Mã chức năng | Thành phần giải pháp chính |
| :--- | :--- | :--- |
| **1. Tóm tắt nội dung sự cố** | FR-01 | Bộ tóm tắt có cấu trúc, mỗi dòng gắn sự kiện nguồn |
| **2. Kiểm tra thông tin còn thiếu** | FR-02 | Bộ kiểm tra định danh sản phẩm và checklist câu hỏi mẫu |
| **3. Trích dẫn tài liệu đã duyệt** | FR-03 | Kho đoạn tri thức có phiên bản, bộ truy xuất có lọc, trình xem nguồn |
| **4. Bản nháp phản hồi tiếng Việt** | FR-04 | Bộ soạn thảo dựa trên dữ kiện được phép tiết lộ, kiểm tra độ dài |
| **5. Quyền quyết định thuộc nhân viên** | FR-05 | Màn hình duyệt, trạng thái phê duyệt gắn phiên bản, nhật ký kiểm toán |

---

## 2. Mục tiêu 1: Tóm tắt Nội dung Sự cố (FR-01)

Hệ thống tóm tắt ca thành sáu nhóm thông tin tách bạch, để nhân viên nắm tình huống mà không phải đọc lại toàn bộ lịch sử ticket.

### Chức năng
* **Tách riêng 6 nhóm thông tin:** Triệu chứng khách báo, quan sát đã xác nhận, hành động đã thử, kết quả, câu hỏi tồn đọng, người đang phụ trách.
* Mỗi dòng trích dẫn sự kiện nguồn và giữ thứ tự thời gian; phân biệt "chưa biết" với "không có".
* Lời khách báo giữ nguyên là lời khách, không biến thành khuyết tật hay trách nhiệm đã xác nhận.
* Giữ chính xác mã model, serial, mã lỗi, đơn vị và phủ định; chịu được tiếng Việt thiếu dấu và thuật ngữ tiếng Anh lẫn trong câu.

### Đề xuất giải pháp
* Đầu ra là cấu trúc JSON có trường cố định cho từng nhóm, mỗi phần tử có `event_ref` bắt buộc; phần tử không có nguồn bị loại.
* **Kiểm tra sau sinh:** Đối chiếu mã model, serial, mã lỗi trong tóm tắt với danh sách thực thể đã trích xuất ở bước tiền xử lý (mục 8.4); lệch thì gắn cờ và báo, không tự sửa.
* Không suy ra tuổi, giới tính, mức chuyên môn hay cấu hình thiết bị của khách.

---

## 3. Mục tiêu 2: Kiểm tra Thông tin Còn thiếu (FR-02)

Trước khi đưa bất kỳ hướng dẫn nào, hệ thống kiểm tra khách đã cung cấp đủ thông tin định danh thiết bị chưa, và hỏi lại bằng câu chuẩn nếu chưa.

### Chức năng
* **Checklist bắt buộc:** Model, số serial, phiên bản firmware, cấu hình/revision, mã lỗi chính xác.
* **Mỗi mục trạng thái:** Đã có (kèm nguồn), Còn thiếu, Mâu thuẫn. Dữ liệu mâu thuẫn hiển thị cả hai giá trị, không tự gộp.
* Thiếu hoặc mâu thuẫn thì giữ phần hướng dẫn thủ tục; gói chỉ gồm yêu cầu bổ sung thông tin hoặc chuyển cấp.
* Không suy ra chẩn đoán chỉ từ mã lỗi, không suy ra serial từ model.

### Đề xuất giải pháp
* Bộ quy tắc xác định đối chiếu liên kết khách–sản phẩm đã được phê duyệt; liên kết đề xuất mới phải được nhân viên xác nhận trước khi dùng.
* Thư viện câu hỏi mẫu tiếng Việt đã duyệt, mỗi câu có ID (ví dụ `Q-001`); mô hình chỉ chọn câu, không tự viết câu hỏi kỹ thuật.

---

## 4. Mục tiêu 3: Trích xuất Tài liệu Đã duyệt Kèm Trích dẫn (FR-03)

Mọi khuyến nghị và khẳng định quan trọng phải dựa trên đoạn tài liệu đã được phê duyệt (Approved Passages) và chỉ rõ nguồn để nhân viên tự kiểm tra.

### Chức năng
* Chỉ truy xuất đoạn đã duyệt, còn hiệu lực, đúng model và đúng đối tượng; gồm tối đa 10 đoạn kèm lý do áp dụng; số đoạn thực sự đưa vào mô hình phụ thuộc ngân sách token (mục 8.1).
* Mỗi trích dẫn gồm: Tên tài liệu, phiên bản (revision), trạng thái hiệu lực, mục, số trang hoặc mục, tham chiếu gốc.
* Nhân viên mở được đoạn đã duyệt và vị trí trong tài liệu gốc; không có đường dẫn trực tiếp thì hiển thị tham chiếu ổn định để tra cứu thủ công.
* Không có nguồn phù hợp, hai phiên bản mâu thuẫn hoặc thiếu sơ đồ/bảng thiết yếu: Giữ khuyến nghị liên quan và chuyển yêu cầu thông tin hoặc chuyển cấp, không trả lời từ kiến thức chung của mô hình.
* Nguồn bị thu hồi thì chặn ngay mọi đầu ra phụ thuộc.

### Đề xuất giải pháp
* Kho đoạn tri thức nhập từ CSV UTF-8 đã được quản lý tri thức duyệt, có liên kết thay thế (supersession) giữa các phiên bản.
* Bộ truy xuất lọc theo quyền, model, trạng thái hiệu lực trước khi xếp hạng.
* **Kiểm tra trích dẫn sau sinh:** Mỗi `passage_id` phải tồn tại trong tập truy xuất; trích dẫn bịa bị loại và ghi lỗi.
* Một trích dẫn chứng tỏ nguồn tồn tại chứ không chứng tỏ khuyến nghị đúng, vì vậy người duyệt kỹ thuật vẫn kiểm tra độ phù hợp.

```json
{
  "passage_id": "P-0007",
  "doc_title": "string",
  "revision": "Rev.C",
  "effective_status": "current",
  "section": "4.2",
  "page": 18,
  "applies_because": "khớp model và đối tượng",
  "original_ref": "tham chiếu ổn định hoặc deep link"
}
```

---

## 5. Mục tiêu 4: Bản nháp Phản hồi Tiếng Việt Trung tính (FR-04)

Hệ thống soạn bản nháp để nhân viên chỉnh và dùng, nhưng chỉ từ dữ kiện khách được phép biết và bằng giọng văn trung tính.

### Chức năng
* Tiếng Việt trung tính, thông thường dưới 180 từ; phân biệt rõ yêu cầu bổ sung thông tin, hướng dẫn và đề xuất bước tiếp theo (không phải lịch hẹn hay cam kết).
* Chỉ dùng tập dữ kiện công khai cho người nhận, được chuẩn bị trước khi sinh; không dùng ghi chú nội bộ, giá, dữ liệu khách khác.
* Không còn chỗ giữ chỗ chưa điền hay ghi chú bằng chứng nội bộ trong văn bản.
* Đoạn thủ tục (nếu có) là đoạn danh sách trắng do mã chèn nguyên văn; mô hình chỉ viết phần dẫn dắt không mang tính hướng dẫn vận hành. Khi không có đoạn khớp, áp dụng thang xử lý ở mục 8.2.
* Không chắc về nội dung thì chuyển người duyệt kỹ thuật.

### Đề xuất giải pháp
* Hai luồng ngữ cảnh tách riêng: Luồng nội bộ cho nhân viên và luồng khách chỉ nhận dữ kiện đã lọc.
* **Kiểm tra sau sinh bằng mã xác định (không tốn lượt gọi mô hình):** Đếm từ (chỉ cảnh báo mềm), quét chỗ giữ chỗ, so khớp mã model/serial/đơn vị với thực thể đã xác minh, phát hiện từ ngữ mang tính chỉ dẫn vận hành; chỉ lỗi nghiêm trọng mới kích hoạt lượt sửa (mục 8.3).
* Câu thay thế: Câu yêu cầu thông tin và câu chuyển cấp đã duyệt (xem FR-02 và phần ranh giới).

---

## 6. Mục tiêu 5: Quyền Quyết định Thuộc Nhân viên (FR-05)

Gói hỗ trợ chỉ là gợi ý đã chuẩn bị; không nội dung nào đến tay khách khi nhân viên chưa xem xét, chỉnh sửa hoặc duyệt (Approve).

### Chức năng
* **Màn hình hai cột:** Gói hỗ trợ bên trái; bảng bằng chứng bên phải (vấn đề gốc, định danh sản phẩm, thông tin thiếu, đoạn nguồn, độ mới, nhãn rủi ro).
* **Ba hành động:** Sửa, Từ chối (bắt buộc chọn lý do có cấu trúc), Gửi duyệt. Sửa dữ kiện hoặc hướng dẫn thì kiểm tra lại toàn bộ.
* Nội dung kỹ thuật bắt buộc qua người duyệt kỹ thuật; phê duyệt gắn với ca, người nhận, đúng văn bản, phiên bản nguồn và chính sách, hết hạn sau 1 ngày làm việc hoặc khi có thay đổi quan trọng.
* Trước khi xuất, kiểm tra lại quyền, người nhận, trạng thái nguồn, độ mới và rủi ro; xuất chỉ gồm văn bản gửi khách. Xuất không có nghĩa là đã gửi.
* Nhân viên luôn chuyển cấp được mà không cần tạo phản hồi.

### Đề xuất giải pháp
* Máy trạng thái riêng cho: Nháp, đã duyệt, đã xuất; mỗi chuyển trạng thái ghi người thực hiện, thời gian và phiên bản nguồn.
* Lý do từ chối và chỉnh sửa lưu có cấu trúc để cải thiện sau; không tự huấn luyện lại hay tự đăng tri thức mới.
* Nhật ký kiểm toán ghi phiên bản mô hình, prompt, bộ truy xuất, chính sách và nguồn cho mỗi lần thử.

---

## 7. Ba Ranh giới Nghiêm cấm (Excludes)

Ba ranh giới dưới đây là yêu cầu bắt buộc, được thực thi bằng mã và cấu hình chứ không chỉ bằng lời nhắc cho mô hình. Vi phạm bất kỳ điều nào là lỗi nghiêm trọng, dừng phát hành.

| Ranh giới | Yêu cầu chức năng | Cách thực thi trong giải pháp | Kiểm chứng |
| :--- | :--- | :--- | :--- |
| **B1. AI tuyệt đối không tự động gửi tin cho khách hàng** *(No customer sending)* | Hệ thống chỉ xuất văn bản gửi khách sau khi nhân viên duyệt; việc gửi thực hiện ở ứng dụng hiện có. Không có gửi hàng loạt. | Không cấp cho mô hình bất kỳ công cụ gửi hay thông tin xác thực nào; giao diện không có nút "Gửi khách"; kiểm tra lại quyền, người nhận và văn bản ngay trước khi xuất; chặn nếu dịch vụ chính sách không khả dụng. | Thử đổi người nhận hoặc bằng chứng sau khi duyệt: Phải bị chặn xuất. Kiểm tra văn bản và siêu dữ liệu xuất. |
| **B2. AI không tự động đóng ticket** *(No ticket closure)* | Gợi ý không phải hành động đã thực hiện. Đóng hành chính, hành động đã xác minh và khách xác nhận giải quyết là các trạng thái riêng. | Hệ thống không có quyền ghi vào trạng thái ticket; không coi sự im lặng của khách hay ticket đã đóng là xác nhận giải quyết; bước gợi ý không bao giờ được ghi thành "đã làm". | Khi nhân viên đóng ca chưa có xác nhận của khách: Chỉ ghi "đóng hành chính". |
| **B3. AI không tự chẩn đoán sự cố nguy hiểm hoặc hứa hẹn bảo hành, hoàn tiền** | Gặp dấu hiệu thương tích, khói, cháy, điện giật, chuyển động bất ngờ, thiết bị đang có điện, vô hiệu bảo vệ hoặc nổ thì chuyển cấp ngay cho người có chuyên môn bằng câu đã duyệt, không sinh bước kiểm tra, đấu dây hay khởi động lại. Bảo hành, hoàn tiền, trách nhiệm, giao hàng, tồn kho, giá và thay thế thuộc người có thẩm quyền. | Quy tắc xác định và checklist chuyển cấp chạy trước mô hình; mô hình không thể ghi đè bằng độ tin cậy; thủ tục chỉ qua danh sách trắng ký sẵn; rủi ro chưa rõ thì chuyển cấp; phát biểu về quyền lợi chỉ dùng trường dữ liệu có thẩm quyền, không để mô hình tự tính. | Ca có khói hoặc chuyển động bất ngờ phải chuyển cấp; câu hỏi bảo hành chỉ thu thập chứng từ và chuyển người phụ trách. |

> **Lưu ý phạm vi:** Phát hiện rủi ro là công cụ hỗ trợ, không phải chứng nhận an toàn, và sản phẩm không được định vị là thiết bị an toàn hay thay thế kỹ sư có chuyên môn. Lần sửa chữa thành công trong ticket cũ chỉ là báo cáo lịch sử, không phải quy trình đã duyệt cho thiết bị khác.

---

## 8. Xử lý Ngoại lệ và Giới hạn Hệ thống

Mục này là căn cứ cho Dev viết mã và Tester viết test case. Các giới hạn lấy từ RFP: Mỗi gói tối đa 2 lượt gọi mô hình, mỗi lượt tối đa 8.000 token vào và 1.200 token ra (gồm cả hướng dẫn hệ thống); vượt giới hạn thì giữ lại xử lý, không cắt âm thầm.

### 8.1 Ngân sách token đầu vào (10 đoạn so với 8.000 token)

Rủi ro là có thật: 10 đoạn tài liệu cộng lịch sử ca có thể vượt 8.000 token, nhất là với tiếng Việt vốn tốn token hơn. Một điều chỉnh quan trọng so với đề xuất "cắt tỉa": RFP cấm cắt âm thầm nội dung, nên thuật toán chọn đoạn nguyên vẹn theo thứ hạng, không bao giờ cắt giữa một đoạn hay một sự kiện, và luôn báo cho nhân viên biết cái gì đã bị bỏ.

#### Phân bổ ngân sách đề xuất
*(Giá trị khởi điểm, phải đo lại bằng bộ đếm token của mô hình được chọn trên dữ liệu tiếng Việt thật)*

| Thành phần | Tối đa (Token) |
| :--- | :--- |
| Hướng dẫn hệ thống, schema đầu ra | 1.000 |
| Thực thể đã trích xuất và checklist thiếu thông tin | 300 |
| Sự kiện của ca | 1.800 |
| Đoạn tài liệu | 2.500 |
| **Ngưỡng mềm tổng (70% của 8.000)** | **5.600** |
| Phần dự phòng cho sai số đếm token và lượt sửa | 2.400 |

#### Thuật toán chọn ngữ cảnh
1. Đếm token bằng bộ đếm của chính mô hình; trước khi đo thực tế, dùng hệ số bảo thủ.
2. **Luôn giữ:** Hướng dẫn, thực thể, tin nhắn đầu tiên và mới nhất của khách, các sự kiện chứa dấu hiệu an toàn hoặc dữ kiện định danh.
3. Xếp đoạn tài liệu theo điểm liên quan; thêm nguyên đoạn theo thứ hạng cho tới khi chạm ngưỡng phần của đoạn; đoạn không vừa thì bỏ qua và thử đoạn thấp hơn nhỏ hơn.
4. Các sự kiện còn lại thêm theo thứ tự mới nhất trước tới khi chạm ngưỡng phần sự kiện.
5. **Ghi vào nhật ký và hiện ở giao diện:** *"Đã dùng N/M đoạn, bỏ X sự kiện cũ do giới hạn ngữ cảnh"*; đoạn bị loại hiện trong bảng bằng chứng với nhãn *"không dùng để sinh gói"*. Chỉ đoạn đã đưa vào mô hình mới được trích dẫn.
6. Nếu phần bắt buộc (bước 2) đã vượt ngưỡng 8.000 token: Giữ gói với lý do *"ca quá dài"* và chuyển xử lý thủ công, không gọi mô hình.
7. Nội dung đơn lẻ trên 8.000 ký tự bị cách ly kèm lý do (theo RFP), không đưa vào prompt.
8. Tóm tắt dựa trên một phần lịch sử phải ghi rõ điều đó trên đầu gói.

### 8.2 Khi không có Whitelist Snippet phù hợp (nghẽn khâu duyệt)

Trong giai đoạn thí điểm, hầu hết ca sẽ không có snippet khớp, vì RFP chỉ yêu cầu duyệt 30 đoạn đầu tiên tại G0 và giới hạn ở 2 dòng sản phẩm, 3 loại ca. Vì vậy không có snippet khớp là trạng thái bình thường, không phải lỗi hệ thống và không làm cả gói rơi vào Hold. Chỉ phần hướng dẫn thủ tục bị giữ; tóm tắt, checklist thiếu thông tin và bản nháp vẫn được tạo.

#### Thang xử lý theo thứ tự ưu tiên
1. **Có snippet khớp và đủ điều kiện tiên quyết:** Mã chèn nguyên văn.
2. **Không có snippet nhưng có đoạn đã duyệt không mang tính thủ tục phù hợp** *(ví dụ tài liệu có sẵn, trạng thái dịch vụ)*: Tạo bản nháp thông tin chung, có trích dẫn, tuyệt đối không có bước vận hành hay ngụ ý chỉ dẫn.
3. **Không có đoạn phù hợp, hoặc thiếu định danh:** Bản nháp *"yêu cầu bổ sung thông tin"* bằng câu mẫu đã duyệt.
4. **Có dấu hiệu nguy hiểm, mâu thuẫn tài liệu hoặc rủi ro chưa rõ:** Gói chuyển cấp, không sinh bản nháp thủ tục.

#### Giảm tải cho Knowledge Steward
* Ghi số lần mỗi tình huống "thiếu snippet" xuất hiện; Steward duyệt trước các snippet có nhu cầu cao nhất.
* Đo và báo cáo tỷ lệ gói rơi vào mỗi bậc của thang trên; các ca giữ lại vẫn tính vào mẫu số của chỉ số hữu ích (RFP mục 8), không được tính thành công.
* Phạm vi pilot được giữ nhỏ có chủ ý; không nới whitelist để đạt chỉ số.

### 8.3 Ngân sách 2 lượt gọi mô hình

Lượt 2 là lượt cuối. Mọi lần thử lại, sinh lại và gọi lỗi do nhà cung cấp đều dùng chung 2 lượt này (RFP), và toàn hệ thống tối đa 1.600 lượt gọi mỗi tháng.

* Lượt 1 là lượt sinh chính. Lượt 2 chỉ là lượt sửa, và chỉ khi lượt 1 trượt một kiểm tra nghiêm trọng.
* Nếu lượt 2 vẫn trượt kiểm tra, không gọi lượt 3. Gói chuyển sang trạng thái **"Gợi ý không khả dụng"** kèm lý do cụ thể, chuyển nhân viên xử lý thủ công và cho phép tìm tài liệu thủ công hoặc dùng mẫu đã duyệt.
* Gói không được tự động chạy lại. Chỉ chủ sở hữu hệ thống mới được duyệt hạn mức riêng (có tính phí riêng) cho gói đó.
* Lỗi nhà cung cấp (hết giờ, lỗi mạng) vẫn tính một lượt; kết quả bị cắt vì vượt 1.200 token ra cũng tính là một lượt thất bại.

#### Giảm xác suất cần lượt sửa
* **Chèn thực thể bằng mã:** Mô hình dùng ký hiệu như `{MODEL}`, `{SERIAL}`, `{ERROR_CODE}`; mã thay giá trị đã xác minh trước khi kiểm tra. Nhờ đó mô hình không thể viết sai mã model hay serial.
* **Phân loại kiểm tra:**
  * *Nghiêm trọng (kích hoạt lượt sửa hoặc giữ gói):* Trích dẫn bịa, `event_ref` không tồn tại, thông tin ngoài tập được phép tiết lộ, thủ tục do mô hình viết, lệch thực thể.
  * *Cảnh báo mềm (không tốn lượt, chỉ hiển thị cho nhân viên):* Bản nháp vượt 180 từ (RFP chỉ nói "thông thường dưới 180 từ").
* **Prompt lượt sửa gọn:** Chỉ gửi trường lỗi, thông báo lỗi và bằng chứng liên quan, để luôn nằm trong 8.000 token.
* Mọi kiểm tra chạy bằng mã xác định, không dùng thêm mô hình.

### 8.4 Tiền xử lý tiếng Việt và mã lỗi

Thực hiện bước tiền xử lý xác định (không gọi mô hình, không tốn lượt) dựa trên hai lưu ý:
1. **Văn bản gốc luôn được giữ nguyên.** Bước này chỉ tạo bản chuẩn hóa để so khớp và danh sách thực thể ứng viên kèm vị trí trong văn bản gốc; mô hình nhận cả hai.
2. **Không tự "sửa" mã lỗi.** Mã nhận diện không phân biệt hoa thường (`f0022` thành ứng viên `F0022`) và đối chiếu với từ điển thuật ngữ của hai dòng sản phẩm. Trường hợp mơ hồ (chữ `O` hay số `0`, mã trùng giữa hai dòng) thì hiển thị *"cần nhân viên xác nhận"*; không gộp mờ tự động và không đoán nguyên nhân từ mã (theo DAT 03 và SUP 02).

#### Các thành phần
* Chuẩn hóa Unicode NFC, một bản gập dấu thanh (`"bien tan bao loi f0022"`) chỉ dùng để so khớp.
* Bộ trích thực thể: Model, serial, mã lỗi, đơn vị, phủ định, theo mẫu của từ điển (ví dụ `F0022`, `r0018`, `A501`).
* Từ điển thuật ngữ do Knowledge Steward quản lý, có phiên bản.
* Danh sách thực thể được đưa vào prompt dưới dạng trường có cấu trúc, và làm chuẩn để kiểm tra đầu ra (mục 8.3).

#### Hệ quả cho định tuyến an toàn
Quét từ khóa nguy hiểm phải chạy trên cả bản có dấu và bản gập dấu, vì khách có thể gõ `"khoi"` thay cho `"khói"`. Nhưng bản gập dấu gây nhập nhằng, ví dụ `"chay"` có thể là `"cháy"` (lửa) hoặc `"chạy"` (vận hành). 
* **Quy tắc:** Khớp ở bản có dấu thì chuyển cấp; chỉ khớp ở bản gập dấu với từ nhập nhằng thì giữ phần thủ tục và hiện cảnh báo *"cần kiểm tra an toàn"* để nhân viên quyết định chuyển cấp.

### 8.5 Bảng kịch bản ngoại lệ (EX-01 đến EX-15)

Bốn trạng thái gói: **Sẵn sàng**, **Một phần** (có phần bị giữ, phần còn lại vẫn dùng được), **Chuyển cấp**, **Gợi ý không khả dụng** (chuyển thủ công). Mọi trạng thái đều hiển thị lý do cho nhân viên.

| ID | Tình huống | Hành vi hệ thống | Trạng thái gói | Lượt gọi mô hình |
| :--- | :--- | :--- | :--- | :--- |
| **EX-01** | Ngữ cảnh ước tính vượt ngưỡng mềm 5.600 token | Chọn đoạn và sự kiện nguyên vẹn theo thứ hạng, báo phần bị bỏ (8.1) | Sẵn sàng hoặc Một phần | 1 |
| **EX-02** | Phần bắt buộc đã vượt 8.000 token | Không gọi mô hình, báo "ca quá dài" | Gợi ý không khả dụng | 0 |
| **EX-03** | Một đoạn hoặc sự kiện trên 8.000 ký tự | Cách ly kèm lý do, không đưa vào prompt | Một phần | 1 |
| **EX-04** | Kết quả bị cắt do vượt 1.200 token ra | Coi là lượt thất bại, thử lượt sửa với yêu cầu ngắn hơn | Theo EX-05 hoặc EX-06 | 1 đến 2 |
| **EX-05** | Lượt 1 trượt kiểm tra nghiêm trọng | Lượt 2 chỉ sửa trường lỗi | Sẵn sàng nếu lượt 2 đạt | 2 |
| **EX-06** | Lượt 2 vẫn trượt | Không gọi lượt 3; chuyển thủ công, cho phép tìm thủ công hoặc dùng mẫu | Gợi ý không khả dụng | 2 |
| **EX-07** | Hết hạn mức 1.600 lượt/tháng hoặc ngân sách chi phí | Giữ lại, báo lý do; chỉ chủ sở hữu duyệt hạn mức riêng mới tiếp tục | Gợi ý không khả dụng | 0 |
| **EX-08** | Không có whitelist snippet khớp | Thang xử lý bậc 2 đến 4 (8.2); không báo lỗi hệ thống | Một phần | 1 |
| **EX-09** | Không có đoạn tài liệu phù hợp hoặc mâu thuẫn phiên bản | Bản nháp yêu cầu bổ sung thông tin hoặc chuyển cấp; hiển thị cả hai tham chiếu nếu mâu thuẫn | Một phần hoặc Chuyển cấp | 1 |
| **EX-10** | Mã lỗi hoặc model mơ hồ (O hay 0, thiếu dấu, trùng giữa hai dòng) | Hiện "cần nhân viên xác nhận"; giữ phần thủ tục | Một phần | 1 |
| **EX-11** | Dấu hiệu nguy hiểm ở bản có dấu | Chuyển cấp trước mô hình bằng câu đã duyệt | Chuyển cấp | 0 |
| **EX-12** | Chỉ khớp từ nhập nhằng ở bản gập dấu ("chay") | Giữ phần thủ tục, hiện cảnh báo "cần kiểm tra an toàn" | Một phần | 1 |
| **EX-13** | Lỗi hoặc hết giờ từ nhà cung cấp mô hình | Tính một lượt; lượt 2 nếu còn; sau đó chuyển thủ công | Gợi ý không khả dụng | 1 đến 2 |
| **EX-14** | Nguồn bị thu hồi hoặc quyền thay đổi khi đang sinh | Chặn xuất mọi đầu ra phụ thuộc | Một phần hoặc Gợi ý không khả dụng | Theo tiến trình |
| **EX-15** | Dịch vụ chính sách hoặc phân quyền không khả dụng | Chặn xuất, không dự đoán quyền (fail closed) | Gợi ý không khả dụng | 0 |

> *Ghi chú:* Mỗi dòng cần ít nhất một test case; EX-05, EX-06, EX-11 và EX-14 là test chặn phát hành.

---

## 9. Ràng buộc Cấu trúc Dữ liệu và Kiểm soát JSON

Để đảm bảo mô hình AI trả về kết quả đồng nhất, không bị lỗi định dạng hay tự bịa ra các trường thông tin lạ, hệ thống áp dụng cơ chế kiểm soát dữ liệu 2 tầng:

* **Nguyên tắc khóa chặt thuộc tính (Strict Property Rules):** Thiết lập quy tắc cấm thuộc tính thừa (`additionalProperties: false`) để hệ thống tự động từ chối bất kỳ gói dữ liệu nào chứa các trường không được định nghĩa trước. Phân biệt rõ giữa Cảnh báo mềm (chỉ hiển thị nhắc nhở cho nhân viên, ví dụ: bản nháp vượt nhẹ 180 từ) và Lỗi nghiêm trọng (chặn gói hoặc chạy lượt sửa, ví dụ: trích dẫn bịa, thiếu nguồn sự kiện).
* **Mô hình xử lý 2 tầng (Two-tier Payload Construction):**
  * *Tầng LLM (Mô hình AI):* AI chỉ chịu trách nhiệm sinh các trường nội dung lõi (`case_summary`, `missing_facts`, `customer_draft.text`). Việc thu hẹp phạm vi đầu ra giúp tiết kiệm token và giảm tối đa tỷ lệ sinh lỗi.
  * *Tầng Backend (Mã hệ thống):* Code phần mềm tự động tính toán số từ, kiểm tra trùng lặp, gắn mã kiểm toán (`task_id`, `audit`), ghép nối danh sách trích dẫn (`citations`) và phân định trạng thái gói (`ready`, `partial`, `escalate`, `unavailable`) trước khi hiển thị lên màn hình nhân viên.
* **Quy tắc bắt buộc đối với nguồn sự kiện (`event_ref`):** Mỗi dòng tóm tắt sự cố (`case_summary`) bắt buộc phải gắn kèm mảng mã sự kiện nguồn (`event_ref` chứa từ 1 đến 20 phần tử, dạng chuỗi như `EV-001`). Định dạng mảng chuỗi giúp bảo toàn chính xác các tiền tố và số 0 ở đầu mã sự kiện. Các dòng tóm tắt không có nguồn đối chiếu sẽ bị mã hệ thống tự động lọc bỏ.