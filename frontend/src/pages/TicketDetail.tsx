import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useTickets } from '../context/TicketsProvider'
import type { TicketPriority, TicketStatus } from '../types/ticket'

const statuses: Record<TicketStatus, string> = {
  PENDING_REVIEW: 'Chờ duyệt',
  PROCESSING: 'Đang xử lý',
  HAZARD_ESCALATED: 'Cảnh báo khẩn cấp',
  RESOLVED: 'Đã giải quyết',
  AI_SOLVED: 'Đã giải quyết',
  ESCALATED: 'Cảnh báo khẩn cấp',
}
function statusClass(status: TicketStatus) {
  if (status === 'RESOLVED' || status === 'AI_SOLVED') return 'resolved'
  if (status === 'HAZARD_ESCALATED' || status === 'ESCALATED') return 'hazard'
  return status === 'PENDING_REVIEW' ? 'pending' : 'processing'
}
const priorities: Record<TicketPriority, string> = { LOW: 'Thấp', MEDIUM: 'Trung bình', HIGH: 'Cao', URGENT: 'Khẩn cấp' }

export default function TicketDetail() {
  const { ticketId } = useParams()
  const { tickets, loading, updateTicket, deleteTicket } = useTickets()
  const navigate = useNavigate()
  const ticket = tickets.find(item => item.id === ticketId)
  const [reply, setReply] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)
  if (loading) return <p role="status">Đang tải ticket…</p>
  if (!ticket) return <section className="panel"><h1>Không tìm thấy ticket</h1><Link to="/tickets" className="text-link">Về danh sách ticket</Link></section>
  const replies = ticket.replies ?? []

  function sendReply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!ticket || !reply.trim()) return
    updateTicket({ ...ticket, replies: [...replies, { id: crypto.randomUUID(), content: reply.trim(), createdAt: new Date().toISOString() }] })
    setReply('')
  }

  return <>
    <div className="ticket-breadcrumb"><Link to="/tickets">Danh sách ticket</Link><span>/</span><span>{ticket.id}</span></div>
    <div className="ticket-detail-heading"><h1>{ticket.title}</h1><div className="ticket-meta"><span className={`status status-${statusClass(ticket.status)}`}>{statuses[ticket.status]}</span><span className={`priority priority-${ticket.priority.toLowerCase()}`}>Ưu tiên {priorities[ticket.priority].toLocaleLowerCase('vi')}</span><span>{ticket.id} • Tạo bởi {ticket.customerName} • {new Date(ticket.createdAt).toLocaleString('vi-VN')}</span></div></div>
    <div className="ticket-detail-layout">
      <section className="panel conversation-panel"><h2>Lịch sử trao đổi</h2>
        <div className="conversation-history" aria-live="polite">
          <article className="message customer-message"><small>{ticket.customerName} • {new Date(ticket.createdAt).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}</small><p>{ticket.description || ticket.title}</p></article>
          {replies.map(message => <article className="message agent-message" key={message.id}><small>Nhân viên hỗ trợ • {new Date(message.createdAt).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}</small><p>{message.content}</p></article>)}
        </div>
        <form className="reply-form" onSubmit={sendReply}><label className="sr-only" htmlFor="ticket-reply">Nội dung phản hồi</label><textarea id="ticket-reply" placeholder="Nhập nội dung phản hồi..." value={reply} onChange={event => setReply(event.target.value)} required /><button className="primary-button" disabled={!reply.trim()}>Gửi phản hồi</button></form>
      </section>
      <aside className="ticket-detail-side">
        <section className="panel ticket-info"><h2>Thông tin ticket</h2><dl><dt>Người phụ trách</dt><dd>{ticket.assignee || 'Chưa phân công'}</dd><dt>Khách hàng</dt><dd>{ticket.customerName}</dd><dt>Thiết bị</dt><dd>{ticket.device}</dd><dt>Nhãn an toàn</dt><dd>{ticket.safetyLabel ? 'Có cảnh báo' : 'Không có cảnh báo'}</dd><dt>Ngày tiếp nhận</dt><dd>{new Date(ticket.createdAt).toLocaleDateString('vi-VN')}</dd></dl>
          <label className="field-label">Trạng thái<select aria-label="Trạng thái" value={ticket.status} onChange={event => updateTicket({ ...ticket, status: event.target.value as TicketStatus })}>{Object.entries(statuses).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
          <label className="field-label">Mức ưu tiên<select aria-label="Mức ưu tiên" value={ticket.priority} onChange={event => updateTicket({ ...ticket, priority: event.target.value as TicketPriority })}>{Object.entries(priorities).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
        </section>
        <section className="insight-panel ai-suggestion"><strong>AI ASSISTANT</strong><h2>Đề xuất xử lý</h2><p>Kiểm tra thông tin yêu cầu và xác nhận tình trạng với khách hàng trước khi thực hiện.</p><ol><li>Xem lại nội dung và lịch sử trao đổi.</li><li>Xác định nguyên nhân và mức độ ưu tiên.</li><li>Gửi phản hồi hướng dẫn cho khách hàng.</li></ol><button className="primary-button" onClick={() => setReply(`Chào bạn, mình đã tiếp nhận yêu cầu "${ticket.title}" và sẽ kiểm tra để hỗ trợ bạn. Bạn vui lòng cung cấp thêm thông tin về tình trạng đang gặp nhé.`)}>Dùng gợi ý</button><small>Gợi ý minh họa • Nhân viên cần kiểm tra trước khi gửi.</small></section>
      </aside>
    </div>
    <div className="detail-footer"><span>Phản hồi và cập nhật được lưu trên trình duyệt này.</span>{confirmDelete ? <div><span>Xóa ticket này?</span><button className="danger-button" onClick={() => { deleteTicket(ticket.id); navigate('/tickets', { replace: true }) }}>Xác nhận xóa</button><button className="secondary-button" onClick={() => setConfirmDelete(false)}>Hủy</button></div> : <button className="danger-ghost" onClick={() => setConfirmDelete(true)}>Xóa ticket</button>}</div>
  </>
}
