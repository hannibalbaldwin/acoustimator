import { cn } from '@/lib/utils'

interface StatCardProps {
  label: string
  value: string
  delta?: {
    value: string
    positive?: boolean
  }
  className?: string
}

export function StatCard({ label, value, delta, className }: StatCardProps) {
  return (
    <div className={cn('bg-white border border-zinc-200 rounded-lg px-5 py-4', className)}>
      <p className="text-xs font-medium text-zinc-500 uppercase tracking-wide">{label}</p>
      <div className="flex items-end gap-2 mt-1">
        <p className="text-2xl font-mono font-semibold text-zinc-900 tabular-nums">{value}</p>
        {delta && (
          <span
            className={cn(
              'text-xs font-medium font-mono mb-0.5 px-1.5 py-0.5 rounded',
              delta.positive
                ? 'text-green-700 bg-green-100'
                : 'text-red-700 bg-red-100'
            )}
          >
            {delta.positive ? '+' : ''}{delta.value}
          </span>
        )}
      </div>
    </div>
  )
}
