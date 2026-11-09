import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { Ticket, TicketPriority, TicketStatus } from '../types/ticket'
import { isHazardStatus, isResolvedStatus } from '../types/ticket'

const statusLabels: Record<TicketStatus, string> = {
  PENDING_REVIEW: 'Chờ duyệt',
  PROCESSING: 'Đang xử lý',
  HAZARD_ESCALATED: 'Cảnh báo khẩn cấp',
  RESOLVED: 'Đã giải quyết',
  AI_SOLVED: 'Đã giải quyết',
  ESCALATED: 'Cảnh báo khẩn cấp',
}
const priorityLabels: Record<TicketPriority, string> = { LOW: 'Thấp', MEDIUM: 'Trung bình', HIGH: 'Cao', URGENT: 'Khẩn cấp' }
const PAGE_SIZE = 7

function getStatusLabel(status: TicketStatus) {
  return statusLabels[status]
}
function getStatusClass(status: TicketStatus) {
  if (isResolvedStatus(status)) return 'resolved'
  if (isHazardStatus(status)) return 'hazard'
  return status === 'PENDING_REVIEW' ? 'pending' : 'processing'
}

export default function TicketLiveFeedTable({ tickets, loading, onSelect }: { tickets: Ticket[]; loading: boolean; onSelect: (ticket: Ticket) => void }) {
  const [params, setParams] = useSearchParams()
  const keyword = params.get('search') ?? ''
  const [status, setStatus] = useState('ALL')
  const [priority, setPriority] = useState('ALL')
  const [device, setDevice] = useState('ALL')
  const [page, setPage] = useState(1)

  const filtered = useMemo(() => tickets.filter(ticket => {
    const text = `${ticket.id} ${ticket.title} ${ticket.customerName} ${ticket.device}`.toLocaleLowerCase('vi')
    const matchesStatus = status === 'ALL' || (status === 'RESOLVED' ? isResolvedStatus(ticket.status) : status === 'HAZARD_ESCALATED' ? isHazardStatus(ticket.status) : ticket.status === status)
    return text.includes(keyword.trim().toLocaleLowerCase('vi'))
      && matchesStatus
      && (priority === 'ALL' || ticket.priority === priority)
      && (device === 'ALL' || ticket.device === device)
  }), [tickets, keyword, status, priority, device])

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const currentPage = Math.min(page, pageCount)
  const start = (currentPage - 1) * PAGE_SIZE
  const devices = [...new Set(tickets.map(ticket => ticket.device).filter(Boolean))]

  return <section className="ticket-feed" aria-label="Danh sách ticket">
    <div className="table-toolbar">
      <label className="search-box"><span aria-hidden="true">⌕</span><input aria-label="Tìm kiếm ticket" placeholder="Tìm theo mã case hoặc tiêu đề..." value={keyword} onChange={event => {
        setPage(1)
        setParams(current => {
          const next = new URLSearchParams(current)
          if (event.target.value) next.set('search', event.target.value)
          else next.delete('search')
          return next
        }, { replace: true })
      }} /></label>
      <select aria-label="Lọc trạng thái" value={status} onChange={event => { setStatus(event.target.value); setPage(1) }}>
        <option value="ALL">Tất cả trạng thái</option>
        <option value="PENDING_REVIEW">Chờ duyệt</option>
        <option value="PROCESSING">Đang xử lý</option>
        <option value="HAZARD_ESCALATED">Cảnh báo khẩn cấp</option>
        <option value="RESOLVED">Đã giải quyết</option>
      </select>
      <select aria-label="Lọc mức ưu tiên" value={priority} onChange={event => { setPriority(event.target.value); setPage(1) }}>
        <option value="ALL">Tất cả mức ưu tiên</option>
        {Object.entries(priorityLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
      </select>
      <select aria-label="Lọc thiết bị" value={device} onChange={event => { setDevice(event.target.value); setPage(1) }}>
        <option value="ALL">Tất cả thiết bị</option>
        {devices.map(item => <option key={item} value={item}>{item}</option>)}
      </select>
    </div>

    <div className="table-scroll">
      <table className="crm22-ticket-table">
        <thead><tr><th>Mã case</th><th>Tiêu đề</th><th>Thiết bị</th><th>Nhãn an toàn</th><th>Trạng thái</th></tr></thead>
        <tbody>
          {loading
            ? Array.from({ length: 5 }, (_, index) => <tr key={index}>{Array.from({ length: 5 }, (_, cell) => <td key={cell}><span className="skeleton" /></td>)}</tr>)
            : filtered.length
              ? filtered.slice(start, start + PAGE_SIZE).map(ticket => <tr key={ticket.id}>
                <td><button className="ticket-id ticket-id-button" onClick={() => onSelect(ticket)}>{ticket.id}</button></td>
                <td className="ticket-title"><button className="ticket-open-link" onClick={() => onSelect(ticket)}>{ticket.title}</button><small className="crm22-customer">{ticket.customerName}</small></td>
                <td>{ticket.device || 'Chưa xác định'}</td>
                <td>{ticket.safetyLabel ? <span className="crm22-safety yes">⚠ Có cảnh báo</span> : <span className="crm22-safety no">Không</span>}</td>
                <td><span className={`status status-${getStatusClass(ticket.status)}`}>{getStatusLabel(ticket.status)}</span></td>
              </tr>)
              : <tr><td colSpan={5} className="empty-state">Không tìm thấy ticket phù hợp.</td></tr>}
        </tbody>
      </table>
    </div>

    <div className="table-footer">
      <span>Hiển thị {filtered.length ? start + 1 : 0}–{Math.min(start + PAGE_SIZE, filtered.length)} trên {filtered.length} ticket</span>
      <div className="pagination"><button aria-label="Trang trước" disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)}>‹</button><span>{currentPage} / {pageCount}</span><button aria-label="Trang sau" disabled={currentPage === pageCount} onClick={() => setPage(currentPage + 1)}>›</button></div>
    </div>
  </section>
}
