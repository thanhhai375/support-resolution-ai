import type { Ticket } from "../types/ticket";

export const mockTickets: Ticket[] = [
  { id:"1042", code:"TK-1042", title:"Quá nhiệt biến tần khi vận hành", category:"Chuyển cấp kỹ thuật", priority:"Khẩn cấp", status:"Đang xử lý", updatedAt:"07/11 10:42", equipment:"Drive VFD-204", safetyLabel:"High Risk" },
  { id:"1041", code:"TK-1041", title:"Cần tài liệu cài đặt biến tần VFD", category:"Tài liệu", priority:"Cao", status:"Chờ duyệt", updatedAt:"07/11 10:42", equipment:"Drive VFD-108", safetyLabel:"Medium" },
  { id:"1040", code:"TK-1040", title:"Cập nhật tiến độ bảo trì động cơ", category:"Tiến độ dịch vụ", priority:"Trung bình", status:"Đang xử lý", updatedAt:"07/11 10:42", equipment:"Motor M-112", safetyLabel:"Low" },
  { id:"1039", code:"TK-1039", title:"Lỗi quá dòng khi khởi động", category:"Chuyển cấp kỹ thuật", priority:"Cao", status:"Mới", updatedAt:"07/11 10:42", equipment:"Motor M-205", safetyLabel:"High Risk" },
  { id:"1038", code:"TK-1038", title:"Hướng dẫn cấu hình thông số", category:"Tài liệu", priority:"Thấp", status:"Đã giải quyết", updatedAt:"07/11 10:42", equipment:"Drive D-302", safetyLabel:"Low" },
  { id:"1037", code:"TK-1037", title:"Dòng rò động cơ vượt ngưỡng an toàn", category:"Cảnh báo an toàn", priority:"Khẩn cấp", status:"Đang xử lý", updatedAt:"07/11 09:18", equipment:"Motor M-318", safetyLabel:"High Risk" },
  { id:"1036", code:"TK-1036", title:"Kiểm tra rung động ổ bi", category:"Tiến độ dịch vụ", priority:"Trung bình", status:"Chờ duyệt", updatedAt:"06/11 16:25", equipment:"Motor M-101", safetyLabel:"Medium" },
  { id:"1035", code:"TK-1035", title:"Tài liệu bảo trì định kỳ", category:"Tài liệu", priority:"Thấp", status:"Đã giải quyết", updatedAt:"06/11 14:05", equipment:"Motor M-008", safetyLabel:"Low" }
];