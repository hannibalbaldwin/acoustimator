'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { format } from 'date-fns'
import { StatCard } from '@/components/dashboard/StatCard'
import { CostTrendChart } from '@/components/dashboard/CostTrendChart'
import { ConfidenceBadge } from '@/components/estimates/ConfidenceBadge'
import { ScopeTypeBadge } from '@/components/estimates/ScopeTypeBadge'
import { EstimateBoard } from '@/components/estimates/EstimateBoard'
import { listEstimates, getDashboardStats, type EstimateListItem, type DashboardStats } from '@/lib/api'
import { formatCurrency } from '@/lib/utils'
import type { ScopeType } from '@/lib/types'
import { useTheme } from '@/components/ThemeProvider'

const STATUS_STYLES: Record<string, { color: string; bg: string; border: string }> = {
  draft:     { color: '#6b82a0', bg: 'rgba(107,130,160,0.10)', border: 'rgba(107,130,160,0.18)' },
  reviewed:  { color: '#60a5fa', bg: 'rgba(96,165,250,0.10)',  border: 'rgba(96,165,250,0.18)'  },
  finalized: { color: '#a1d67c', bg: 'rgba(161,214,124,0.10)',border: 'rgba(161,214,124,0.18)' },
  exported:  { color: '#c084fc', bg: 'rgba(192,132,252,0.10)',border: 'rgba(192,132,252,0.18)' },
}

export default function DashboardPage() {
  const { theme } = useTheme()
  const isLight = theme === 'light'
  const [estimates, setEstimates] = useState<EstimateListItem[]>([])
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [view, setView] = useState<'table' | 'board'>('table')

  useEffect(() => {
    let cancelled = false
    Promise.all([
      listEstimates({ limit: 20 }),
      getDashboardStats(),
    ])
      .then(([estimatesRes, dashStats]) => {
        if (cancelled) return
        setEstimates(estimatesRes.items)
        setStats(dashStats)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load dashboard data')
        setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  return (
    <div className="px-4 py-6 md:px-8 md:py-8 w-full max-w-screen-2xl">

      {/* ── Header ── */}
      <div className="flex items-start justify-between mb-7">
        <div>
          <h1
            className="text-[22px] font-semibold tracking-tight leading-tight"
            style={{ color: isLight ? '#0f1923' : '#d8e4f5' }}
          >
            Dashboard
          </h1>
          <p className="text-[13px] mt-1" style={{ color: isLight ? '#5a7a9a' : '#3a4f6a' }}>
            {format(new Date(), 'MMMM d, yyyy')} · Commercial Acoustics, Tampa FL
          </p>
        </div>

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

      {/* ── Stat cards ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5 mb-6">
        <StatCard
          label="Total Projects"
          value={loading ? '—' : (stats?.total_projects.toString() ?? '—')}
        />
        <StatCard
          label="Active Estimates"
          value={loading ? '—' : (stats?.active_estimates.toString() ?? '—')}
        />
        <StatCard
          label="Avg ACT Cost / SF"
          value={loading ? '—' : (stats?.avg_act_cost_per_sf != null ? '$' + stats.avg_act_cost_per_sf.toFixed(2) : '—')}
          accent
        />
        <StatCard
          label="Total SF Estimated"
          value={loading ? '—' : (stats?.total_historical_sf != null ? (stats.total_historical_sf / 1_000_000).toFixed(1) + 'M' : '—')}
          delta={{ value: 'historical', neutral: true }}
        />
      </div>

      {/* ── Trend chart ── */}
      <div className="mb-6">
        <CostTrendChart />
      </div>

      {/* ── Recent estimates table ── */}
      <div
        className="rounded-[8px] overflow-hidden"
        style={{
          background: isLight ? '#ffffff' : '#131822',
          border: `1px solid ${isLight ? 'rgba(0,0,0,0.09)' : 'rgba(255,255,255,0.08)'}`,
        }}
      >
        {/* Section header with view toggle */}
        <div
          className="flex items-center justify-between px-5 py-3.5"
          style={{ borderBottom: `1px solid ${isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.07)'}` }}
        >
          <h2 className="text-[13px] font-semibold" style={{ color: isLight ? '#1a2335' : '#d8e4f5' }}>
            Recent Estimates
          </h2>
          <div className="flex items-center gap-2">
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
                    : { background: 'transparent', border: `1px solid ${isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)'}`, color: isLight ? '#7890aa' : '#3a4f6a' }
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
                    : { background: 'transparent', border: `1px solid ${isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)'}`, color: isLight ? '#7890aa' : '#3a4f6a' }
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
            <Link
              href="/projects"
              className="text-[12px] font-medium transition-colors"
              style={{ color: isLight ? '#4a8a10' : '#a1d67c' }}
            >
              View all projects →
            </Link>
          </div>
        </div>

        {error && (
          <div className="px-5 py-4 text-[13px]" style={{ color: '#f05252' }}>
            {error}
          </div>
        )}

        {view === 'table' ? (
          <div className={`overflow-x-auto${loading ? ' opacity-50 pointer-events-none' : ''}`}>
            <table className="w-full text-[13px]">
              <thead>
                <tr style={{ borderBottom: `1px solid ${isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.06)'}` }}>
                  {['Project', 'Scopes', 'Total', 'Confidence', 'Status', 'Date', ''].map(
                    (col, i) => (
                      <th
                        key={i}
                        className={`px-4 py-2.5 text-[10px] font-semibold uppercase tracking-[0.09em] ${
                          col === 'Total' ? 'text-right' : 'text-left'
                        }`}
                        style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}
                      >
                        {col}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody>
                {estimates.map((est) => {
                  const st = STATUS_STYLES[est.status] ?? STATUS_STYLES.draft
                  return (
                    <tr
                      key={est.id}
                      className="group transition-colors"
                      style={{ borderBottom: `1px solid ${isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.04)'}` }}
                      onMouseEnter={(e) =>
                        ((e.currentTarget as HTMLTableRowElement).style.background =
                          isLight ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.025)')
                      }
                      onMouseLeave={(e) =>
                        ((e.currentTarget as HTMLTableRowElement).style.background = 'transparent')
                      }
                    >
                      <td className="px-4 py-2.5">
                        <p className="font-medium" style={{ color: isLight ? '#1a2335' : '#d8e4f5' }}>
                          {est.project_name}
                        </p>
                        <p className="text-[11px] mt-0.5" style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}>
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
                      <td className="px-4 py-2.5 text-right tabular-nums font-semibold"
                        style={{
                          fontFamily: 'var(--font-jetbrains-mono), monospace',
                          color: isLight ? '#1a2335' : '#d8e4f5',
                        }}
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
                        style={{
                          color: isLight ? '#7890aa' : '#3a4f6a',
                          fontFamily: 'var(--font-jetbrains-mono), monospace',
                        }}
                      >
                        {est.created_at.slice(0, 10)}
                      </td>
                      <td className="px-4 py-2.5">
                        <Link
                          href={`/estimates/${est.id}`}
                          className="text-[12px] font-medium opacity-0 group-hover:opacity-100 transition-opacity"
                          style={{ color: isLight ? '#4a8a10' : '#a1d67c' }}
                        >
                          Review →
                        </Link>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className={`px-5 py-4${loading ? ' opacity-50 pointer-events-none' : ''}`}>
            <EstimateBoard estimates={estimates} />
          </div>
        )}
      </div>
    </div>
  )
}
