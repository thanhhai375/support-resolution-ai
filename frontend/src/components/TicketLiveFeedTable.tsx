import { useMemo, useState } from 'react'
import type { Ticket, TicketStatus } from '../types/ticket'

interface TicketLiveFeedTableProps {
  tickets: Ticket[]
  loading: boolean
  onSelect: (ticket: Ticket) => void
}

const statusLabels: Record<TicketStatus, string> = {
  AI_SOLVED: 'AI Solved',
  PROCESSING: 'Processing',
  ESCALATED: 'Escalated',
}

const priorityLabels: Record<Ticket['priority'], string> = {
  LOW: 'Thấp',
  MEDIUM: 'Trung bình',
  HIGH: 'Cao',
  URGENT: 'Khẩn cấp',
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit', month: '2-digit',
    hour: '2-digit', minute: '2-digit',
  }).format(date)
}

export default function TicketLiveFeedTable({ tickets, loading, onSelect }: TicketLiveFeedTableProps) {
  const [keyword, setKeyword] = useState('')
  const [status, setStatus] = useState<'ALL' | TicketStatus>('ALL')

  const filteredTickets = useMemo(() => {
    const normalizedKeyword = keyword.trim().toLocaleLowerCase('vi')
    return tickets.filter((ticket) => {
      const matchesKeyword = ticket.title.toLocaleLowerCase('vi').includes(normalizedKeyword)
      const matchesStatus = status === 'ALL' || ticket.status === status
      return matchesKeyword && matchesStatus
    })
  }, [tickets, keyword, status])

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Ticket Live Feed</h2>
          <p>Theo dõi các yêu cầu hỗ trợ mới nhất</p>
        </div>
        <span className="live-indicator"><i /> Live updates</span>
      </div>

      <div className="table-toolbar">
        <label className="search-box">
          <span aria-hidden="true">⌕</span>
          <input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="Tìm theo tiêu đề ticket..."
            aria-label="Tìm kiếm ticket"
          />
        </label>
        <select
          value={status}
          onChange={(event) => setStatus(event.target.value as 'ALL' | TicketStatus)}
          aria-label="Lọc theo trạng thái"
        >
          <option value="ALL">Tất cả trạng thái</option>
          <option value="AI_SOLVED">AI Solved</option>
          <option value="PROCESSING">Processing</option>
          <option value="ESCALATED">Escalated</option>
        </select>
      </div>

      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Mã ticket</th>
              <th>Tiêu đề</th>
              <th>Người gửi</th>
              <th>Ưu tiên</th>
              <th>Trạng thái</th>
              <th>Thời gian</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 5 }, (_, index) => (
                <tr key={`skeleton-${index}`}>
                  {Array.from({ length: 6 }, (_, cell) => (
                    <td key={cell}><span className="skeleton" /></td>
                  ))}
                </tr>
              ))
            ) : filteredTickets.length > 0 ? (
              filteredTickets.map((ticket) => (
                <tr key={ticket.id} className="ticket-row-clickable" onClick={() => onSelect(ticket)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') onSelect(ticket) }} tabIndex={0} aria-label={`Mở ticket ${ticket.id}`}>
                  <td className="ticket-id">{ticket.id}</td>
                  <td className="ticket-title"><button className="ticket-open-link" onClick={event => { event.stopPropagation(); onSelect(ticket) }}>{ticket.title}</button></td>
                  <td>{ticket.customerName}</td>
                  <td><span className={`priority priority-${ticket.priority.toLowerCase()}`}>{priorityLabels[ticket.priority]}</span></td>
                  <td><span className={`status status-${ticket.status.toLowerCase()}`}>{statusLabels[ticket.status]}</span></td>
                  <td className="date-cell">{formatDate(ticket.createdAt)}</td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={6} className="empty-state">Không tìm thấy ticket phù hợp.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="table-footer">Hiển thị {loading ? '...' : filteredTickets.length} / {tickets.length} ticket</div>
    </section>
  )
}
