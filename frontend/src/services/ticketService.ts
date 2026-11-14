import type { Ticket, TicketPriority, TicketStatus } from '../types/ticket'
import { getStoredToken } from '../auth/token'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

const mockTickets: Ticket[] = [
  { id: 'TK-1024', title: 'Động cơ không khởi động sau khi cấp nguồn', customerName: 'Nguyễn An', status: 'PENDING_REVIEW', priority: 'HIGH', createdAt: '2026-11-06T09:30:00.000Z', responseTimeMinutes: 12, device: 'Motor', safetyLabel: false },
  { id: 'TK-1023', title: 'Biến tần phát cảnh báo quá dòng', customerName: 'Trần Bình', status: 'PROCESSING', priority: 'MEDIUM', createdAt: '2026-11-06T09:18:00.000Z', responseTimeMinutes: 18, device: 'Drive', safetyLabel: false },
  { id: 'TK-1022', title: 'Tủ điện có dấu hiệu quá nhiệt', customerName: 'Lê Minh', status: 'HAZARD_ESCALATED', priority: 'URGENT', createdAt: '2026-11-06T08:55:00.000Z', responseTimeMinutes: 35, device: 'Motor', safetyLabel: true },
  { id: 'TK-1021', title: 'Rung bất thường khi vận hành động cơ', customerName: 'Phạm Hà', status: 'RESOLVED', priority: 'LOW', createdAt: '2026-11-06T08:20:00.000Z', responseTimeMinutes: 9, device: 'Motor', safetyLabel: false },
  { id: 'TK-1020', title: 'Drive hiển thị mã lỗi F-001', customerName: 'Đỗ Nam', status: 'PROCESSING', priority: 'MEDIUM', createdAt: '2026-11-06T07:45:00.000Z', responseTimeMinutes: 22, device: 'Drive', safetyLabel: true },
]

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function normalizeStatus(value: unknown): TicketStatus {
  const status = String(value ?? 'PROCESSING').toUpperCase()

  if (status === 'OPEN' || status === 'PENDING' || status === 'PENDING_REVIEW') {
    return 'PENDING_REVIEW'
  }

  if (status === 'IN_PROGRESS' || status === 'PROCESSING') {
    return 'PROCESSING'
  }

  if (status === 'CLOSED') return 'CLOSED'

if (status === 'RESOLVED') return 'RESOLVED'

if (status === 'AI_SOLVED') return 'AI_SOLVED'

  if (status === 'ESCALATED' || status === 'HAZARD_ESCALATED') {
    return 'HAZARD_ESCALATED'
  }

  return 'PROCESSING'
}

function normalizePriority(value: unknown): TicketPriority {
  const priority = String(value ?? 'MEDIUM').toUpperCase()

  if (priority === 'CRITICAL') return 'URGENT'

  return priority === 'LOW'
    || priority === 'MEDIUM'
    || priority === 'HIGH'
    || priority === 'URGENT'
    ? priority
    : 'MEDIUM'
}

function normalizeTicket(raw: unknown, index: number): Ticket {
  if (!isRecord(raw)) throw new Error(`Ticket tại vị trí ${index} không hợp lệ`)
  const responseTime = raw.responseTimeMinutes
  return {
    id: String(raw.ticket_number ?? raw.id ?? raw.ticketId ?? raw.caseId ?? `TK-${index + 1}`),
    title: String(raw.subject ?? raw.title ?? 'Chưa có tiêu đề').replace('Khách hàng', '').trim(),
    customerName: String(
      raw.customerName
      ?? raw.customer_name
      ?? raw.created_by
      ?? raw.requesterName
      ?? raw.customer
      ?? 'Khách hàng'
),
    status: normalizeStatus(raw.status),
    priority: normalizePriority(raw.priority),
    createdAt: String(raw.createdAt ?? raw.updatedAt ?? new Date().toISOString()),
    responseTimeMinutes: typeof responseTime === 'number' && Number.isFinite(responseTime) && responseTime >= 0 ? responseTime : null,
    device: String(raw.device ?? raw.equipment ?? raw.product_name ?? raw.productName ?? raw.category ?? 'Chưa xác định'),

      safetyLabel: raw.safetyLabel === true
        || raw.safety_label === true
        || raw.is_hazard_escalated === true
        || raw.safetyLabel === 'true',

      serialNumber: String(raw.serial_number ?? raw.serialNumber ?? ''),

      hazardReason: String(raw.hazard_reason ?? raw.hazardReason ?? ''),

      description: typeof raw.description === 'string' ? raw.description : '',
      assignee: typeof raw.assignee === 'string' ? raw.assignee : 'Chưa phân công',
  }
}

export async function getTickets(): Promise<{ tickets: Ticket[]; source: 'api' | 'mock' }> {
  try {
    const token = getStoredToken()
    const response = await fetch(`${API_BASE_URL}/api/tickets?page=0&size=100`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      signal: AbortSignal.timeout(15000),
    })
    if (!response.ok) throw new Error(`API trả về HTTP ${response.status}`)
    const payload: unknown = await response.json()
    const rows = Array.isArray(payload)
  ? payload
  : isRecord(payload)
    ? (payload.items ?? payload.data ?? payload.tickets)
    : undefined
    if (!Array.isArray(rows)) throw new Error('API cần trả về mảng ticket hoặc object chứa data/tickets')
    return { tickets: rows.map(normalizeTicket), source: 'api' }
  } catch (error) {
    console.warn('Không tải được API /api/tickets:', error)
    return { tickets: mockTickets, source: 'mock' }
  }
}
export interface TicketOption {
  id: string
  name: string
}

export interface TicketOptions {
  products: TicketOption[]
  categories: TicketOption[]
}

export async function getTicketOptions(): Promise<TicketOptions> {
  const token = getStoredToken()

  const response = await fetch(`${API_BASE_URL}/api/tickets/options`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal: AbortSignal.timeout(15000),
  })

  if (!response.ok) {
    throw new Error(`Không tải được danh sách sản phẩm và danh mục: HTTP ${response.status}`)
  }

  const payload: unknown = await response.json()

  if (
    !isRecord(payload)
    || !Array.isArray(payload.products)
    || !Array.isArray(payload.categories)
  ) {
    throw new Error('Dữ liệu sản phẩm hoặc danh mục không hợp lệ')
  }

  return {
    products: payload.products.filter(
      (item): item is TicketOption =>
        isRecord(item)
        && typeof item.id === 'string'
        && typeof item.name === 'string'
    ),
    categories: payload.categories.filter(
      (item): item is TicketOption =>
        isRecord(item)
        && typeof item.id === 'string'
        && typeof item.name === 'string'
    ),
  }
}
export interface CreateTicketInput {
  title: string
  customerName: string
  description: string
  priority: TicketPriority
  productId: string
  categoryId: string
  isHazardEscalated: boolean
  hazardReason: string
}

export async function createTicket(input: CreateTicketInput): Promise<Ticket> {
  const token = getStoredToken()

  const response = await fetch(`${API_BASE_URL}/api/tickets`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
  subject: input.title,
  description: input.description,
  product_id: input.productId,
  category_id: input.categoryId,
  priority: input.priority === 'URGENT' ? 'CRITICAL' : input.priority,
  created_by: input.customerName,
  is_hazard_escalated: input.isHazardEscalated,
  hazard_reason: input.isHazardEscalated ? input.hazardReason : null,
}),
    signal: AbortSignal.timeout(15000),
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`Không tạo được ticket: HTTP ${response.status} - ${errorText}`)
  }

  const payload: unknown = await response.json()

  if (!isRecord(payload) || !isRecord(payload.data)) {
    throw new Error('Dữ liệu ticket trả về không hợp lệ')
  }

  const raw = payload.data
  const ticket = normalizeTicket(raw, 0)

  return {
    ...ticket,
    customerName: input.customerName,
    createdAt: String(raw.created_at ?? raw.createdAt ?? new Date().toISOString()),
    priority: input.priority,
  }
}