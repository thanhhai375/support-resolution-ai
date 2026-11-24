import { createDemoToken, DEMO_EMAIL, DEMO_PASSWORD } from '../auth/demo'
import type { UserRole } from '../auth/token'
import { useEffect, useRef, useState } from 'react'
import type { Ticket } from '../types/ticket'
import { useAuth } from '../auth/AuthProvider'
import { exportCopilotPdf, getCopilot, isCopilotDemo, reviewCopilot, type CopilotDraft } from '../services/copilotService'
import SourceViewer from './SourceViewer'
import type { KnowledgeExcerpt } from '../data/knowledge'
import './ReviewApprovalPanel.css'

export default function ReviewApprovalPanel({ ticket }: { ticket: Ticket }) {
  const { role, token, signIn } = useAuth()
  const canReview = role === 'ENGINEER' || role === 'MANAGER'
  const [data, setData] = useState<CopilotDraft | null>(null)
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [reason, setReason] = useState('')
  const [selected, setSelected] = useState<KnowledgeExcerpt | null>(null)
  const dialog = useRef<HTMLDialogElement>(null)
  const rejectButton = useRef<HTMLButtonElement>(null)
  const version = useRef(0)
  useEffect(() => {
    const request = ++version.current
    setLoading(true); setBusy(false); setData(null); setError(''); setSelected(null); setReason('')
    dialog.current?.close()
    getCopilot(ticket, token).then(value => {
      if (request === version.current) { setData(value); setDraft(value.draft) }
    }).catch(() => {
      if (request === version.current) setError('Không thể tải bản nháp. API có thể chưa sẵn sàng. Vui lòng thử lại.')
    }).finally(() => { if (request === version.current) setLoading(false) })
    return () => { version.current++ }
  }, [ticket.id, token, retry]) // Reload only when the ticket/session changes.

  async function review(action: 'approve' | 'reject') {
    if (!data || busy || !canReview || !draft.trim() || (action === 'reject' && !reason.trim())) return
    const request = version.current
    setBusy(true); setError('')
    try {
      const updated = await reviewCopilot(ticket.id, token, data, action, draft.trim(), reason.trim())
      if (request !== version.current) return
      setData(updated); setDraft(updated.draft)
      dialog.current?.close(); rejectButton.current?.focus()
    } catch (cause) {
      if (request === version.current) setError(cause instanceof Error ? cause.message : 'Không thể cập nhật phê duyệt.')
    } finally { if (request === version.current) setBusy(false) }
  }
  async function exportPdf() {
    if (!data || data.approval_status !== 'APPROVED' || busy) return
    setBusy(true); setError('')
    try {
      if (isCopilotDemo(token)) {
        const preview = window.open('', '_blank')
        if (!preview) throw new Error('Vui lòng cho phép mở cửa sổ để lưu PDF.')
        preview.document.title = `Phản hồi khách hàng - ${ticket.id}`
        const style = preview.document.createElement('style')
        style.textContent = 'body{font:16px Arial,sans-serif;margin:24mm}pre{white-space:pre-wrap;font:inherit;line-height:1.6}'
        preview.document.head.append(style)
        const content = preview.document.createElement('pre')
        content.textContent = data.draft
        preview.document.body.append(content)
        preview.focus(); preview.print()
      } else await exportCopilotPdf(ticket.id, token)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Không thể xuất PDF.') }
    finally { setBusy(false) }
  }
  const dirty = data !== null && draft !== data.draft
  return <section className="panel crm30-review" aria-labelledby="copilot-title" aria-busy={loading || busy}>
    <div className="crm30-header"><h2 id="copilot-title">Bản nháp Copilot AI</h2>
      {data && <span role="status" className={`crm30-status crm30-status-${data.approval_status.toLowerCase()}`}>{data.approval_status}</span>}
    </div>
    {isCopilotDemo(token) && <label className="crm30-label">Vai trò demo
      <select aria-label="Vai trò demo" value={role ?? 'ADMIN'} disabled={busy || loading} onChange={event => {
        setError('')
        void signIn(createDemoToken(DEMO_EMAIL, DEMO_PASSWORD, event.target.value as UserRole)).catch(() => setError('Không thể đổi vai trò demo.'))
      }}>
        <option value="ADMIN">ADMIN — chỉ xem</option>
        <option value="STAFF">STAFF — chỉ xem</option>
        <option value="ENGINEER">ENGINEER — chỉnh sửa và duyệt</option>
        <option value="MANAGER">MANAGER — chỉnh sửa và duyệt</option>
      </select>
    </label>}
    {loading && <p role="status">Đang tải bản nháp…</p>}
    {error && <p role="alert" className="crm30-reason">{error}</p>}
    {!loading && !data && <button className="secondary-button" onClick={() => setRetry(value => value + 1)}>Thử lại</button>}
    {data && <>
      <p><strong>Intent:</strong> {data.intent}</p>
      {isCopilotDemo(token) && <p className="crm30-helper">Dữ liệu demo. Phê duyệt được giữ trong phiên chạy; xuất PDF mở hộp thoại in, chọn Lưu dưới dạng PDF.</p>}
      <label className="crm30-label" htmlFor="copilot-draft">Nội dung phản hồi khách hàng</label>
      <textarea id="copilot-draft" className="crm30-editor" rows={10} value={draft} readOnly={!canReview || busy || data.approval_status === 'APPROVED'} onChange={event => setDraft(event.target.value)} />
      {dirty && <p className="crm30-helper">Có chỉnh sửa chưa lưu. Nội dung sẽ được gửi kèm khi phê duyệt hoặc từ chối.</p>}
      <div className="copilot-citations"><h3>Tài liệu trích dẫn</h3>
        {data.citations.length === 0 && <p>Chưa có trích dẫn.</p>}
        {data.citations.map(item => <button key={item.id} className="evidence-source-button" onClick={() => setSelected(item)}>Xem tài liệu nguồn {item.id} · {item.title} · Trang {item.page}</button>)}
      </div>
      {data.approval_status === 'REJECTED' && <p className="crm30-reason"><strong>Lý do từ chối:</strong> {data.rejection_reason || 'Chưa có lý do.'}</p>}
      {canReview && data.approval_status !== 'APPROVED' && <div className="crm30-actions">
        <button ref={rejectButton} className="crm30-neutral" disabled={busy || !draft.trim()} onClick={() => { setReason(''); setError(''); dialog.current?.showModal() }}>Từ chối</button>
        <button className="crm30-approve" disabled={busy || !draft.trim()} onClick={() => void review('approve')}>{busy ? 'Đang xử lý…' : 'Phê duyệt'}</button>
      </div>}
      {data.approval_status === 'APPROVED' && <button className="primary-button" disabled={busy} onClick={() => void exportPdf()}>Xuất PDF</button>}
      {!canReview && <p className="crm30-helper">Bạn có quyền xem. Phê duyệt dành cho ENGINEER và MANAGER.</p>}
    </>}
    <dialog ref={dialog} className="copilot-reject-dialog" aria-labelledby="reject-title" onCancel={event => { if (busy) event.preventDefault() }} onClose={() => rejectButton.current?.focus()}>
      <form onSubmit={event => { event.preventDefault(); void review('reject') }}>
        <h2 id="reject-title">Từ chối bản nháp</h2>
        <label htmlFor="copilot-reason">Lý do từ chối</label>
        <textarea id="copilot-reason" autoFocus required maxLength={2000} value={reason} disabled={busy} onChange={event => setReason(event.target.value)} />
        {error && <p role="alert">{error}</p>}
        <div className="crm30-actions"><button type="button" className="crm30-neutral" disabled={busy} onClick={() => dialog.current?.close()}>Hủy</button>
          <button className="crm30-reject-confirm" disabled={busy || !reason.trim()}>{busy ? 'Đang xử lý…' : 'Xác nhận từ chối'}</button></div>
      </form>
    </dialog>
    <SourceViewer excerpt={selected} onClose={() => setSelected(null)} illustrative={isCopilotDemo(token)} />
  </section>
}
