import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { getTickets } from '../services/ticketService'
import type { Ticket } from '../types/ticket'

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


function useTicketState() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [ticketsReady, setTicketsReady] = useState(false)
  const [loading, setLoading] = useState(true)
  const [dataSource, setDataSource] = useState<'api' | 'mock'>('mock')
  const [errorMessage, setErrorMessage] = useState('')
  const [notice, setNotice] = useState('')

  // Keep ticket state alive while navigating within the protected workspace.
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


  return { tickets, loading, dataSource, errorMessage, metrics, createTicket, updateTicket, deleteTicket, notice, setNotice }
}
const TicketsContext = createContext<ReturnType<typeof useTicketState> | null>(null)
export function TicketsProvider({ children }: { children: ReactNode }) {
  const value = useTicketState()
  return <TicketsContext.Provider value={value}>{children}</TicketsContext.Provider>
}
export function useTickets() {
  const context = useContext(TicketsContext)
  if (!context) throw new Error('useTickets requires TicketsProvider')
  return context
}
