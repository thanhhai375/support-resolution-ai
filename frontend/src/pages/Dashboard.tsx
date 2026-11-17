import StatCard from '../components/StatCard'
import TicketTrend from '../components/TicketTrend'

export interface DashboardMetrics {
  total: number
  pendingReview: number
  hazardEscalated: number
  resolved: number
}

export default function Dashboard({ metrics, loading }: { metrics: DashboardMetrics; loading: boolean }) {
  const value = (number: number) => loading ? '—' : number.toLocaleString('vi-VN')
  return <>
<div className="page-title-row">
  <div>
    <p className="dashboard-kicker">
      SONGNHAT COPILOT / TECHNICAL SUPPORT
    </p>

    <h1>Trung tâm hỗ trợ kỹ thuật</h1>

    <p className="subtitle">
      Quản lý yêu cầu hỗ trợ động cơ, biến tần
      và theo dõi an toàn vận hành.
    </p>
  </div>

  <span className="date-filter">
    Tổng quan ticket
  </span>
</div>

    <div className="stats-grid dashboard-stats">
      <StatCard label="Tổng số ticket" value={value(metrics.total)} helper="Tất cả yêu cầu đã ghi nhận" icon="▤" tone="blue" />
      <StatCard label="Chờ duyệt" value={value(metrics.pendingReview)} helper="Ticket đang chờ nhân viên xác nhận" icon="◷" tone="orange" />
      <StatCard label="Cảnh báo khẩn cấp" value={value(metrics.hazardEscalated)} helper="Ticket cần ưu tiên xử lý an toàn" icon="⚠" tone="red" />
      <StatCard label="Đã giải quyết" value={value(metrics.resolved)} helper="Ticket đã hoàn tất xử lý" icon="✓" tone="green" />
    </div>

    <div className="dashboard-panels">
      <TicketTrend title="Xu hướng ticket tiếp nhận" />
      <section className="panel status-panel">
        <h2>Chỉ số xử lý ticket</h2>
        <div className="status-summary"><span className="dot blue-dot" /><span>Chờ duyệt</span><b>{value(metrics.pendingReview)}</b></div>
        <div className="status-summary"><span className="dot red-dot" /><span>Cảnh báo khẩn cấp</span><b>{value(metrics.hazardEscalated)}</b></div>
        <div className="status-summary"><span className="dot green-dot" /><span>Đã giải quyết</span><b>{value(metrics.resolved)}</b></div>
      </section>
    </div>
    <section className="insight-panel">
      <strong>THEO DÕI VẬN HÀNH</strong>
      <p>{loading ? 'Đang tải dữ liệu ticket...' : `Hệ thống ghi nhận ${metrics.total} ticket, trong đó có ${metrics.pendingReview} ticket chờ duyệt, ${metrics.hazardEscalated} cảnh báo khẩn cấp và ${metrics.resolved} ticket đã giải quyết.`}</p>
      <small>Số liệu được tính trực tiếp từ danh sách ticket hiện tại.</small>
    </section>
  </>
}
