
import { useEffect, useMemo, useState } from 'react'
import StatCard from './components/StatCard'
import Dashboard from './pages/Dashboard'
import TicketList from './pages/TicketList'
import { getTickets } from './services/ticketService'
import type { Ticket } from './types/ticket'

type Page = 'dashboard' | 'tickets' | 'analytics'

function isTicket(value: unknown): value is Ticket {
  if (typeof value !== 'object' || value === null) return false
  const ticket = value as Record<string, unknown>
  return typeof ticket.id === 'string'
    && typeof ticket.title === 'string'
    && typeof ticket.customerName === 'string'
    && (ticket.status === 'AI_SOLVED' || ticket.status === 'PROCESSING' || ticket.status === 'ESCALATED')
    && (ticket.priority === 'LOW' || ticket.priority === 'MEDIUM' || ticket.priority === 'HIGH' || ticket.priority === 'URGENT')
    && typeof ticket.createdAt === 'string'
    && (ticket.responseTimeMinutes === null || typeof ticket.responseTimeMinutes === 'number')
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [ticketsReady, setTicketsReady] = useState(false)
  const [loading, setLoading] = useState(true)
  const [dataSource, setDataSource] = useState<'api' | 'mock'>('mock')
  const [page, setPage] = useState<Page>('dashboard')
  const [errorMessage, setErrorMessage] = useState('')
  const [globalSearch, setGlobalSearch] = useState('')
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null)
  const [showHelp, setShowHelp] = useState(false)
  const [showAdminMenu, setShowAdminMenu] = useState(false)
  const [showProfile, setShowProfile] = useState(false)
  const [notice, setNotice] = useState('')

  // Chỉ gọi API tại App.tsx
  useEffect(() => {
    let isMounted = true

    async function loadTickets() {
      setLoading(true)

      try {
        const result = await getTickets()

        if (isMounted) {
          let initialTickets = result.tickets
          // Chỉ khôi phục dữ liệu đã lưu khi đang dùng Mock; API thật luôn là nguồn ưu tiên.
          if (result.source === 'mock') {
            try {
              const saved = localStorage.getItem('support-ai-tickets-v2')
              if (saved) {
                const parsed: unknown = JSON.parse(saved)
                if (Array.isArray(parsed)) initialTickets = parsed.filter(isTicket)
              }
            } catch { /* Bỏ qua dữ liệu local bị lỗi định dạng */ }
          }
          setTickets(initialTickets)
          setTicketsReady(true)
          setDataSource(result.source)

          setErrorMessage(
            result.source === 'mock'
              ? 'Backend chưa kết nối được. Đang hiển thị dữ liệu mẫu để bạn tiếp tục phát triển giao diện.'
              : ''
          )
        }
      } catch {
        if (isMounted) {
          setErrorMessage('Không thể tải dữ liệu ticket.')
          setTicketsReady(true)
        }
      } finally {
        if (isMounted) {
          setLoading(false)
        }
      }
    }

    void loadTickets()

    return () => {
      isMounted = false
    }
  }, [])

  useEffect(() => {
    if (!ticketsReady) return
    try { localStorage.setItem('support-ai-tickets-v2', JSON.stringify(tickets)) }
    catch { setNotice('Không thể lưu dữ liệu trên trình duyệt. Bộ nhớ có thể đã đầy.') }
  }, [tickets, ticketsReady])

  function createTicket(input: Omit<Ticket, 'id' | 'createdAt' | 'responseTimeMinutes'>) {
    const nextNumber = Math.max(1024, ...tickets.map(ticket => Number(ticket.id.replace(/\D/g, '')) || 0)) + 1
    const created: Ticket = { ...input, id: `TK-${nextNumber}`, createdAt: new Date().toISOString(), responseTimeMinutes: null }
    setTickets(current => [created, ...current])
    setNotice(`Đã tạo ticket ${created.id}.`)
  }

  function updateTicket(updated: Ticket) {
    setTickets(current => current.map(ticket => ticket.id === updated.id ? updated : ticket))
    setNotice(`Đã cập nhật ticket ${updated.id}.`)
  }

  function deleteTicket(id: string) {
    setTickets(current => current.filter(ticket => ticket.id !== id))
    setNotice(`Đã xóa ticket ${id}.`)
  }

  // Tính toán các chỉ số Dashboard
  const metrics = useMemo(() => {
    const total = tickets.length

    const solved = tickets.filter(
      (ticket) => ticket.status === 'AI_SOLVED'
    ).length

    const processing = tickets.filter(
      (ticket) => ticket.status === 'PROCESSING'
    ).length

    const escalated = tickets.filter(
      (ticket) => ticket.status === 'ESCALATED'
    ).length

    const responseTimes = tickets
      .map((ticket) => ticket.responseTimeMinutes)
      .filter(
        (value): value is number =>
          value !== null && Number.isFinite(value)
      )

    const averageResponse = responseTimes.length
      ? responseTimes.reduce((sum, value) => sum + value, 0)
        / responseTimes.length
      : 0

    return {
      total,
      solved,
      processing,
      escalated,
      resolutionRate: total
        ? Math.round((solved / total) * 100)
        : 0,
      averageResponse: averageResponse.toFixed(0),
    }
  }, [tickets])

  const nav = (nextPage: Page) => {
    setPage(nextPage)
    setShowAdminMenu(false)
  }

  const searchResults = globalSearch.trim()
    ? tickets.filter((ticket) =>
        `${ticket.id} ${ticket.title} ${ticket.customerName}`
          .toLocaleLowerCase('vi')
          .includes(globalSearch.trim().toLocaleLowerCase('vi'))
      ).slice(0, 6)
    : []

  return (
    <div className="app-shell">
      {/* Header */}
      <header className="topbar">
        <button
          className="brand"
          onClick={() => nav('dashboard')}
          aria-label="Về Dashboard"
        >
          <span>SUPPORT AI</span>
        </button>

        <div className="top-search-wrap">
          <label className="top-search">
            <span aria-hidden="true">⌕</span>
            <input
              value={globalSearch}
              onChange={(event) => setGlobalSearch(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Escape') setGlobalSearch('')
                if (event.key === 'Enter' && searchResults[0]) setSelectedTicket(searchResults[0])
              }}
              placeholder="Tìm kiếm ticket, người dùng..."
              aria-label="Tìm kiếm ticket hoặc người dùng"
            />
            {globalSearch && <button className="search-clear" onClick={() => setGlobalSearch('')} aria-label="Xóa tìm kiếm">×</button>}
          </label>
          {globalSearch.trim() && (
            <div className="global-search-results">
              <div className="dropdown-eyebrow">KẾT QUẢ TÌM KIẾM</div>
              {searchResults.length ? searchResults.map((ticket) => (
                <button key={ticket.id} className="global-search-result" onClick={() => { setSelectedTicket(ticket); setGlobalSearch('') }}>
                  <span className="result-icon">▤</span>
                  <span className="result-copy"><strong>{ticket.title}</strong><small>{ticket.id} · {ticket.customerName}</small></span>
                  <span className={`result-status status-${ticket.status.toLowerCase()}`}>{ticket.status === 'AI_SOLVED' ? 'Đã xử lý' : ticket.status === 'PROCESSING' ? 'Đang xử lý' : 'Chuyển cấp'}</span>
                </button>
              )) : <p className="search-empty">Không tìm thấy ticket phù hợp.</p>}
            </div>
          )}
        </div>

        <div className="top-actions">
          <button className="header-link" onClick={() => setShowHelp(true)}>Trợ giúp</button>
          <span className="header-separator">•</span>
          <div className="admin-menu-wrap">
            <button className={`admin-trigger ${showAdminMenu ? 'is-open' : ''}`} onClick={() => setShowAdminMenu((value) => !value)} aria-expanded={showAdminMenu}>
              <span className="admin-avatar">A</span><span>Admin</span><span className="chevron">⌄</span>
            </button>
            {showAdminMenu && <div className="admin-dropdown">
              <div className="admin-summary"><span className="admin-avatar large">A</span><span><strong>Quản trị viên</strong><small>admin@supportai.vn</small></span></div>
              <button onClick={() => { setShowProfile(true); setShowAdminMenu(false) }}>Thông tin tài khoản</button>
              <button onClick={() => { setNotice('Cài đặt hệ thống sẽ được kết nối với Backend trong phiên bản tiếp theo.'); setShowAdminMenu(false) }}>Cài đặt hệ thống</button>
            </div>}
          </div>
        </div>
      </header>

      {/* Sidebar */}
      <aside className="sidebar">
        <p className="nav-caption">WORKSPACE</p>

        <nav className="navigation" aria-label="Điều hướng chính">
          <button
            className={`nav-item ${page === 'dashboard' ? 'active' : ''}`}
            onClick={() => nav('dashboard')}
          >
            <span>◉</span> Tổng quan
          </button>

          <button
            className={`nav-item ${page === 'tickets' ? 'active' : ''}`}
            onClick={() => nav('tickets')}
          >
            <span>▤</span> Danh sách ticket
          </button>

          <button
            className={`nav-item ${page === 'analytics' ? 'active' : ''}`}
            onClick={() => nav('analytics')}
          >
            <span>◷</span> Phân tích dữ liệu
          </button>
        </nav>

        <div className="sidebar-note">
          <strong>AI ASSISTANT</strong>
          <p>
            Phân loại yêu cầu và gợi ý phản hồi tự động.
          </p>
        </div>
      </aside>

      {notice && <div className="toast-notice" role="status">{notice}<button onClick={() => setNotice('')} aria-label="Đóng thông báo">×</button></div>}

      {selectedTicket && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelectedTicket(null) }}>
        <section className="dialog-card" role="dialog" aria-modal="true" aria-labelledby="ticket-dialog-title">
          <div className="dialog-heading"><div><span className="dialog-kicker">CHI TIẾT TICKET · {selectedTicket.id}</span><h2 id="ticket-dialog-title">{selectedTicket.title}</h2></div><button className="icon-close" onClick={() => setSelectedTicket(null)} aria-label="Đóng">×</button></div>
          <div className="detail-grid"><div><small>Khách hàng</small><strong>{selectedTicket.customerName}</strong></div><div><small>Trạng thái</small><strong>{selectedTicket.status === 'AI_SOLVED' ? 'Đã giải quyết' : selectedTicket.status === 'PROCESSING' ? 'Đang xử lý' : 'Chuyển cấp'}</strong></div><div><small>Mức độ ưu tiên</small><strong>{selectedTicket.priority}</strong></div><div><small>Thời gian phản hồi</small><strong>{selectedTicket.responseTimeMinutes == null ? 'Chưa có dữ liệu' : `${selectedTicket.responseTimeMinutes} phút`}</strong></div></div>
          <button className="primary-button dialog-action" onClick={() => { setSelectedTicket(null); nav('tickets') }}>Mở danh sách ticket</button>
        </section>
      </div>}

      {showHelp && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setShowHelp(false) }}><section className="dialog-card" role="dialog" aria-modal="true" aria-labelledby="help-title"><div className="dialog-heading"><div><span className="dialog-kicker">SUPPORT AI · TRUNG TÂM TRỢ GIÚP</span><h2 id="help-title">Bạn cần hỗ trợ?</h2></div><button className="icon-close" onClick={() => setShowHelp(false)} aria-label="Đóng">×</button></div><div className="help-list"><div><strong>⌕ Tìm kiếm ticket</strong><p>Nhập mã ticket, tiêu đề hoặc tên khách hàng vào thanh tìm kiếm phía trên.</p></div><div><strong>▤ Quản lý ticket</strong><p>Chọn “Danh sách ticket” ở thanh điều hướng để xem và lọc các yêu cầu hỗ trợ.</p></div><div><strong>◷ Theo dõi hiệu quả</strong><p>Trang tổng quan và phân tích giúp bạn theo dõi trạng thái và hiệu suất xử lý.</p></div></div><button className="primary-button dialog-action" onClick={() => setShowHelp(false)}>Đã hiểu</button></section></div>}

      {showProfile && <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setShowProfile(false) }}><section className="dialog-card profile-dialog" role="dialog" aria-modal="true" aria-labelledby="profile-title"><div className="dialog-heading"><div><span className="dialog-kicker">TÀI KHOẢN</span><h2 id="profile-title">Thông tin quản trị viên</h2></div><button className="icon-close" onClick={() => setShowProfile(false)} aria-label="Đóng">×</button></div><div className="profile-avatar">A</div><strong className="profile-name">Quản trị viên</strong><span className="profile-email">admin@supportai.vn</span><p className="profile-note">Tài khoản quản trị giao diện Support AI.</p><button className="primary-button dialog-action" onClick={() => setShowProfile(false)}>Đóng</button></section></div>}

      {/* Main content */}
      <main className="main-content">
        <div className="page-content">
          {errorMessage && (
            <div className="notice" role="status">
              {errorMessage}
            </div>
          )}

          {/* Dashboard page */}
          {page === 'dashboard' && (
            <Dashboard
              metrics={metrics}
              loading={loading}
            />
          )}

          {/* Ticket List page */}
          {page === 'tickets' && (
            <TicketList
              tickets={tickets}
              loading={loading}
              onCreate={createTicket}
              onUpdate={updateTicket}
              onDelete={deleteTicket}
            />
          )}

          {/* Analytics page - tạm thời giữ tại App */}
          {page === 'analytics' && (
            <>
              <div className="page-title-row">
                <div>
                  <h1>Phân tích dữ liệu</h1>
                  <p className="subtitle">
                    Theo dõi hiệu quả xử lý yêu cầu hỗ trợ.
                  </p>
                </div>

                <span className="date-filter">
                  30 ngày gần nhất
                </span>
              </div>

              <div className="stats-grid">
                <StatCard
                  label="Tổng số ticket"
                  value={loading ? '—' : String(metrics.total)}
                  helper="Tất cả yêu cầu"
                  icon="▤"
                  tone="blue"
                />

                <StatCard
                  label="AI Resolution Rate"
                  value={loading ? '—' : `${metrics.resolutionRate}%`}
                  helper="AI tự động giải quyết"
                  icon="✦"
                  tone="green"
                />

                <StatCard
                  label="Phản hồi trung bình"
                  value={loading ? '—' : `${metrics.averageResponse} phút`}
                  helper="Thời gian phản hồi"
                  icon="◷"
                  tone="purple"
                />
              </div>

              <section className="panel">
                <h2>Trạng thái ticket</h2>

                <p className="analytics-copy">
                  Đã giải quyết: {metrics.solved}
                  {' · '}
                  Đang xử lý: {metrics.processing}
                  {' · '}
                  Escalated: {metrics.escalated}
                </p>
              </section>
            </>
          )}

          {/* Footer */}
          <footer className="page-footer">
            <span>© 2026 SUPPORT AI</span>

            <span>
              Nguồn dữ liệu:{' '}
              {dataSource === 'api' ? 'Backend API' : 'Mock data'}
            </span>
          </footer>
        </div>
      </main>
    </div>
  )
}
