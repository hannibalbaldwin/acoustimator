import type { EstimateResponse } from '@/lib/types'
import { formatCurrency, formatCurrencyFull } from '@/lib/utils'
import { ConfidenceBadge } from './ConfidenceBadge'
import { cn } from '@/lib/utils'

interface EstimateSummaryProps {
  estimate: EstimateResponse
}

function StatCard({
  label,
  value,
  highlight,
  sub,
}: {
  label: string
  value: string
  highlight?: boolean
  sub?: string
}) {
  return (
    <div className="bg-white border border-zinc-200 rounded-lg px-5 py-4">
      <p className="text-xs font-medium text-zinc-500 uppercase tracking-wide">{label}</p>
      <p
        className={cn(
          'text-2xl font-mono font-semibold mt-1 tabular-nums',
          highlight ? 'text-green-700' : 'text-zinc-900'
        )}
      >
        {value}
      </p>
      {sub && <p className="text-xs text-zinc-400 mt-0.5 font-mono">{sub}</p>}
    </div>
  )
}

export function EstimateSummary({ estimate }: EstimateSummaryProps) {
  const isHighConf = estimate.confidence_level === 'high'

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-zinc-900">{estimate.project_name}</h1>
          <div className="flex items-center gap-3 mt-1">
            {estimate.gc_name && (
              <span className="text-sm text-zinc-500">{estimate.gc_name}</span>
            )}
            {estimate.address && (
              <span className="text-sm text-zinc-400">{estimate.address}</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <ConfidenceBadge
            level={estimate.confidence_level}
            score={estimate.confidence_score}
            className="text-sm px-3 py-1"
          />
          <span className={cn(
            'text-xs px-2 py-1 rounded border font-medium',
            estimate.status === 'draft' && 'bg-zinc-100 text-zinc-600 border-zinc-200',
            estimate.status === 'reviewed' && 'bg-blue-100 text-blue-700 border-blue-200',
            estimate.status === 'finalized' && 'bg-green-100 text-green-700 border-green-200',
            estimate.status === 'exported' && 'bg-purple-100 text-purple-700 border-purple-200',
          )}>
            {estimate.status.charAt(0).toUpperCase() + estimate.status.slice(1)}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3">
        <StatCard
          label="Total Cost"
          value={formatCurrency(estimate.total_cost)}
          highlight={isHighConf}
        />
        <StatCard
          label="Total SF"
          value={estimate.total_sf != null
            ? new Intl.NumberFormat('en-US').format(estimate.total_sf)
            : '—'}
          sub="square feet"
        />
        <StatCard
          label="Cost / SF"
          value={estimate.cost_per_sf != null
            ? formatCurrencyFull(estimate.cost_per_sf)
            : '—'}
          sub="blended rate"
        />
        <StatCard
          label="Man Days"
          value={estimate.man_days != null ? estimate.man_days.toFixed(1) : '—'}
          sub="labor estimate"
        />
      </div>
    </div>
  )
}
