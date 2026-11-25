import { getCurrentUser } from './authService'
import { readClaims } from '../auth/token'
import { DEMO_AUTH_ENABLED } from '../auth/demo'
import { knowledgeExcerpts, type KnowledgeExcerpt } from '../data/knowledge'
import type { Ticket } from '../types/ticket'

export interface CopilotDraft {
  intent: string
  draft: string
  citations: KnowledgeExcerpt[]
  approval_status: 'PENDING' | 'APPROVED' | 'REJECTED'
  missing_facts?: string[]
  next_step?: string
  is_hazard_escalated?: boolean
  rejection_reason: string | null
}
export const isCopilotDemo = (token: string | null) => DEMO_AUTH_ENABLED && readClaims(token)?.demo === true
const fixtures = new Map<string, CopilotDraft>()
const base = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

function parsePackage(value: unknown): CopilotDraft {
  if (!value || typeof value !== 'object') throw new Error('Support Package không hợp lệ.')
  const item = value as Record<string, unknown>
  if (typeof item.intent !== 'string' || typeof item.draft !== 'string') throw new Error('Thiếu intent hoặc draft trong Support Package.')
  const citations = Array.isArray(item.citations) ? item.citations.map((raw, index): KnowledgeExcerpt => {
    const c = raw as Record<string, unknown>
    if (!c || typeof c.document_title !== 'string' || typeof c.content_snippet !== 'string' || typeof c.page_number !== 'number') throw new Error('Trích dẫn từ Backend không hợp lệ.')
    return { id: String(c.passage_id || `source-${index + 1}`), title: String(c.section || c.document_title), document: c.document_title, page: c.page_number, content: c.content_snippet, revision: String(c.version || 'Chưa xác định'), productLine: 'Chưa xác định' }
  }) : []
  return { intent: item.intent, draft: item.draft, citations, approval_status: 'PENDING', rejection_reason: null,
    missing_facts: Array.isArray(item.missing_facts) ? item.missing_facts.filter((v): v is string => typeof v === 'string') : [],
    next_step: typeof item.next_step === 'string' ? item.next_step : undefined,
    is_hazard_escalated: item.is_hazard_escalated === true }
}
const pending = new Map<string, Promise<CopilotDraft>>()
async function request(path: string, token: string | null, init?: RequestInit) {
  const response = await fetch(`${base}${path}`, { ...init,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    signal: AbortSignal.timeout(90000) })
  if (!response.ok) throw new Error(`Copilot API: HTTP ${response.status}. ${response.status === 403 ? 'Bạn không có quyền thực hiện thao tác này.' : 'Vui lòng kiểm tra Network.'}`)
  return response
}
export async function getCopilot(ticket: Ticket, token: string | null): Promise<CopilotDraft> {
  if (isCopilotDemo(token)) {
    if (!fixtures.has(ticket.id)) fixtures.set(ticket.id, {
      intent: 'Hỗ trợ kỹ thuật', draft: `Kính gửi ${ticket.customerName},\n\nChúng tôi đã tiếp nhận yêu cầu "${ticket.title}". Vui lòng cung cấp model, serial và mã cảnh báo để bộ phận kỹ thuật kiểm tra.\n\nTrân trọng,\nBộ phận hỗ trợ khách hàng`,
      citations: knowledgeExcerpts.filter(c => c.productLine === (/drive|biến tần/i.test(ticket.device) ? 'Drives' : 'Motors')).slice(0, 2),
      approval_status: 'PENDING', rejection_reason: null,
    })
    return structuredClone(fixtures.get(ticket.id)!)
  }
  if (!token) throw new Error('Bạn cần đăng nhập lại.')
  if (!ticket.backendId || !ticket.productId) throw new Error('Ticket thiếu UUID hoặc Product ID từ Backend.')
  const body = JSON.stringify({ ticket_description: ticket.description?.trim() || ticket.title, ticket_id: ticket.backendId, product_id: ticket.productId, limit: 3 })
  const key = JSON.stringify([token, body])
  const existing = pending.get(key)
  if (existing) return existing
  const task = request(`/api/tickets/${encodeURIComponent(ticket.backendId)}/copilot/generate`, token, { method: 'POST', body }).then(r => r.json()).then(parsePackage).finally(() => pending.delete(key))
  pending.set(key, task)
  return task
}
export async function reviewCopilot(ticket: Ticket, token: string | null, current: CopilotDraft, action: 'approve' | 'reject', draft: string, reason: string): Promise<CopilotDraft> {
  if (isCopilotDemo(token)) {
    const updated: CopilotDraft = { ...current, draft, approval_status: action === 'approve' ? 'APPROVED' : 'REJECTED', rejection_reason: action === 'reject' ? reason : null }
    fixtures.set(ticket.id, updated)
    return structuredClone(updated)
  }
  if (!token || !ticket.backendId) throw new Error('Thiếu phiên đăng nhập hoặc UUID ticket.')
  if (action === 'reject') {
    if (!reason.trim()) throw new Error('Vui lòng nhập lý do từ chối.')
    const user = await getCurrentUser(token)
    if (!user.email || !['ENGINEER', 'MANAGER'].includes(user.role)) throw new Error('Bạn không có quyền từ chối bản nháp.')
    const response = await request(`/api/v1/copilot/${encodeURIComponent(ticket.backendId)}/reject`, token, {
      method: 'PATCH', body: JSON.stringify({ rejection_reason: reason.trim(), rejected_by: user.email }),
    })
    const result = await response.json()
    if (result.persisted !== true || result.approval_status !== 'REJECTED') {
      throw new Error('Backend chưa xác nhận lưu trạng thái từ chối. Vui lòng liên hệ đội Backend.')
    }
    return { ...current, approval_status: 'REJECTED', rejection_reason: reason.trim() }
  }
  if (draft !== current.draft.trim()) throw new Error('Backend chưa hỗ trợ lưu nội dung đã chỉnh sửa.')
  const response = await request(`/api/tickets/${encodeURIComponent(ticket.backendId)}/copilot/approve`, token, { method: 'PATCH', body: '{}' })
  const result = await response.json()
  if ((result.data?.status ?? result.status) !== 'RESOLVED') throw new Error('Backend chưa xác nhận trạng thái đã giải quyết.')
  return { ...current, approval_status: 'APPROVED', rejection_reason: null }
}
export async function exportCopilotPdf(id: string, token: string | null, data?: CopilotDraft): Promise<void> {
  if (!data || data.approval_status !== 'APPROVED' || !data.draft.trim()) {
    throw new Error('Chỉ được xuất bản nháp đã duyệt.')
  }
  // Real export must remain blocked until the server supplies the saved approved
  // content and authoritative case/account/source IDs for export-check.
  if (!isCopilotDemo(token)) {
    throw new Error('Backend chưa cung cấp bản duyệt đã lưu và dữ liệu kiểm tra quyền xuất PDF.')
  }
  const preview = window.open('', '_blank')
  if (!preview) throw new Error('Vui lòng cho phép mở cửa sổ để lưu PDF.')
  preview.opener = null
  preview.document.title = `DEMO - Phản hồi khách hàng - ${id}`
  const style = preview.document.createElement('style')
  style.textContent = '@page{size:A4;margin:20mm}body{font:14px Arial,sans-serif;color:#111}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;line-height:1.6}'
  preview.document.head.append(style)
  const heading = preview.document.createElement('h1')
  heading.textContent = 'Phản hồi khách hàng (DEMO)'
  const meta = preview.document.createElement('p')
  meta.textContent = `Ticket: ${id} — Dữ liệu minh họa, không gửi khách hàng.`
  const content = preview.document.createElement('pre')
  content.textContent = data.draft
  preview.document.body.append(heading, meta, content)
  preview.focus()
  preview.print()
}
