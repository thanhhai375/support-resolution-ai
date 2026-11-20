
import {
  Ticket,
  Clock3,
  ShieldAlert,
  CheckCircle2,
  Sparkles,
} from 'lucide-react'

interface StatCardProps {
  label: string
  value: string
  helper: string
  icon: string
  tone: 'blue' | 'green' | 'red' | 'purple' | 'orange'
}

const toneIcons = {
  blue: Ticket,
  orange: Clock3,
  red: ShieldAlert,
  green: CheckCircle2,
  purple: Sparkles,
}

export default function StatCard({
  label,
  value,
  helper,
  tone,
}: StatCardProps) {
  const Icon = toneIcons[tone]

  return (
    <article className={`stat-card stat-card--${tone}`}>
      <p className="stat-label">{label}</p>

      <div className="stat-value-row">
        <strong className="stat-value">
          {value}
        </strong>

        <span
          className={`stat-icon ${tone}`}
          aria-hidden="true"
        >
          <Icon size={25} strokeWidth={2.2} />
        </span>
      </div>

      <p className="stat-helper">{helper}</p>
    </article>
  )
}
