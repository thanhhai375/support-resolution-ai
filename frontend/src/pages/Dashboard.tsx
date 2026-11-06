import StatCard from '../components/StatCard'
import TicketTrend from '../components/TicketTrend'

export interface DashboardMetrics {
  total: number
  solved: number
  processing: number
  escalated: number
  resolutionRate: number
  averageResponse: string
}

export default function Dashboard({ metrics, loading }: { metrics: DashboardMetrics; loading: boolean }) {
  const value = (number: number) => loading ? '—' : number.toLocaleString('vi-VN')
  return <>
    <div className="page-title-row"><div><h1>Tổng quan hệ thống</h1><p className="subtitle">Theo dõi tình hình tiếp nhận và xử lý yêu cầu hỗ trợ.</p></div><span className="date-filter">Dữ liệu hiện tại</span></div>
    <div className="stats-grid dashboard-stats">
      <StatCard label="Tổng số ticket" value={value(metrics.total)} helper="Tất cả yêu cầu đã ghi nhận" icon="" tone="blue" />
      <StatCard label="Đang xử lý" value={value(metrics.processing)} helper="Ticket đang được tiếp nhận" icon="" tone="orange" />
      <StatCard label="Đã giải quyết" value={value(metrics.solved)} helper={`${metrics.resolutionRate}% tổng ticket`} icon="" tone="green" />
      <StatCard label="Chuyển cấp" value={value(metrics.escalated)} helper="Cần ưu tiên xử lý" icon="" tone="purple" />
    </div>
    <div className="dashboard-panels">
      <TicketTrend />
      <section className="panel status-panel"><h2>Phân bố trạng thái</h2>
        <div className="status-summary"><span className="dot blue-dot" /><span>Đang xử lý</span><b>{value(metrics.processing)}</b></div>
        <div className="status-summary"><span className="dot green-dot" /><span>Đã giải quyết</span><b>{value(metrics.solved)}</b></div>
        <div className="status-summary"><span className="dot red-dot" /><span>Chuyển cấp</span><b>{value(metrics.escalated)}</b></div>
      </section>
    </div>
    <section className="insight-panel"><strong>INSIGHT TỪ AI</strong><p>AI đã giải quyết {metrics.resolutionRate}% số ticket trong dữ liệu hiện tại. Nhân viên có thể ưu tiên các yêu cầu đang chuyển cấp để cải thiện tốc độ hỗ trợ.</p><small>Gợi ý dựa trên dữ liệu ticket đã ghi nhận • Cần nhân viên xác nhận trước khi áp dụng</small></section>
  </>
}
