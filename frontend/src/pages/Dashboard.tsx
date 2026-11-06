
import StatCard from '../components/StatCard'

export interface DashboardMetrics {
  total: number
  solved: number
  processing: number
  escalated: number
  resolutionRate: number
  averageResponse: string
}

interface DashboardProps {
  metrics: DashboardMetrics
  loading: boolean
}

export default function Dashboard({
  metrics,
  loading,
}: DashboardProps) {
  return (
    <>
      <div className="page-title-row">
        <div>
          <h1>Tổng quan hệ thống</h1>
          <p className="subtitle">
            Theo dõi tình hình tiếp nhận và xử lý yêu cầu hỗ trợ.
          </p>
        </div>

        <span className="date-filter">
          30 ngày gần nhất
        </span>
      </div>

      <div className="stats-grid dashboard-stats">
        <StatCard
          label="Tổng số ticket"
          value={loading ? '—' : metrics.total.toLocaleString('vi-VN')}
          helper="+12,8% so với kỳ trước"
          icon="▤"
          tone="blue"
        />

        <StatCard
          label="AI Resolution Rate"
          value={loading ? '—' : `${metrics.resolutionRate}%`}
          helper="Tỷ lệ AI tự động giải quyết"
          icon="✦"
          tone="green"
        />

        <StatCard
          label="Phản hồi trung bình"
          value={loading ? '—' : `${metrics.averageResponse} phút`}
          helper="Thời gian phản hồi trung bình"
          icon="◷"
          tone="purple"
        />

        <StatCard
          label="Ticket cần chú ý"
          value={loading ? '—' : String(metrics.escalated)}
          helper="Đang chuyển nhân viên xử lý"
          icon="!"
          tone="orange"
        />
      </div>

      <div className="dashboard-panels">
        <section className="panel trend-panel">
          <h2>Xu hướng ticket theo thời gian</h2>
          <p className="legend">
            <i /> Ticket tiếp nhận
          </p>

          <div
            className="chart-area"
            aria-label="Biểu đồ ticket theo thời gian"
          >
            {[34, 49, 39, 68, 58, 91, 78, 100].map(
              (height, index) => (
                <div className="chart-column" key={index}>
                  <span style={{ height: `${height}%` }} />

                  <small>
                    {[
                      '01/10',
                      '05/10',
                      '10/10',
                      '15/10',
                      '20/10',
                      '25/10',
                      '28/10',
                      '30/10',
                    ][index]}
                  </small>
                </div>
              )
            )}
          </div>
        </section>

        <section className="panel status-panel">
          <h2>Phân bố trạng thái</h2>

          <div className="status-summary">
            <span className="dot blue-dot" />
            <span>Mới / Processing</span>
            <b>{metrics.processing}</b>
          </div>

          <div className="status-summary">
            <span className="dot green-dot" />
            <span>Đã giải quyết</span>
            <b>{metrics.solved}</b>
          </div>

          <div className="status-summary">
            <span className="dot red-dot" />
            <span>Escalated</span>
            <b>{metrics.escalated}</b>
          </div>
        </section>
      </div>

      <section className="insight-panel">
        <strong>INSIGHT TỪ AI</strong>

        <p>
          AI đã giải quyết {metrics.resolutionRate}% số ticket
          trong dữ liệu hiện tại. Nhân viên có thể ưu tiên
          các yêu cầu đang Escalated để cải thiện tốc độ hỗ trợ.
        </p>

        <small>
          Gợi ý dựa trên dữ liệu ticket đã ghi nhận ·
          Cần nhân viên xác nhận trước khi áp dụng
        </small>
      </section>
    </>
  )
}
