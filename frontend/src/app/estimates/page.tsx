'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { EstimateBoard } from '@/components/estimates/EstimateBoard'
import { ConfidenceBadge } from '@/components/estimates/ConfidenceBadge'
import { ScopeTypeBadge } from '@/components/estimates/ScopeTypeBadge'
import { listEstimates, deleteEstimate, type EstimateListItem } from '@/lib/api'
import { formatCurrency } from '@/lib/utils'
import type { ScopeType } from '@/lib/types'
import { useTheme } from '@/components/ThemeProvider'
import { WaveformLoader } from '@/components/ui/WaveformLoader'

const STATUS_STYLES: Record<string, { color: string; bg: string; border: string }> = {
  draft:     { color: '#6b82a0', bg: 'rgba(107,130,160,0.10)', border: 'rgba(107,130,160,0.18)' },
  reviewed:  { color: '#60a5fa', bg: 'rgba(96,165,250,0.10)',  border: 'rgba(96,165,250,0.18)'  },
  finalized: { color: '#a1d67c', bg: 'rgba(161,214,124,0.10)', border: 'rgba(161,214,124,0.18)' },
  exported:  { color: '#c084fc', bg: 'rgba(192,132,252,0.10)', border: 'rgba(192,132,252,0.18)' },
}

const STATUS_FILTERS = ['All', 'draft', 'reviewed', 'finalized', 'exported'] as const

export default function EstimatesPage() {
  const { theme } = useTheme()
  const isLight = theme === 'light'

  const textPrimary = isLight ? '#0f1923' : '#d8e4f5'
  const textSubtitle = isLight ? '#5a7a9a' : '#3a4f6a'
  const textMuted = isLight ? '#7890aa' : '#3a4f6a'
  const tableBg = isLight ? '#ffffff' : '#131822'
  const borderDefault = isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)'
  const borderFaint = isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.06)'
  const borderHairline = isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.04)'
  const rowHoverBg = isLight ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.025)'
  const inactiveFilterBorder = isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)'
  const inactiveFilterColor = isLight ? '#7890aa' : '#3a4f6a'

  const [estimates, setEstimates] = useState<EstimateListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [view, setView] = useState<'table' | 'board'>('board')
  const [statusFilter, setStatusFilter] = useState<string>('All')

  const handleDeleteEstimate = async (id: string) => {
    if (!window.confirm('Delete this estimate?')) return
    try {
      await deleteEstimate(id)
      setEstimates((prev) => prev.filter((e) => e.id !== id))
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete estimate')
    }
  }

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    const params: { limit: number; status?: string } = { limit: 50 }
    if (statusFilter !== 'All') params.status = statusFilter

    listEstimates(params)
      .then((res) => {
        if (cancelled) return
        setEstimates(res.items)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load estimates')
        setLoading(false)
      })

    return () => { cancelled = true }
  }, [statusFilter])

  return (
    <div className="px-4 py-6 md:px-8 md:py-8 w-full max-w-screen-2xl">

      {/* ── Header ── */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1
            className="text-[22px] font-semibold tracking-tight leading-tight"
            style={{ color: textPrimary }}
          >
            Estimates
          </h1>
          <p className="text-[13px] mt-1" style={{ color: textSubtitle }}>
            {loading ? '...' : `${estimates.length} estimate${estimates.length !== 1 ? 's' : ''}`}
            {statusFilter !== 'All' && ` · filtered by ${statusFilter}`}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* View toggle */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => setView('table')}
              className="flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-[4px] transition-all"
              style={
                view === 'table'
                  ? isLight
                    ? { background: 'rgba(82,155,30,0.12)', border: '1px solid rgba(82,155,30,0.28)', color: '#3d7010' }
                    : { background: 'rgba(161,214,124,0.12)', border: '1px solid rgba(161,214,124,0.22)', color: '#a1d67c' }
                  : { background: 'transparent', border: `1px solid ${inactiveFilterBorder}`, color: inactiveFilterColor }
              }
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                <line x1="1" y1="3" x2="11" y2="3" />
                <line x1="1" y1="6" x2="11" y2="6" />
                <line x1="1" y1="9" x2="11" y2="9" />
              </svg>
              Table
            </button>
            <button
              onClick={() => setView('board')}
              className="flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-[4px] transition-all"
              style={
                view === 'board'
                  ? isLight
                    ? { background: 'rgba(82,155,30,0.12)', border: '1px solid rgba(82,155,30,0.28)', color: '#3d7010' }
                    : { background: 'rgba(161,214,124,0.12)', border: '1px solid rgba(161,214,124,0.22)', color: '#a1d67c' }
                  : { background: 'transparent', border: `1px solid ${inactiveFilterBorder}`, color: inactiveFilterColor }
              }
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="1" y="1" width="4" height="4" rx="0.75" />
                <rect x="7" y="1" width="4" height="4" rx="0.75" />
                <rect x="1" y="7" width="4" height="4" rx="0.75" />
                <rect x="7" y="7" width="4" height="4" rx="0.75" />
              </svg>
              Board
            </button>
          </div>

          {/* New Estimate CTA */}
          <Link
            href="/estimates/new"
            className="flex items-center gap-2 px-4 py-2 text-[13px] font-semibold rounded-[6px] transition-all duration-100 hover:scale-[1.01]"
            style={{
              background: 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
              color: '#080b10',
              boxShadow: '0 0 20px rgba(161,214,124,0.2)',
            }}
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M12 5v14M5 12h14" strokeWidth="2.5" strokeLinecap="round" />
            </svg>
            New Estimate
          </Link>
        </div>
      </div>

      {/* ── Status filters ── */}
      <div className="flex items-center gap-1.5 mb-5">
        {STATUS_FILTERS.map((s) => {
          const isActive = statusFilter === s
          return (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className="text-[11px] font-medium px-3 py-1 rounded-[4px] transition-all capitalize"
              style={
                isActive
                  ? isLight
                    ? { background: 'rgba(82,155,30,0.12)', border: '1px solid rgba(82,155,30,0.28)', color: '#3d7010' }
                    : { background: 'rgba(161,214,124,0.12)', border: '1px solid rgba(161,214,124,0.22)', color: '#a1d67c' }
                  : { background: 'transparent', border: `1px solid ${inactiveFilterBorder}`, color: inactiveFilterColor }
              }
            >
              {s}
            </button>
          )
        })}
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 rounded-[6px] text-[13px]" style={{ color: '#f05252', background: 'rgba(240,82,82,0.08)', border: '1px solid rgba(240,82,82,0.15)' }}>
          {error}
        </div>
      )}

      {/* ── Content ── */}
      <div className={loading ? 'opacity-50 pointer-events-none' : undefined}>
        {view === 'board' ? (
          <EstimateBoard estimates={estimates} />
        ) : (
          <div
            className="rounded-[8px] overflow-hidden"
            style={{ background: tableBg, border: `1px solid ${borderDefault}` }}
          >
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr style={{ borderBottom: `1px solid ${borderFaint}` }}>
                    {['Project', 'Scopes', 'Total', 'Confidence', 'Status', 'Date', ''].map((col, i) => (
                      <th
                        key={i}
                        className={`px-4 py-2.5 text-[10px] font-semibold uppercase tracking-[0.09em] ${col === 'Total' ? 'text-right' : 'text-left'}`}
                        style={{ color: textMuted }}
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {loading && estimates.length === 0 && (
                    <tr>
                      <td colSpan={7}>
                        <WaveformLoader variant="block" />
                      </td>
                    </tr>
                  )}
                  {estimates.length === 0 && !loading && (
                    <tr>
                      <td colSpan={7} className="px-4 py-8 text-center text-[13px]" style={{ color: textMuted }}>
                        No estimates found
                      </td>
                    </tr>
                  )}
                  {estimates.map((est) => {
                    const st = STATUS_STYLES[est.status] ?? STATUS_STYLES.draft
                    return (
                      <tr
                        key={est.id}
                        className="group transition-colors"
                        style={{ borderBottom: `1px solid ${borderHairline}` }}
                        onMouseEnter={(e) =>
                          ((e.currentTarget as HTMLTableRowElement).style.background = rowHoverBg)
                        }
                        onMouseLeave={(e) =>
                          ((e.currentTarget as HTMLTableRowElement).style.background = 'transparent')
                        }
                      >
                        <td className="px-4 py-2.5">
                          <p className="font-medium" style={{ color: textPrimary }}>
                            {est.project_name}
                          </p>
                          <p className="text-[11px] mt-0.5" style={{ color: textMuted }}>
                            {est.gc_name}
                          </p>
                        </td>
                        <td className="px-4 py-2.5">
                          <div className="flex flex-wrap gap-1">
                            {est.scope_types.map((s) => (
                              <ScopeTypeBadge key={s} type={s as ScopeType} />
                            ))}
                          </div>
                        </td>
                        <td
                          className="px-4 py-2.5 text-right tabular-nums font-semibold"
                          style={{ fontFamily: 'var(--font-jetbrains-mono), monospace', color: textPrimary }}
                        >
                          {formatCurrency(est.total_cost)}
                        </td>
                        <td className="px-4 py-2.5">
                          <ConfidenceBadge level={(est.confidence_level ?? 'low') as 'high' | 'medium' | 'low'} />
                        </td>
                        <td className="px-4 py-2.5">
                          <span
                            className="text-[11px] px-2 py-0.5 rounded-[4px] font-medium"
                            style={{ color: st.color, background: st.bg, border: `1px solid ${st.border}` }}
                          >
                            {est.status.charAt(0).toUpperCase() + est.status.slice(1)}
                          </span>
                        </td>
                        <td
                          className="px-4 py-2.5 text-[11px] tabular-nums"
                          style={{ color: textMuted, fontFamily: 'var(--font-jetbrains-mono), monospace' }}
                        >
                          {est.created_at.slice(0, 10)}
                        </td>
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-3 justify-end">
                            <Link
                              href={`/estimates/${est.id}`}
                              className="text-[12px] font-medium opacity-0 group-hover:opacity-100 transition-opacity"
                              style={{ color: isLight ? '#4a8a10' : '#a1d67c' }}
                            >
                              Review →
                            </Link>
                            <button
                              onClick={(e) => { e.preventDefault(); handleDeleteEstimate(est.id) }}
                              className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center rounded p-1"
                              title="Delete estimate"
                              onMouseEnter={(e) => {
                                const el = e.currentTarget as HTMLButtonElement
                                el.style.color = '#ef4444'
                              }}
                              onMouseLeave={(e) => {
                                const el = e.currentTarget as HTMLButtonElement
                                el.style.color = isLight ? '#7890aa' : '#3a4f6a'
                              }}
                              style={{ color: isLight ? '#7890aa' : '#3a4f6a', background: 'transparent', border: 'none', cursor: 'pointer' }}
                            >
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="3 6 5 6 21 6" />
                                <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                                <path d="M10 11v6M14 11v6" />
                                <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
                              </svg>
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
