export type TicketStatus =
  | 'PENDING_REVIEW'
  | 'PROCESSING'
  | 'HAZARD_ESCALATED'
  | 'RESOLVED'
  // Giữ tương thích với dữ liệu cũ nếu backend vẫn trả các trạng thái này.
  | 'AI_SOLVED'
  | 'ESCALATED'

export type TicketPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT'

export interface Ticket {
  id: string
  title: string
  customerName: string
  status: TicketStatus
  priority: TicketPriority
  createdAt: string
  responseTimeMinutes: number | null
  device: string
  safetyLabel: boolean
  description?: string
  assignee?: string
  replies?: { id: string; content: string; createdAt: string }[]
}

export interface TicketApiResponse {
  data?: unknown
}

export function isResolvedStatus(status: TicketStatus): boolean {
  return status === 'RESOLVED' || status === 'AI_SOLVED'
}

export function isHazardStatus(status: TicketStatus): boolean {
  return status === 'HAZARD_ESCALATED' || status === 'ESCALATED'
}
