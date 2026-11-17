
interface StatCardProps {
  label: string
  value: string
  helper: string
  icon: string
  tone: 'blue' | 'green' | 'red' | 'purple' | 'orange'
}

export default function StatCard({
  label,
  value,
  helper,
  icon,
  tone,
}: StatCardProps) {
  return (
    <article className={`stat-card stat-card--${tone}`}>
      <p className="stat-label">{label}</p>

      <div className="stat-value-row">
        <strong className="stat-value">{value}</strong>

        <span className={`stat-icon ${tone}`} aria-hidden="true">
          {icon}
        </span>
      </div>

      <p className="stat-helper">{helper}</p>
    </article>
  )
}
