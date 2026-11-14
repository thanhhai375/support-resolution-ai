import { useEffect, useMemo, useState } from 'react'
import { getTicketOptions } from '../services/ticketService'
import type { TicketOption } from '../services/ticketService'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import TicketLiveFeedTable from '../components/TicketLiveFeedTable'
import type { Ticket, TicketPriority } from '../types/ticket'
import type { CreateTicketInput } from '../services/ticketService'

interface TicketListProps {
  tickets: Ticket[]
  loading: boolean
  onCreate: (ticket: CreateTicketInput) => Promise<void>
}

export default function TicketList({ tickets, loading, onCreate }: TicketListProps) {
  const [creating, setCreating] = useState(false)
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [customerName, setCustomerName] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState<TicketPriority>('MEDIUM')
  const [isHazardEscalated, setIsHazardEscalated] = useState(false)
  const [hazardReason, setHazardReason] = useState('')
  const [formError, setFormError] = useState('')
  const [products, setProducts] = useState<TicketOption[]>([])
  const [categories, setCategories] = useState<TicketOption[]>([])
  const [productId, setProductId] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [optionsLoading, setOptionsLoading] = useState(false)
useEffect(() => {
  let active = true

  async function loadOptions() {
    setOptionsLoading(true)

    try {
      const result = await getTicketOptions()

      if (active) {
        setProducts(result.products)
        setCategories(result.categories)
      }
    } catch (error) {
      console.error('Không tải được sản phẩm và danh mục:', error)
      if (active) {
        setFormError('Không tải được danh sách sản phẩm và danh mục.')
      }
    } finally {
      if (active) setOptionsLoading(false)
    }
  }

  void loadOptions()

  return () => {
    active = false
  }
}, [])

  const sortedTickets = useMemo(() => [...tickets].sort((a, b) => b.createdAt.localeCompare(a.createdAt)), [tickets])

  function submitCreate(event: FormEvent<HTMLFormElement>) {
  event.preventDefault()

  if (!title.trim() || !customerName.trim()) {
    setFormError('Vui lòng nhập tiêu đề và tên khách hàng.')
    return
  }

  if (!productId || !categoryId) {
    setFormError('Vui lòng chọn sản phẩm và danh mục.')
    return
  }

  onCreate({
  title: title.trim(),
  customerName: customerName.trim(),
  description: description.trim(),
  priority,
  productId,
  categoryId,
  isHazardEscalated,
  hazardReason: hazardReason.trim(),
})

  setTitle('')
  setCustomerName('')
  setDescription('')
  setPriority('MEDIUM')
  setProductId('')
  setCategoryId('')
  setIsHazardEscalated(false)
  setHazardReason('')
  setFormError('')
  setCreating(false)
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
          <label className="field-label">
            Sản phẩm
            <select
              value={productId}
              onChange={e => setProductId(e.target.value)}
              required
              disabled={optionsLoading}
            >
              <option value="">-- Chọn sản phẩm --</option>
              {products.map(product => (
                <option key={product.id} value={product.id}>
                  {product.name}
                </option>
              ))}
            </select>
          </label>

          <label className="field-label">
            Danh mục yêu cầu
            <select
              value={categoryId}
              onChange={e => setCategoryId(e.target.value)}
              required
              disabled={optionsLoading}
            >
              <option value="">-- Chọn danh mục --</option>
              {categories.map(category => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field-label">Mức độ ưu tiên<select value={priority} onChange={e => setPriority(e.target.value as TicketPriority)}><option value="LOW">Thấp</option><option value="MEDIUM">Trung bình</option><option value="HIGH">Cao</option><option value="URGENT">Khẩn cấp</option></select></label>
          <label className="field-label">Mô tả<textarea value={description} onChange={e => setDescription(e.target.value)} placeholder="Mô tả vấn đề khách hàng đang gặp..." rows={3} /></label>
          <label className="field-label">
                Nhãn an toàn
                <select
                  value={isHazardEscalated ? 'true' : 'false'}
                  onChange={e => {
                    const checked = e.target.value === 'true'
                    setIsHazardEscalated(checked)
                    if (!checked) setHazardReason('')
                  }}
                >
                  <option value="false">Không có cảnh báo</option>
                  <option value="true">Có cảnh báo</option>
                </select>
              </label>

              {isHazardEscalated && (
                <label className="field-label">
                  Lý do cảnh báo an toàn
                  <textarea
                    value={hazardReason}
                    onChange={e => setHazardReason(e.target.value)}
                    placeholder="Ví dụ: Động cơ có dấu hiệu quá nhiệt..."
                    rows={2}
                    required
                  />
                </label>
              )}
          {formError && <p className="form-error" role="alert">{formError}</p>}
          <div className="form-actions"><button type="button" className="secondary-button" onClick={() => setCreating(false)}>Hủy</button><button className="primary-button" type="submit">Tạo ticket</button></div>
        </form>
      </div>}
    </>
  )
}
