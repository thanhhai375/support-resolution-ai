import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import TicketLiveFeedTable from '../components/TicketLiveFeedTable'
import type { Ticket, TicketPriority } from '../types/ticket'

interface TicketListProps {
  tickets: Ticket[]
  loading: boolean
  onCreate: (ticket: Omit<Ticket, 'id' | 'createdAt' | 'responseTimeMinutes'>) => void
}

export default function TicketList({ tickets, loading, onCreate }: TicketListProps) {
  const [creating, setCreating] = useState(false)
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [customerName, setCustomerName] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState<TicketPriority>('MEDIUM')
  const [formError, setFormError] = useState('')

  const sortedTickets = useMemo(() => [...tickets].sort((a, b) => b.createdAt.localeCompare(a.createdAt)), [tickets])

  function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!title.trim() || !customerName.trim()) {
      setFormError('Vui lòng nhập tiêu đề và tên khách hàng.')
      return
    }
    onCreate({ title: title.trim(), customerName: customerName.trim(), description: description.trim(), priority, status: 'PROCESSING', assignee: 'Chưa phân công' })
    setTitle(''); setCustomerName(''); setDescription(''); setPriority('MEDIUM'); setFormError(''); setCreating(false)
  }

  return (
    <>
      <div className="page-title-row">
        <div><h1>Danh sách ticket</h1><p className="subtitle">Quản lý, phân loại và theo dõi tiến độ các yêu cầu hỗ trợ.</p></div>
        <button className="primary-button" onClick={() => setCreating(true)}>＋ Tạo ticket</button>
      </div>
      <TicketLiveFeedTable tickets={sortedTickets} loading={loading} onSelect={ticket => navigate(`/tickets/${encodeURIComponent(ticket.id)}`)} />

      {creating && <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) setCreating(false) }}>
        <form className="dialog-card ticket-form" onSubmit={submitCreate}>
          <div className="dialog-heading"><div><span className="dialog-kicker">QUẢN LÝ YÊU CẦU</span><h2>Tạo ticket mới</h2></div><button type="button" className="icon-close" onClick={() => setCreating(false)} aria-label="Đóng">×</button></div>
          <label className="field-label">Tiêu đề ticket<input autoFocus value={title} onChange={e => setTitle(e.target.value)} placeholder="Ví dụ: Không thể đăng nhập..." /></label>
          <label className="field-label">Tên khách hàng<input value={customerName} onChange={e => setCustomerName(e.target.value)} placeholder="Nhập tên khách hàng" /></label>
          <label className="field-label">Mức độ ưu tiên<select value={priority} onChange={e => setPriority(e.target.value as TicketPriority)}><option value="LOW">Thấp</option><option value="MEDIUM">Trung bình</option><option value="HIGH">Cao</option><option value="URGENT">Khẩn cấp</option></select></label>
          <label className="field-label">Mô tả<textarea value={description} onChange={e => setDescription(e.target.value)} placeholder="Mô tả vấn đề khách hàng đang gặp..." rows={3} /></label>
          {formError && <p className="form-error" role="alert">{formError}</p>}
          <div className="form-actions"><button type="button" className="secondary-button" onClick={() => setCreating(false)}>Hủy</button><button className="primary-button" type="submit">Tạo ticket</button></div>
        </form>
      </div>}

    </>
  )
}
