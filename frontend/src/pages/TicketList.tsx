import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import TicketLiveFeedTable from '../components/TicketLiveFeedTable'
import type { Ticket, TicketPriority, TicketStatus } from '../types/ticket'

interface TicketListProps {
  tickets: Ticket[]
  loading: boolean
  onCreate: (ticket: Omit<Ticket, 'id' | 'createdAt' | 'responseTimeMinutes'>) => void
  onUpdate: (ticket: Ticket) => void
  onDelete: (id: string) => void
}

const priorityLabels: Record<TicketPriority, string> = {
  LOW: 'Thấp', MEDIUM: 'Trung bình', HIGH: 'Cao', URGENT: 'Khẩn cấp',
}

export default function TicketList({ tickets, loading, onCreate, onUpdate, onDelete }: TicketListProps) {
  const [creating, setCreating] = useState(false)
  const [active, setActive] = useState<Ticket | null>(null)
  const [title, setTitle] = useState('')
  const [customerName, setCustomerName] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState<TicketPriority>('MEDIUM')
  const [formError, setFormError] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)

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

  function changeStatus(status: TicketStatus) {
    if (!active) return
    const updated = { ...active, status }
    onUpdate(updated)
    setActive(updated)
  }

  return (
    <>
      <div className="page-title-row">
        <div><h1>Danh sách ticket</h1><p className="subtitle">Quản lý, phân loại và theo dõi tiến độ các yêu cầu hỗ trợ.</p></div>
        <button className="primary-button" onClick={() => setCreating(true)}>＋ Tạo ticket</button>
      </div>
      <div className="ticket-summary-row">
        <div><span>Tổng ticket</span><strong>{tickets.length}</strong></div>
        <div><span>Đang xử lý</span><strong>{tickets.filter(t => t.status === 'PROCESSING').length}</strong></div>
        <div><span>Đã giải quyết</span><strong>{tickets.filter(t => t.status === 'AI_SOLVED').length}</strong></div>
        <div><span>Chuyển cấp</span><strong>{tickets.filter(t => t.status === 'ESCALATED').length}</strong></div>
      </div>
      <TicketLiveFeedTable tickets={sortedTickets} loading={loading} onSelect={setActive} />

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

      {active && <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) { setActive(null); setConfirmDelete(false) } }}>
        <section className="dialog-card ticket-detail" role="dialog" aria-modal="true" aria-labelledby="ticket-detail-title">
          <div className="dialog-heading"><div><span className="dialog-kicker">CHI TIẾT TICKET · {active.id}</span><h2 id="ticket-detail-title">{active.title}</h2></div><button className="icon-close" onClick={() => { setActive(null); setConfirmDelete(false) }} aria-label="Đóng">×</button></div>
          <div className="detail-grid"><div><small>Khách hàng</small><strong>{active.customerName}</strong></div><div><small>Mức ưu tiên</small><strong>{priorityLabels[active.priority]}</strong></div><div><small>Người phụ trách</small><strong>{active.assignee || 'Chưa phân công'}</strong></div><div><small>Ngày tạo</small><strong>{new Date(active.createdAt).toLocaleString('vi-VN')}</strong></div></div>
          <div className="detail-section"><label className="field-label">Trạng thái xử lý<select value={active.status} onChange={e => changeStatus(e.target.value as TicketStatus)}><option value="PROCESSING">Đang xử lý</option><option value="AI_SOLVED">Đã giải quyết</option><option value="ESCALATED">Chuyển cấp</option></select></label></div>
          <div className="detail-section"><h3>Mô tả vấn đề</h3><p>{active.description || 'Chưa có mô tả cho ticket này.'}</p></div>
          {confirmDelete ? <div className="delete-confirm"><span>Bạn chắc chắn muốn xóa ticket {active.id}?</span><button className="danger-button" onClick={() => { onDelete(active.id); setActive(null); setConfirmDelete(false) }}>Xác nhận xóa</button><button className="secondary-button" onClick={() => setConfirmDelete(false)}>Không</button></div> : <div className="form-actions"><button className="danger-ghost" onClick={() => setConfirmDelete(true)}>Xóa ticket</button><button className="primary-button" onClick={() => setActive(null)}>Hoàn tất</button></div>}
          <p className="local-data-note">Các thay đổi hiện được lưu trên trình duyệt này. Cần kết nối API Backend để đồng bộ nhiều thiết bị.</p>
        </section>
      </div>}
    </>
  )
}
