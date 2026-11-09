
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

  const counts = categories.map((category) => ({
    label: category.label,
    count: tickets.filter((ticket) =>
      category.match.test(ticket.title)
    ).length,
  }))

  const responseTimes = tickets
    .map((ticket) => ticket.responseTimeMinutes)
    .filter(
      (value): value is number =>
        value !== null && Number.isFinite(value)
    )

  const averageResponse = responseTimes.length
    ? Math.round(
        responseTimes.reduce((sum, value) => sum + value, 0) /
          responseTimes.length
      )
    : 0

  const aiSolved = tickets.filter(
    (ticket) => ticket.status === 'AI_SOLVED'
  ).length

  const resolutionRate = metrics.total
    ? Math.round((metrics.resolved / metrics.total) * 100)
    : 0

  const displayValue = (value: string) =>
    loading ? '—' : value

  return (
    <>
      <div className="page-title-row">
        <div>
          <h1>Phân tích hiệu suất hỗ trợ</h1>
          <p className="subtitle">
            Đo lường chất lượng xử lý ticket và mức độ hỗ trợ của AI.
          </p>
        </div>
        <span className="date-filter">Dữ liệu hiện tại</span>
      </div>

      <div className="stats-grid dashboard-stats">
        <StatCard
          label="Tổng ticket"
          value={displayValue(metrics.total.toLocaleString('vi-VN'))}
          helper="Tất cả yêu cầu đã ghi nhận"
          icon=""
          tone="blue"
        />

        <StatCard
          label="Ticket chờ duyệt"
          value={displayValue(String(metrics.pendingReview))}
          helper="Đang chờ nhân viên xác nhận"
          icon=""
          tone="orange"
        />

        <StatCard
          label="Ticket khẩn cấp"
          value={displayValue(String(metrics.hazardEscalated))}
          helper="Ticket được chuyển cấp cảnh báo"
          icon=""
          tone="purple"
        />

        <StatCard
          label="Ticket đã giải quyết"
          value={displayValue(String(metrics.resolved))}
          helper="Đã hoàn tất xử lý"
          icon=""
          tone="green"
        />
      </div>

      <div className="analytics-panels">
        <TicketTrend title="Số lượng ticket theo ngày" />

        <section className="panel ai-performance">
          <h2>Hiệu quả hỗ trợ AI</h2>
          <p>Tỷ lệ ticket đã giải quyết</p>

          <strong>{loading ? '—' : `${resolutionRate}%`}</strong>

          <progress
            max={100}
            value={loading ? 0 : resolutionRate}
            aria-label="Tỷ lệ ticket đã giải quyết"
          />

          <p>Ticket được AI giải quyết</p>
          <b>{loading ? '—' : `${aiSolved} / ${metrics.total}`}</b>

          <p>Thời gian phản hồi trung bình</p>
          <b>
            {loading
              ? '—'
              : responseTimes.length
                ? `${averageResponse} phút`
                : 'Chưa có dữ liệu'}
          </b>
        </section>
      </div>

      <div className="analytics-bottom">
        <section className="panel category-panel">
          <h2>Top danh mục yêu cầu</h2>

          {counts.map((category) => (
            <div className="category-row" key={category.label}>
              <span>{category.label}</span>

              <progress
                max={Math.max(1, metrics.total)}
                value={category.count}
                aria-label={category.label}
              />

              <b>
                {metrics.total
                  ? Math.round(
                      (category.count / metrics.total) * 100
                    )
                  : 0}
                %
              </b>
            </div>
          ))}

          <small>
            Nhóm theo từ khóa tiêu đề, có thể trùng danh mục.
          </small>
        </section>

        <section className="insight-panel metric-definitions">
          <h2>Định nghĩa chỉ số</h2>

          <p>
            • Tổng ticket: tổng số yêu cầu đã ghi nhận.
            <br />
            • Ticket chờ duyệt: trạng thái Pending Review.
            <br />
            • Ticket khẩn cấp: trạng thái Hazard Escalated hoặc Escalated.
            <br />
            • Ticket đã giải quyết: trạng thái Resolved hoặc AI Solved.
          </p>
        </section>
      </div>
    </>
  )
}
