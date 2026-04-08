import type { ConfidenceLevel } from '@/lib/types'
import { cn } from '@/lib/utils'

interface ConfidenceBadgeProps {
  level: ConfidenceLevel
  score?: number | null
  className?: string
}

const config: Record<ConfidenceLevel, { label: string; dot: string; classes: string }> = {
  high: {
    label: 'High',
    dot: '🟢',
    classes: 'bg-green-100 text-green-800 border border-green-200',
  },
  medium: {
    label: 'Medium',
    dot: '🟡',
    classes: 'bg-amber-100 text-amber-800 border border-amber-200',
  },
  low: {
    label: 'Low',
    dot: '🔴',
    classes: 'bg-red-100 text-red-800 border border-red-200',
  },
}

export function ConfidenceBadge({ level, score, className }: ConfidenceBadgeProps) {
  const { label, dot, classes } = config[level]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium font-mono',
        classes,
        className
      )}
    >
      <span className="text-[10px]">{dot}</span>
      {label}
      {score != null && (
        <span className="opacity-75">({Math.round(score * 100)}%)</span>
      )}
    </span>
  )
}
