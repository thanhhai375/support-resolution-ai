import { useTickets } from '../context/TicketsProvider'

export default function TicketTrend({ title = 'Xu hướng ticket theo thời gian' }: { title?: string }) {
  const { tickets } = useTickets()
  const dates = tickets.map(ticket => new Date(ticket.createdAt).getTime()).filter(Number.isFinite)
  const latest = dates.length ? Math.max(...dates) : Date.now()
  const end = new Date(latest)
  end.setHours(0, 0, 0, 0)
  const days = Array.from({ length: 8 }, (_, index) => {
    const day = new Date(end)
    day.setDate(day.getDate() - (7 - index))
    const next = new Date(day)
    next.setDate(next.getDate() + 1)
    return { label: day.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' }), count: dates.filter(date => date >= day.getTime() && date < next.getTime()).length }
  })
  const max = Math.max(1, ...days.map(day => day.count))
  return <section className="panel trend-panel"><h2>{title}</h2><p className="legend"><i /> Ticket tiếp nhận</p>
    <div className="chart-area" role="img" aria-label={`Ticket theo ngày: ${days.map(day => `${day.label}: ${day.count}`).join(', ')}`}>
      {days.map(day => <div className="chart-column" key={day.label}><span title={`${day.label}: ${day.count} ticket`} style={{ height: `${day.count / max * 85}%`, minHeight: day.count ? 4 : 0 }} /><small>{day.label}</small></div>)}
    </div>
  </section>
}
