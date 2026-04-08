import type { ConfidenceLevel } from '@/lib/types'
import { cn } from '@/lib/utils'

interface ConfidenceBadgeProps {
  level: ConfidenceLevel
  score?: number | null
  size?: 'sm' | 'lg'
  className?: string
}

const config: Record<
  ConfidenceLevel,
  { label: string; color: string; bg: string; border: string; dot: string }
> = {
  high: {
    label: 'High',
    color: '#a1d67c',
    bg: 'rgba(161, 214, 124, 0.10)',
    border: 'rgba(161, 214, 124, 0.22)',
    dot: '#a1d67c',
  },
  medium: {
    label: 'Medium',
    color: '#f59e0b',
    bg: 'rgba(245, 158, 11, 0.10)',
    border: 'rgba(245, 158, 11, 0.22)',
    dot: '#f59e0b',
  },
  low: {
    label: 'Low',
    color: '#f05252',
    bg: 'rgba(240, 82, 82, 0.10)',
    border: 'rgba(240, 82, 82, 0.22)',
    dot: '#f05252',
  },
}

export function ConfidenceBadge({ level, score, size = 'sm', className }: ConfidenceBadgeProps) {
  const c = config[level]
  const isLg = size === 'lg'

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-[4px] font-medium font-mono',
        isLg ? 'px-3 py-1.5 text-sm' : 'px-2 py-0.5 text-[11px]',
        className
      )}
      style={{
        color: c.color,
        background: c.bg,
        border: `1px solid ${c.border}`,
      }}
    >
      <span
        className={cn('rounded-full flex-shrink-0', isLg ? 'w-2 h-2' : 'w-1.5 h-1.5')}
        style={{ background: c.dot, boxShadow: `0 0 6px ${c.dot}` }}
      />
      {c.label}
      {score != null && (
        <span className="opacity-70">({Math.round(score * 100)}%)</span>
      )}
    </span>
  )
}
