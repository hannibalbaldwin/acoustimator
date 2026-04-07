import type { ScopeType } from '@/lib/types'
import { cn } from '@/lib/utils'

interface ScopeTypeBadgeProps {
  type: ScopeType
  className?: string
}

const scopeColors: Record<ScopeType, string> = {
  ACT: 'bg-blue-100 text-blue-700 border-blue-200',
  AWP: 'bg-green-100 text-green-700 border-green-200',
  AP: 'bg-green-100 text-green-700 border-green-200',
  FW: 'bg-teal-100 text-teal-700 border-teal-200',
  SM: 'bg-purple-100 text-purple-700 border-purple-200',
  WW: 'bg-orange-100 text-orange-700 border-orange-200',
  Baffles: 'bg-pink-100 text-pink-700 border-pink-200',
  RPG: 'bg-violet-100 text-violet-700 border-violet-200',
  Other: 'bg-zinc-100 text-zinc-600 border-zinc-200',
}

export function ScopeTypeBadge({ type, className }: ScopeTypeBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold border font-mono tracking-wide',
        scopeColors[type] ?? scopeColors.Other,
        className
      )}
    >
      {type}
    </span>
  )
}
