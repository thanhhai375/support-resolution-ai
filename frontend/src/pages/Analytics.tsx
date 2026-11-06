import StatCard from '../components/StatCard'
import TicketTrend from '../components/TicketTrend'
import { useTickets } from '../context/TicketsProvider'

export default function Analytics() {
  const { metrics, tickets, loading } = useTickets()
  const categories = [
    { label: 'Tài khoản', match: /tài khoản|đăng nhập|mật khẩu/i },
    { label: 'Thanh toán', match: /thanh toán|đơn hàng/i },
    { label: 'Kỹ thuật', match: /lỗi|email/i },
  ]
  const counts = categories.map(category => ({ label: category.label, count: tickets.filter(ticket => category.match.test(ticket.title)).length }))
  const value = (text: string) => loading ? '—' : text
  return <>
    <div className="page-title-row"><div><h1>Phân tích hiệu suất hỗ trợ</h1><p className="subtitle">Đo lường chất lượng xử lý ticket và mức độ hỗ trợ của AI.</p></div><span className="date-filter">Dữ liệu hiện tại</span></div>
    <div className="stats-grid dashboard-stats">
      <StatCard label="Tổng ticket" value={value(metrics.total.toLocaleString('vi-VN'))} helper="Tất cả yêu cầu đã ghi nhận" icon="" tone="blue" />
      <StatCard label="Tỷ lệ giải quyết" value={value(`${metrics.resolutionRate}%`)} helper="Ticket đã giải quyết / tổng ticket" icon="" tone="green" />
      <StatCard label="Phản hồi trung bình" value={value(`${metrics.averageResponse} phút`)} helper="Tính từ ticket có dữ liệu phản hồi" icon="" tone="purple" />
      <StatCard label="Ticket AI giải quyết" value={value(String(metrics.solved))} helper="Ticket được đánh dấu AI Solved" icon="" tone="orange" />
    </div>
    <div className="analytics-panels"><TicketTrend title="Số lượng ticket theo ngày" /><section className="panel ai-performance"><h2>Hiệu quả hỗ trợ AI</h2><p>Tỷ lệ ticket được AI giải quyết</p><strong>{metrics.resolutionRate}%</strong><progress max={100} value={metrics.resolutionRate} aria-label="Tỷ lệ AI giải quyết" /><p>Ticket giải quyết với hỗ trợ AI</p><b>{metrics.solved} / {metrics.total}</b></section></div>
    <div className="analytics-bottom"><section className="panel category-panel"><h2>Top danh mục yêu cầu</h2>{counts.map(category => <div className="category-row" key={category.label}><span>{category.label}</span><progress max={Math.max(1, metrics.total)} value={category.count} aria-label={category.label} /><b>{metrics.total ? Math.round(category.count / metrics.total * 100) : 0}%</b></div>)}<small>Nhóm theo từ khóa tiêu đề, có thể trùng danh mục.</small></section><section className="insight-panel metric-definitions"><h2>Định nghĩa chỉ số</h2><p>• Tỷ lệ giải quyết = ticket đã giải quyết / tổng ticket.<br />• Phản hồi trung bình tính trên các ticket có thời gian phản hồi.<br />• AI giải quyết: ticket có trạng thái AI Solved.</p></section></div>
  </>
}
