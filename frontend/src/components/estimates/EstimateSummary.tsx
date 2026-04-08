import { formatCurrency } from '@/lib/utils'
import { ConfidenceBadge } from './ConfidenceBadge'
import { ScopeTypeBadge } from './ScopeTypeBadge'
import type { EstimateResponse } from '@/lib/types'

interface EstimateSummaryProps {
  estimate: EstimateResponse
}

const STATUS_STYLES: Record<string, { color: string; bg: string; border: string }> = {
  draft:     { color: '#6b82a0', bg: 'rgba(107,130,160,0.10)', border: 'rgba(107,130,160,0.18)' },
  reviewed:  { color: '#60a5fa', bg: 'rgba(96,165,250,0.10)',  border: 'rgba(96,165,250,0.18)'  },
  finalized: { color: '#a1d67c', bg: 'rgba(161,214,124,0.10)', border: 'rgba(161,214,124,0.18)' },
  exported:  { color: '#c084fc', bg: 'rgba(192,132,252,0.10)', border: 'rgba(192,132,252,0.18)' },
}

export function EstimateSummary({ estimate }: EstimateSummaryProps) {
  const st = STATUS_STYLES[estimate.status] ?? STATUS_STYLES.draft
  const acceptedScopes = estimate.scopes.filter((s) => s.is_accepted).length
  const totalSF = estimate.scopes.reduce((sum, s) => sum + (s.area_sf ?? 0), 0)
  const uniqueScopes = [...new Set(estimate.scopes.map((s) => s.scope_type))]

  return (
    <div
      className="rounded-[8px] p-5"
      style={{
        background: '#131822',
        border: '1px solid rgba(255,255,255,0.08)',
      }}
    >
      {/* Top row: project name + status */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h1
            className="text-[18px] font-semibold leading-tight"
            style={{ color: '#d8e4f5' }}
          >
            {estimate.project_name}
          </h1>
          {estimate.gc_name && (
            <p className="text-[12px] mt-0.5" style={{ color: '#3a4f6a' }}>
              {estimate.gc_name}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <span
            className="text-[11px] px-2.5 py-0.5 rounded-[4px] font-medium"
            style={{ color: st.color, background: st.bg, border: `1px solid ${st.border}` }}
          >
            {estimate.status.charAt(0).toUpperCase() + estimate.status.slice(1)}
          </span>
          <ConfidenceBadge level={estimate.confidence_level} size="sm" />
        </div>
      </div>

      {/* Stat row */}
      <div
        className="grid grid-cols-4 gap-3 pt-4"
        style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
      >
        <div>
          <p
            className="text-[10px] font-semibold uppercase tracking-[0.09em] mb-1"
            style={{ color: '#3a4f6a' }}
          >
            Total Cost
          </p>
          <p
            className="text-[20px] leading-none font-semibold tabular-nums"
            style={{
              fontFamily: 'var(--font-jetbrains-mono), monospace',
              color: '#a1d67c',
              letterSpacing: '-0.03em',
            }}
          >
            {formatCurrency(estimate.total_cost)}
          </p>
        </div>

        <div>
          <p
            className="text-[10px] font-semibold uppercase tracking-[0.09em] mb-1"
            style={{ color: '#3a4f6a' }}
          >
            Total SF
          </p>
          <p
            className="text-[20px] leading-none font-semibold tabular-nums"
            style={{
              fontFamily: 'var(--font-jetbrains-mono), monospace',
              color: '#d8e4f5',
              letterSpacing: '-0.03em',
            }}
          >
            {totalSF > 0 ? new Intl.NumberFormat('en-US').format(Math.round(totalSF)) : '—'}
          </p>
        </div>

        <div>
          <p
            className="text-[10px] font-semibold uppercase tracking-[0.09em] mb-1"
            style={{ color: '#3a4f6a' }}
          >
            Scope Lines
          </p>
          <p
            className="text-[20px] leading-none font-semibold tabular-nums"
            style={{
              fontFamily: 'var(--font-jetbrains-mono), monospace',
              color: '#d8e4f5',
              letterSpacing: '-0.03em',
            }}
          >
            {acceptedScopes}
            <span className="text-[13px] ml-1" style={{ color: '#3a4f6a' }}>
              / {estimate.scopes.length}
            </span>
          </p>
        </div>

        <div>
          <p
            className="text-[10px] font-semibold uppercase tracking-[0.09em] mb-1.5"
            style={{ color: '#3a4f6a' }}
          >
            Scope Types
          </p>
          <div className="flex flex-wrap gap-1">
            {uniqueScopes.map((s) => (
              <ScopeTypeBadge key={s} type={s} />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
