import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { BookOpen, LayoutDashboard, BarChart3, Settings, LogOut, Menu, Search, Ticket as TicketIcon, X } from 'lucide-react'
import { useAuth } from '../auth/AuthProvider'
import { readClaims } from '../auth/token'
import { useTickets } from '../context/TicketsProvider'

const navigation = [
  { to: '/dashboard', label: 'Tổng quan', accessibleLabel: 'Live Dashboard', icon: LayoutDashboard },
  { to: '/tickets', label: 'Danh sách ticket', accessibleLabel: 'Ticket Feed', icon: TicketIcon },
  { to: '/knowledge-base', label: 'Thư viện tài liệu', accessibleLabel: 'Knowledge Base', icon: BookOpen },
  { to: '/analytics', label: 'Báo cáo & Thống kê', accessibleLabel: 'Analytics', icon: BarChart3 },
  { to: '/ai-settings', label: 'AI Settings', accessibleLabel: 'AI Settings', icon: Settings },
]

export default function MainLayout() {
  const { token, signOut } = useAuth()
  const { tickets, errorMessage, dataSource, notice, setNotice } = useTickets()
  const navigate = useNavigate()
  const location = useLocation()
  const userName = readClaims(token)?.name || readClaims(token)?.sub || 'Người dùng'
  const avatar = Array.from(userName)[0].toLocaleUpperCase('vi')
  const [search, setSearch] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const [online, setOnline] = useState(navigator.onLine)
  const [showHelp, setShowHelp] = useState(false)
  const sidebarRef = useRef<HTMLElement>(null)
  const menuButtonRef = useRef<HTMLButtonElement>(null)
  const headingRef = useRef<HTMLDivElement>(null)
  const previousPath = useRef(location.pathname)
  const results = search.trim() ? tickets.filter(ticket =>
    `${ticket.id} ${ticket.title} ${ticket.customerName}`.toLocaleLowerCase('vi')
      .includes(search.trim().toLocaleLowerCase('vi'))).slice(0, 6) : []

  useEffect(() => {
    const update = () => setOnline(navigator.onLine)
    window.addEventListener('online', update)
    window.addEventListener('offline', update)
    return () => { window.removeEventListener('online', update); window.removeEventListener('offline', update) }
  }, [])

  useEffect(() => {
    setMenuOpen(false)
    setSearch('')
    document.title = `${navigation.find(item => item.to === location.pathname)?.label ?? 'Workspace'} | Support AI`
    if (previousPath.current !== location.pathname) {
      headingRef.current?.focus({ preventScroll: true })
      window.scrollTo({ top: 0 })
      previousPath.current = location.pathname
    }
  }, [location.pathname])

  useEffect(() => {
    if (!menuOpen) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    sidebarRef.current?.querySelector<HTMLButtonElement>('.sidebar-close')?.focus()
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setMenuOpen(false)
      if (event.key === 'Tab') {
        const items = sidebarRef.current?.querySelectorAll<HTMLElement>('a, button')
        if (!items?.length) return
        const first = items[0], last = items[items.length - 1]
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
      }
    }
    window.addEventListener('keydown', onKey)
    const desktop = window.matchMedia('(min-width: 721px)')
    const closeOnDesktop = () => { if (desktop.matches) setMenuOpen(false) }
    desktop.addEventListener('change', closeOnDesktop)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', onKey)
      desktop.removeEventListener('change', closeOnDesktop)
      menuButtonRef.current?.focus()
    }
  }, [menuOpen])

  return <div className={`app-shell crm-shell ${menuOpen ? 'menu-open' : ''}`}>
    <a className="skip-link" href="#main-content">Bỏ qua điều hướng</a>
    <header className="topbar">
      <button ref={menuButtonRef} className="mobile-menu-button" onClick={() => setMenuOpen(true)} aria-label="Mở menu điều hướng" aria-controls="main-sidebar" aria-expanded={menuOpen}><Menu size={21} aria-hidden="true" /></button>
      <Link className="brand" to="/dashboard" aria-label="Support AI – Dashboard">SONGNHAT</Link>
      <div className="top-search-wrap">
        <label className="top-search"><Search size={18} aria-hidden="true" /><input value={search} onChange={event => setSearch(event.target.value)} onKeyDown={event => { if (event.key === 'Escape') setSearch('') }} placeholder="Tìm kiếm ticket, người dùng…" aria-label="Tìm kiếm ticket hoặc người dùng" />{search && <button className="search-clear" onClick={() => setSearch('')} aria-label="Xóa tìm kiếm"><X size={16} /></button>}</label>
        {search.trim() && <div className="global-search-results">
          <div className="dropdown-eyebrow">KẾT QUẢ TÌM KIẾM</div>
          {results.length ? results.map(ticket => <button key={ticket.id} className="global-search-result" onClick={() => { navigate(`/tickets?search=${encodeURIComponent(ticket.id)}`); setSearch('') }}>
            <TicketIcon size={18} aria-hidden="true" /><span className="result-copy"><strong>{ticket.title}</strong><small>{ticket.id} · {ticket.customerName}</small></span>
          </button>) : <p className="search-empty">Không tìm thấy ticket phù hợp.</p>}
        </div>}
      </div>
      <div className="top-actions">
        <button className="header-link" onClick={() => setShowHelp(true)}>Trợ giúp</button><span className="header-separator">•</span>
        <span className="system-status" role="status"><span className={`dot ${online ? 'green-dot' : 'red-dot'}`} /><span>{online ? 'Trực tuyến' : 'Ngoại tuyến'}</span></span>
        <span className="user-summary" title={userName}><span className="admin-avatar" aria-hidden="true">{avatar}</span><span className="user-label">{userName}</span></span>
        <button className="logout-button" onClick={signOut} aria-label="Logout"><LogOut size={17} aria-hidden="true" /><span>Logout</span></button>
      </div>
    </header>
    {menuOpen && <div className="sidebar-backdrop" onClick={() => setMenuOpen(false)} aria-hidden="true" />}
    <aside ref={sidebarRef} id="main-sidebar" className="sidebar" aria-label="Workspace" role={menuOpen ? 'dialog' : undefined} aria-modal={menuOpen ? true : undefined}>
      <div className="sidebar-heading"><Link className="workspace-brand" to="/dashboard"><b>SN</b><span>SONGNHAT<small>Support Resolution AI</small></span></Link><button className="sidebar-close" onClick={() => setMenuOpen(false)} aria-label="Đóng menu"><X size={20} aria-hidden="true" /></button></div>
      <nav className="navigation" aria-label="Điều hướng chính">
        {navigation.map(({ to, label, accessibleLabel, icon: Icon }) => <NavLink key={to} to={to} aria-label={accessibleLabel} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} onClick={() => setMenuOpen(false)}><Icon size={16} aria-hidden="true" />{label}</NavLink>)}
      </nav>
      <div className="sidebar-staff"><span className="staff-avatar">{avatar}</span><div><strong>{userName}</strong><small>Support Agent</small></div></div>
    </aside>
    {notice && <div className="toast-notice" role="status">{notice}<button onClick={() => setNotice('')} aria-label="Đóng thông báo">×</button></div>}
    {showHelp && <div className="modal-backdrop"><section className="dialog-card" role="dialog" aria-modal="true" aria-labelledby="help-title"><h2 id="help-title">Trung tâm trợ giúp</h2><p className="subtitle">Chọn Tổng quan để theo dõi hoạt động. Danh sách ticket cho phép tìm kiếm, lọc và mở chi tiết yêu cầu. Phân tích dữ liệu hiển thị các chỉ số hỗ trợ.</p><button autoFocus className="primary-button dialog-action" onClick={() => setShowHelp(false)}>Đóng</button></section></div>}
    <main id="main-content" className="main-content" tabIndex={-1}>
      <div className="page-content">
        <div ref={headingRef} tabIndex={-1} className="route-content"><Outlet /></div>
        <footer className="page-footer"><span>© 2026 SUPPORT AI</span><span title={errorMessage}>Nguồn dữ liệu: {dataSource === 'api' ? 'Backend API' : 'Dữ liệu minh họa'}</span></footer>
      </div>
    </main>
  </div>
}
