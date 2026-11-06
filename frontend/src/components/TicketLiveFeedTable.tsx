import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { Ticket, TicketPriority, TicketStatus } from '../types/ticket'

const statusLabels: Record<TicketStatus, string> = { AI_SOLVED: 'Đã giải quyết', PROCESSING: 'Đang xử lý', ESCALATED: 'Chuyển cấp' }
const priorityLabels: Record<TicketPriority, string> = { LOW: 'Thấp', MEDIUM: 'Trung bình', HIGH: 'Cao', URGENT: 'Khẩn cấp' }
const PAGE_SIZE = 7

export default function TicketLiveFeedTable({ tickets, loading, onSelect }: { tickets: Ticket[]; loading: boolean; onSelect: (ticket: Ticket) => void }) {
  const [params, setParams] = useSearchParams()
  const keyword = params.get('search') ?? ''
  const [status, setStatus] = useState('ALL')
  const [priority, setPriority] = useState('ALL')
  const [assignee, setAssignee] = useState('ALL')
  const [page, setPage] = useState(1)
  const filtered = tickets.filter(ticket => `${ticket.id} ${ticket.title} ${ticket.customerName}`.toLocaleLowerCase('vi').includes(keyword.trim().toLocaleLowerCase('vi'))
    && (status === 'ALL' || ticket.status === status) && (priority === 'ALL' || ticket.priority === priority)
    && (assignee === 'ALL' || (ticket.assignee || 'Chưa phân công') === assignee))
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const currentPage = Math.min(page, pageCount)
  const start = (currentPage - 1) * PAGE_SIZE
  const assignees = [...new Set(tickets.map(ticket => ticket.assignee || 'Chưa phân công'))]
  return <section className="ticket-feed" aria-label="Danh sách yêu cầu hỗ trợ">
    <div className="table-toolbar">
      <label className="search-box"><span aria-hidden="true">⌕</span><input aria-label="Tìm kiếm ticket" placeholder="Tìm theo mã hoặc người gửi" value={keyword} onChange={event => {
        setPage(1)
        setParams(current => { const next = new URLSearchParams(current); if (event.target.value) next.set('search', event.target.value); else next.delete('search'); return next }, { replace: true })
      }} /></label>
      <select aria-label="Lọc theo trạng thái" value={status} onChange={event => { setStatus(event.target.value); setPage(1) }}><option value="ALL">Tất cả trạng thái</option>{Object.entries(statusLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
      <select aria-label="Lọc mức ưu tiên" value={priority} onChange={event => { setPriority(event.target.value); setPage(1) }}><option value="ALL">Mức ưu tiên</option>{Object.entries(priorityLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
      <select aria-label="Lọc người phụ trách" value={assignee} onChange={event => { setAssignee(event.target.value); setPage(1) }}><option value="ALL">Người phụ trách</option>{assignees.map(name => <option key={name}>{name}</option>)}</select>
    </div>
    <div className="table-scroll"><table><thead><tr><th>Mã ticket</th><th>Tiêu đề</th><th>Người gửi</th><th>Ưu tiên</th><th>Trạng thái</th><th>Cập nhật</th></tr></thead><tbody>
      {loading ? Array.from({ length: 7 }, (_, index) => <tr key={index}>{Array.from({ length: 6 }, (_, cell) => <td key={cell}><span className="skeleton" /></td>)}</tr>)
        : filtered.length ? filtered.slice(start, start + PAGE_SIZE).map(ticket => <tr key={ticket.id}>
          <td><button className="ticket-id ticket-id-button" onClick={() => onSelect(ticket)}>{ticket.id}</button></td>
          <td className="ticket-title"><button className="ticket-open-link" onClick={() => onSelect(ticket)}>{ticket.title}</button></td><td>{ticket.customerName}</td>
          <td><span className={`priority priority-${ticket.priority.toLowerCase()}`}>{priorityLabels[ticket.priority]}</span></td><td><span className={`status status-${ticket.status.toLowerCase()}`}>{statusLabels[ticket.status]}</span></td><td>{new Date(ticket.createdAt).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })}</td>
        </tr>) : <tr><td colSpan={6} className="empty-state">Không tìm thấy ticket phù hợp.</td></tr>}
    </tbody></table></div>
    <div className="table-footer"><span>Hiển thị {filtered.length ? start + 1 : 0}–{Math.min(start + PAGE_SIZE, filtered.length)} trên {filtered.length} ticket</span><div className="pagination"><button aria-label="Trang trước" disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)}>‹</button><span>{currentPage} / {pageCount}</span><button aria-label="Trang sau" disabled={currentPage === pageCount} onClick={() => setPage(currentPage + 1)}>›</button></div></div>
  </section>
}
