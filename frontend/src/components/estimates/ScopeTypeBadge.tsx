import type { ScopeType } from '@/lib/types'
import { cn } from '@/lib/utils'

interface ScopeTypeBadgeProps {
  type: ScopeType
  className?: string
}

// Dark-mode optimized — translucent tinted backgrounds against dark surface
const scopeConfig: Record<ScopeType, { color: string; bg: string; border: string }> = {
  ACT:     { color: '#60a5fa', bg: 'rgba(96,165,250,0.10)',   border: 'rgba(96,165,250,0.20)'   },
  AWP:     { color: '#a1d67c', bg: 'rgba(161,214,124,0.10)', border: 'rgba(161,214,124,0.20)'   },
  AP:      { color: '#a1d67c', bg: 'rgba(161,214,124,0.10)', border: 'rgba(161,214,124,0.20)'   },
  FW:      { color: '#2dd4bf', bg: 'rgba(45,212,191,0.10)',   border: 'rgba(45,212,191,0.20)'   },
  SM:      { color: '#c084fc', bg: 'rgba(192,132,252,0.10)', border: 'rgba(192,132,252,0.20)'   },
  WW:      { color: '#fb923c', bg: 'rgba(251,146,60,0.10)',   border: 'rgba(251,146,60,0.20)'   },
  Baffles: { color: '#f472b6', bg: 'rgba(244,114,182,0.10)', border: 'rgba(244,114,182,0.20)'   },
  RPG:     { color: '#818cf8', bg: 'rgba(129,140,248,0.10)', border: 'rgba(129,140,248,0.20)'   },
  Other:   { color: '#6b7280', bg: 'rgba(107,114,128,0.10)', border: 'rgba(107,114,128,0.20)'   },
}

export function ScopeTypeBadge({ type, className }: ScopeTypeBadgeProps) {
  const c = scopeConfig[type] ?? scopeConfig.Other
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded-[4px] text-[11px] font-semibold font-mono tracking-wide',
        className
      )}
      style={{
        color: c.color,
        background: c.bg,
        border: `1px solid ${c.border}`,
      }}
    >
      {type}
    </span>
  )
}
