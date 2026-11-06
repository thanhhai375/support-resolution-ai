import type { Ticket, TicketPriority, TicketStatus } from '../types/ticket'
import { getStoredToken } from '../auth/token'
import { DEMO_AUTH_ENABLED } from '../auth/demo'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

const mockTickets: Ticket[] = [
  { id: 'TK-1024', title: 'Không thể đăng nhập vào tài khoản', customerName: 'Nguyễn An', status: 'AI_SOLVED', priority: 'HIGH', createdAt: '2026-11-06T09:30:00.000Z', responseTimeMinutes: 12 },
  { id: 'TK-1023', title: 'Yêu cầu đặt lại mật khẩu', customerName: 'Trần Bình', status: 'PROCESSING', priority: 'MEDIUM', createdAt: '2026-11-06T09:18:00.000Z', responseTimeMinutes: 18 },
  { id: 'TK-1022', title: 'Lỗi thanh toán đơn hàng', customerName: 'Lê Minh', status: 'ESCALATED', priority: 'URGENT', createdAt: '2026-11-06T08:55:00.000Z', responseTimeMinutes: 35 },
  { id: 'TK-1021', title: 'Cập nhật thông tin cá nhân', customerName: 'Phạm Hà', status: 'AI_SOLVED', priority: 'LOW', createdAt: '2026-11-06T08:20:00.000Z', responseTimeMinutes: 9 },
  { id: 'TK-1020', title: 'Không nhận được email xác nhận', customerName: 'Đỗ Nam', status: 'PROCESSING', priority: 'MEDIUM', createdAt: '2026-11-06T07:45:00.000Z', responseTimeMinutes: 22 },
  { id: 'TK-1019', title: 'Hướng dẫn sử dụng hệ thống', customerName: 'Vũ Lan', status: 'AI_SOLVED', priority: 'LOW', createdAt: '2026-11-05T14:32:00.000Z', responseTimeMinutes: 7 },
  { id: 'TK-1018', title: 'Tài khoản bị khóa sau nhiều lần đăng nhập', customerName: 'Hoàng Long', status: 'ESCALATED', priority: 'HIGH', createdAt: '2026-11-05T11:10:00.000Z', responseTimeMinutes: 41 },
]

function isStatus(value: unknown): value is TicketStatus {
  return value === 'AI_SOLVED' || value === 'PROCESSING' || value === 'ESCALATED'
}

function isPriority(value: unknown): value is TicketPriority {
  return value === 'LOW' || value === 'MEDIUM' || value === 'HIGH' || value === 'URGENT'
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function normalizeTicket(raw: unknown, index: number): Ticket {
  if (!isRecord(raw)) {
    throw new Error(`Ticket tại vị trí ${index} không phải object hợp lệ`)
  }

  const statusValue = String(raw.status ?? 'PROCESSING').toUpperCase()
  const priorityValue = String(raw.priority ?? 'MEDIUM').toUpperCase()
  const responseTime = raw.responseTimeMinutes

  return {
    id: String(raw.id ?? raw.ticketId ?? `TK-${index + 1}`),
    title: String(raw.title ?? raw.subject ?? 'Chưa có tiêu đề'),
    customerName: String(raw.customerName ?? raw.requesterName ?? raw.customer ?? 'Khách hàng'),
    status: isStatus(statusValue) ? statusValue : 'PROCESSING',
    priority: isPriority(priorityValue) ? priorityValue : 'MEDIUM',
    createdAt: String(raw.createdAt ?? raw.updatedAt ?? new Date().toISOString()),
    responseTimeMinutes: typeof responseTime === 'number' && Number.isFinite(responseTime) && responseTime >= 0
      ? responseTime
      : null,
    description: typeof raw.description === 'string' ? raw.description : '',
    assignee: typeof raw.assignee === 'string' ? raw.assignee : 'Chưa phân công',
  }
}

export async function getTickets(): Promise<{ tickets: Ticket[]; source: 'api' | 'mock' }> {
  if (DEMO_AUTH_ENABLED) return { tickets: mockTickets, source: 'mock' }
  try {
    const token = getStoredToken()
    const response = await fetch(`${API_BASE_URL}/api/tickets`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      signal: AbortSignal.timeout(15_000),
    })
    if (!response.ok) {
      throw new Error(`API trả về HTTP ${response.status}`)
    }

    const payload: unknown = await response.json()
    const rows = Array.isArray(payload)
      ? payload
      : isRecord(payload)
        ? payload.data
        : undefined

    if (!Array.isArray(rows)) {
      throw new Error('Dữ liệu API không đúng định dạng mảng hoặc { data: [] }')
    }

    return { tickets: rows.map(normalizeTicket), source: 'api' }
  } catch (error) {
    console.warn('Không tải được API /api/tickets, chuyển sang mock data:', error)
    return { tickets: mockTickets, source: 'mock' }
  }
}
