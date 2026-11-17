import { useEffect, useState } from 'react'
import type { Ticket } from '../types/ticket'
import './ReviewApprovalPanel.css'

type ReviewStatus = 'pending' | 'approved' | 'rejected'

/** CRM-30: FE-only review UI. No approval/rejection API is invoked. */
export default function ReviewApprovalPanel({ ticket }: { ticket: Ticket }) {
  const [draft, setDraft] = useState('')
  const [status, setStatus] = useState<ReviewStatus>('pending')
  const [rejectReason, setRejectReason] = useState('')
  const [showReject, setShowReject] = useState(false)
  const [message, setMessage] = useState('')

  // Each ticket starts from its own illustrative text, not an AI/backend response.
  useEffect(() => {
    setDraft(`Kính gửi ${ticket.customerName},\n\nChúng tôi đã tiếp nhận yêu cầu hỗ trợ về "${ticket.title}". Nhân viên phụ trách sẽ kiểm tra và liên hệ để trao đổi thêm thông tin.\n\nTrân trọng,\nBộ phận hỗ trợ khách hàng`)
    setStatus('pending')
    setRejectReason('')
    setShowReject(false)
    setMessage('')
  }, [ticket.id, ticket.title, ticket.customerName])

  function handleEdit(value: string) {
    setDraft(value)
    setStatus('pending')
    setMessage('')
  }

  function approveAndExport() {
    const customerText = draft.trim()
    if (!customerText) {
      setMessage('Vui lòng nhập nội dung phản hồi khách hàng trước khi duyệt.')
      return
    }

    // Export ONLY editable customer text. No ticket metadata, citations, AI notes or internal fields.
    const blob = new Blob([customerText], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `customer-response-${ticket.id.replace(/[^a-zA-Z0-9_-]/g, '_')}.txt`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    setStatus('approved')
    setShowReject(false)
    setMessage('Đã xuất tệp văn bản dành cho khách hàng. Trạng thái phê duyệt chỉ áp dụng trên giao diện hiện tại.')
  }

  function reject() {
    if (!rejectReason.trim()) {
      setMessage('Bắt buộc nhập lý do từ chối.')
      return
    }
    setStatus('rejected')
    setShowReject(false)
    setMessage('Đã ghi nhận từ chối trên giao diện hiện tại; chưa gửi lên máy chủ.')
  }

  return (
    <section className="panel crm30-review" aria-labelledby="crm30-title">
      <div className="crm30-header">
        <div>
          <span className="crm30-kicker">CRM-30 · Kiểm duyệt phản hồi</span>
          <h2 id="crm30-title">Kiểm duyệt phản hồi</h2>
        </div>
        <span className={`crm30-status crm30-status-${status}`}>
          {status === 'pending' ? 'Chờ duyệt' : status === 'approved' ? 'Đã phê duyệt' : 'Đã từ chối'}
        </span>
      </div>

      <label className="crm30-label" htmlFor="crm30-customer-draft">Bản nháp phản hồi khách hàng</label>
      <textarea
        id="crm30-customer-draft"
        className="crm30-editor"
        spellCheck={false}
        value={draft}
        onChange={event => handleEdit(event.target.value)}
        rows={9}
        placeholder="Nhập nội dung phản hồi dành riêng cho khách hàng..."
      />
      <p className="crm30-helper">Chỉ nội dung trong ô này được xuất ra file .txt. Đây là bản nháp minh họa, chưa phải kết quả từ hệ thống AI hoặc máy chủ.</p>

      {showReject && (
        <div className="crm30-reject-box">
          <label className="crm30-label" htmlFor="crm30-reject-reason">Lý do từ chối <span aria-hidden="true">*</span></label>
          <textarea
            id="crm30-reject-reason"
            rows={3}
            value={rejectReason}
            onChange={event => { setRejectReason(event.target.value); setMessage('') }}
            placeholder="Nêu rõ lý do để điều chỉnh phản hồi..."
            aria-required="true"
          />
          <div className="crm30-actions">
            <button type="button" className="crm30-reject-confirm" onClick={reject}>Xác nhận từ chối</button>
            <button type="button" className="crm30-neutral" onClick={() => { setShowReject(false); setMessage('') }}>Hủy</button>
          </div>
        </div>
      )}

      {!showReject && (
        <div className="crm30-actions">
          <button type="button" className="crm30-neutral" onClick={() => { setShowReject(true); setMessage('') }}>Từ chối</button>
          <button type="button" className="crm30-approve" onClick={approveAndExport} disabled={!draft.trim()}>Phê duyệt &amp; xuất văn bản</button>
        </div>
      )}

      {status === 'rejected' && <p className="crm30-reason"><strong>Lý do từ chối:</strong> {rejectReason}</p>}
      {message && <p className="crm30-message" role="status">{message}</p>}
      <p className="crm30-disclaimer">Bản minh họa giao diện: chưa lưu phê duyệt hoặc từ chối lên máy chủ, chưa gửi phản hồi cho khách hàng. Trạng thái sẽ được đặt lại khi tải lại trang.</p>
    </section>
  )
}