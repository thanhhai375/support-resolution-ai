export type TicketStatus = 'AI_SOLVED' | 'PROCESSING' | 'ESCALATED'
export type TicketPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT'

export interface Ticket {
  id: string
  title: string
  customerName: string
  status: TicketStatus
  priority: TicketPriority
  createdAt: string
  responseTimeMinutes: number | null
  description?: string
  assignee?: string
}

export interface TicketApiResponse {
  data?: unknown
}
