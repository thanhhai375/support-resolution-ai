export type TicketStatus = "Mới" | "Đang xử lý" | "Chờ duyệt" | "Đã giải quyết";
export type TicketPriority = "Khẩn cấp" | "Cao" | "Trung bình" | "Thấp";
export interface Ticket {
  id: string;
  code: string;
  title: string;
  category: string;
  priority: TicketPriority;
  status: TicketStatus;
  updatedAt: string;
  equipment: string;
  safetyLabel: "High Risk" | "Medium" | "Low";
}