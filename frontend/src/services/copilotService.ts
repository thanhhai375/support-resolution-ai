import { readClaims } from '../auth/token'
import { DEMO_AUTH_ENABLED } from '../auth/demo'
import { knowledgeExcerpts, type KnowledgeExcerpt } from '../data/knowledge'
import type { Ticket } from '../types/ticket'

export interface CopilotDraft {
  intent: string
  draft: string
  citations: KnowledgeExcerpt[]
  approval_status: 'PENDING' | 'APPROVED' | 'REJECTED'
  rejection_reason: string | null
}
export const isCopilotDemo = (token: string | null) => DEMO_AUTH_ENABLED && readClaims(token)?.demo === true
const fixtures = new Map<string, CopilotDraft>()
const base = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

function parseDraft(value: unknown): CopilotDraft {
  const item = value as CopilotDraft
  if (!item || typeof item.intent !== 'string' || typeof item.draft !== 'string' ||
    !['PENDING', 'APPROVED', 'REJECTED'].includes(item.approval_status) ||
    !(item.rejection_reason === null || typeof item.rejection_reason === 'string') ||
    !Array.isArray(item.citations) || item.citations.some(c => !c ||
      !['id', 'title', 'document', 'content', 'revision'].every(key => typeof (c as unknown as Record<string, unknown>)[key] === 'string') ||
      !Number.isInteger(c.page) || !['Motors', 'Drives'].includes(c.productLine))) {
    throw new Error('Dữ liệu bản nháp từ máy chủ không hợp lệ.')
  }
  return item
}
async function request(path: string, token: string | null, init?: RequestInit) {
  const response = await fetch(`${base}${path}`, { ...init,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    signal: AbortSignal.timeout(15000) })
  if (!response.ok) throw new Error(response.status === 404 ? 'Chưa có bản nháp hoặc API chưa sẵn sàng.' :
    response.status === 403 ? 'Bạn không có quyền thực hiện thao tác này.' : 'Không thể xử lý yêu cầu. Vui lòng thử lại.')
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
  return parseDraft(await (await request(`/api/v1/copilot/${encodeURIComponent(ticket.backendId ?? ticket.id)}/approval`, token)).json())
}
export async function reviewCopilot(ticket: Ticket, token: string | null, current: CopilotDraft, action: 'approve' | 'reject', draft: string, reason: string): Promise<CopilotDraft> {
  if (isCopilotDemo(token)) {
    const updated: CopilotDraft = { ...current, draft, approval_status: action === 'approve' ? 'APPROVED' : 'REJECTED', rejection_reason: action === 'reject' ? reason : null }
    fixtures.set(ticket.id, updated)
    return structuredClone(updated)
  }
  const id = ticket.backendId ?? ticket.id
  const result = await (await request(`/api/v1/copilot/${encodeURIComponent(id)}/${action}`, token,
    { method: 'PATCH', body: JSON.stringify({ draft, ...(action === 'reject' ? { rejection_reason: reason } : {}) }) })).json()
  const expected = action === 'approve' ? 'APPROVED' : 'REJECTED'
  if (result.approval_status !== expected || result.persisted !== true) {
    throw new Error('Máy chủ chưa xác nhận lưu quyết định. Hãy tải lại bản nháp trước khi thử lại.')
  }
  try {
    const updated = await getCopilot(ticket, token)
    if (updated.approval_status !== expected) throw new Error('Trạng thái chưa đồng bộ')
    return updated
  } catch {
    throw new Error('Quyết định đã được lưu nhưng chưa tải lại được bản nháp. Hãy tải lại trang, không gửi duyệt lần nữa.')
  }
}
export async function exportCopilotPdf(id: string, token: string | null) {
  const response = await request(`/api/v1/copilot/${encodeURIComponent(id)}/export`, token)
  if (!response.headers.get('content-type')?.includes('application/pdf')) throw new Error('Máy chủ chưa trả về file PDF hợp lệ.')
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = `customer-response-${id.replace(/[^a-zA-Z0-9_-]/g, '_')}.pdf`
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
