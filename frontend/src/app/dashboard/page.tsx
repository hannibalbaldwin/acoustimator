import Link from 'next/link'
import { format } from 'date-fns'
import { StatCard } from '@/components/dashboard/StatCard'
import { CostTrendChart } from '@/components/dashboard/CostTrendChart'
import { ConfidenceBadge } from '@/components/estimates/ConfidenceBadge'
import { ScopeTypeBadge } from '@/components/estimates/ScopeTypeBadge'
import { mockDashboardEstimates, mockTrendData } from '@/lib/mock-data'
import { formatCurrency } from '@/lib/utils'
import type { ScopeType } from '@/lib/types'

const STATUS_STYLES: Record<string, string> = {
  draft: 'text-zinc-500 bg-zinc-100',
  reviewed: 'text-blue-700 bg-blue-100',
  finalized: 'text-green-700 bg-green-100',
  exported: 'text-purple-700 bg-purple-100',
}

export default function DashboardPage() {
  return (
    <div className="px-8 py-8 max-w-7xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-900">Dashboard</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            {format(new Date('2026-04-07'), 'MMMM d, yyyy')} — Commercial Acoustics, Tampa FL
          </p>
        </div>
        <Link
          href="/estimates/new"
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path d="M12 5v14M5 12h14" strokeWidth="2.5" strokeLinecap="round" />
          </svg>
          New Estimate
        </Link>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard
          label="Total Projects"
          value="124"
          delta={{ value: '12 this year', positive: true }}
        />
        <StatCard
          label="Active Estimates"
          value="7"
          delta={{ value: '3 awaiting review' }}
        />
        <StatCard
          label="Avg ACT Cost / SF"
          value="$4.05"
          delta={{ value: '+0.23 YoY', positive: true }}
        />
        <StatCard
          label="Total SF Estimated"
          value="5.4M"
          delta={{ value: '2026 YTD' }}
        />
      </div>

      {/* Trend chart */}
      <div className="mb-6">
        <CostTrendChart data={mockTrendData} />
      </div>

      {/* Recent estimates table */}
      <div className="bg-white border border-zinc-200 rounded-lg overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-zinc-200 bg-zinc-50">
          <h2 className="text-sm font-semibold text-zinc-800">Recent Estimates</h2>
          <Link
            href="/projects"
            className="text-xs text-blue-600 hover:text-blue-800 font-medium"
          >
            View all projects →
          </Link>
        </div>

        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-200">
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Project
              </th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Scopes
              </th>
              <th className="px-4 py-2.5 text-right text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Total
              </th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Confidence
              </th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Status
              </th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Date
              </th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {mockDashboardEstimates.map((est) => (
              <tr key={est.id} className="hover:bg-zinc-50 transition-colors group">
                <td className="px-4 py-2.5">
                  <div>
                    <p className="text-sm font-medium text-zinc-800">{est.project_name}</p>
                    <p className="text-xs text-zinc-400">{est.gc_name}</p>
                  </div>
                </td>
                <td className="px-4 py-2.5">
                  <div className="flex flex-wrap gap-1">
                    {est.scopes.map((s) => (
                      <ScopeTypeBadge key={s} type={s as ScopeType} />
                    ))}
                  </div>
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-sm font-semibold text-zinc-900 tabular-nums">
                  {formatCurrency(est.total_cost)}
                </td>
                <td className="px-4 py-2.5">
                  <ConfidenceBadge level={est.confidence_level} />
                </td>
                <td className="px-4 py-2.5">
                  <span
                    className={`text-xs px-2 py-0.5 rounded font-medium ${STATUS_STYLES[est.status] ?? ''}`}
                  >
                    {est.status.charAt(0).toUpperCase() + est.status.slice(1)}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-xs text-zinc-400 font-mono">{est.created_at}</td>
                <td className="px-4 py-2.5">
                  <Link
                    href={`/estimates/${est.id}`}
                    className="text-xs text-blue-600 hover:text-blue-800 font-medium opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    Review →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
