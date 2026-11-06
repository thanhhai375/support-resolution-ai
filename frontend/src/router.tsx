import { createBrowserRouter, Link, Navigate, Outlet } from 'react-router-dom'
import type { RouteObject } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import { TicketsProvider, useTickets } from './context/TicketsProvider'
import MainLayout from './layouts/MainLayout'
import Dashboard from './pages/Dashboard'
import TicketList from './pages/TicketList'
import AISettings from './pages/AISettings'
import Analytics from './pages/Analytics'
import Login from './pages/Login'
import TicketDetail from './pages/TicketDetail'
import Register from './pages/Register'

function Workspace() {
  return <TicketsProvider><Outlet /></TicketsProvider>
}

function DashboardRoute() {
  const { metrics, loading } = useTickets()
  return <Dashboard metrics={metrics} loading={loading} />
}

function TicketFeedRoute() {
  const { tickets, loading, createTicket } = useTickets()
  return <TicketList tickets={tickets} loading={loading} onCreate={createTicket} />
}

function NotFound() {
  return <section className="panel"><h1>Không tìm thấy trang</h1><p className="subtitle">Đường dẫn này không tồn tại trong không gian làm việc.</p><Link className="text-link" to="/dashboard">Về Dashboard</Link></section>
}

export const routes: RouteObject[] = [
  { path: '/login', element: <Login /> },
  { path: '/register', element: <Register /> },
  {
    element: <ProtectedRoute />,
    children: [{
      element: <Workspace />,
      children: [{
        element: <MainLayout />,
        children: [
          { index: true, element: <Navigate to="/dashboard" replace /> },
          { path: 'dashboard', element: <DashboardRoute /> },
          { path: 'tickets', element: <TicketFeedRoute /> },
          { path: 'tickets/:ticketId', element: <TicketDetail /> },
          { path: 'ai-settings', element: <AISettings /> },
          { path: 'analytics', element: <Analytics /> },
          { path: '*', element: <NotFound /> },
        ],
      }],
    }],
  },
]

export const router = createBrowserRouter(routes, {
  future: { v7_relativeSplatPath: true },
})
