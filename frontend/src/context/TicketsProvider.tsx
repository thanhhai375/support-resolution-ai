import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { createTicket as createTicketApi, getTickets } from '../services/ticketService'
import type { CreateTicketInput } from '../services/ticketService'
import type { Ticket } from '../types/ticket'
import { isHazardStatus, isResolvedStatus } from '../types/ticket'

function isTicket(value: unknown): value is Ticket {
  if (typeof value !== 'object' || value === null) return false
  const ticket = value as Record<string, unknown>
  return typeof ticket.id === 'string'
    && typeof ticket.title === 'string'
    && typeof ticket.customerName === 'string'
    && (['PENDING_REVIEW', 'PROCESSING', 'HAZARD_ESCALATED', 'RESOLVED', 'AI_SOLVED', 'ESCALATED'] as string[]).includes(String(ticket.status))
    && (ticket.priority === 'LOW' || ticket.priority === 'MEDIUM' || ticket.priority === 'HIGH' || ticket.priority === 'URGENT')
    && typeof ticket.createdAt === 'string'
    && (ticket.device === undefined || typeof ticket.device === 'string')
    && (ticket.safetyLabel === undefined || typeof ticket.safetyLabel === 'boolean')
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
                if (Array.isArray(parsed)) initialTickets = parsed.filter(isTicket).map(ticket => ({ ...ticket, device: ticket.device ?? 'Chưa xác định', safetyLabel: ticket.safetyLabel ?? false }))
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

  async function createTicket(input: CreateTicketInput) {
  try {
    setErrorMessage('')

    const created = await createTicketApi(input)

    setTickets(current => [created, ...current])
    setNotice(`Đã tạo ticket ${created.id} thành công.`)
  } catch (error) {
    const message = error instanceof Error
      ? error.message
      : 'Không thể tạo ticket.'

    setErrorMessage(message)
    console.error('Lỗi tạo ticket:', error)
  }
}

  function updateTicket(updated: Ticket) {
    setTickets(current => current.map(ticket => ticket.id === updated.id ? updated : ticket))
    setNotice(`Đã cập nhật ticket ${updated.id}.`)
  }

  function deleteTicket(id: string) {
    setTickets(current => current.filter(ticket => ticket.id !== id))
    setNotice(`Đã xóa ticket ${id}.`)
  }

  // Các chỉ số bám sát yêu cầu Jira CRM-22.
  const metrics = useMemo(() => {
    const total = tickets.length
    const pendingReview = tickets.filter(ticket => ticket.status === 'PENDING_REVIEW').length
    const hazardEscalated = tickets.filter(ticket => isHazardStatus(ticket.status)).length
    const resolved = tickets.filter(ticket => isResolvedStatus(ticket.status)).length

    return {
      total,
      pendingReview,
      hazardEscalated,
      resolved,
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
