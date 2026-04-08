'use client'

import { mockEstimate } from '@/lib/mock-data'
import { EstimateSummary } from '@/components/estimates/EstimateSummary'
import { EstimateTable } from '@/components/estimates/EstimateTable'
import { ComparableProjects } from '@/components/estimates/ComparableProjects'
import { formatCurrency } from '@/lib/utils'

export default function EstimateDetailPage() {
  const estimate = mockEstimate

  const handleExport = () => {
    alert('Export to .xlsx — backend integration pending.')
  }

  const handleGenerateQuote = () => {
    alert('Generate quote PDF — backend integration pending.')
  }

  return (
    <div className="pb-24">
      <div className="px-8 py-8">
        {/* Breadcrumb */}
        <div
          className="flex items-center gap-1.5 text-[11px] mb-5"
          style={{
            color: '#3a4f6a',
            fontFamily: 'var(--font-jetbrains-mono), monospace',
          }}
        >
          <a
            href="/dashboard"
            className="transition-colors"
            style={{ color: '#3a4f6a' }}
            onMouseEnter={(e) => ((e.currentTarget as HTMLAnchorElement).style.color = '#6b82a0')}
            onMouseLeave={(e) => ((e.currentTarget as HTMLAnchorElement).style.color = '#3a4f6a')}
          >
            Dashboard
          </a>
          <span style={{ color: 'rgba(255,255,255,0.12)' }}>/</span>
          <span style={{ color: '#3a4f6a' }}>Estimates</span>
          <span style={{ color: 'rgba(255,255,255,0.12)' }}>/</span>
          <span style={{ color: '#6b82a0' }}>{estimate.id}</span>
        </div>

        {/* Summary */}
        <div className="mb-5">
          <EstimateSummary estimate={estimate} />
        </div>

        {/* Main grid */}
        <div className="flex gap-5">
          {/* Table */}
          <div className="flex-1 min-w-0">
            <EstimateTable scopes={estimate.scopes} />
          </div>

          {/* Sidebar */}
          <div className="w-72 flex-shrink-0 space-y-4">
            <ComparableProjects projects={estimate.comparable_projects} />

            {/* Notes card */}
            <div
              className="rounded-[8px] p-4"
              style={{
                background: '#131822',
                border: '1px solid rgba(255,255,255,0.08)',
              }}
            >
              <h3
                className="text-[10px] font-semibold uppercase tracking-[0.09em] mb-2.5"
                style={{ color: '#3a4f6a' }}
              >
                Estimate Notes
              </h3>
              <textarea
                placeholder="Add notes for this estimate..."
                rows={4}
                className="w-full text-[12px] resize-none rounded-[6px] p-2.5 transition-all focus:outline-none"
                style={{
                  background: '#0e1219',
                  border: '1px solid rgba(255,255,255,0.1)',
                  color: '#d8e4f5',
                }}
              />
            </div>

            {/* AI hint card */}
            <div
              className="rounded-[8px] p-4"
              style={{
                background: 'rgba(129,140,248,0.05)',
                border: '1px solid rgba(129,140,248,0.18)',
              }}
            >
              <div className="flex items-center gap-1.5 mb-2">
                <span
                  className="text-[9px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wide"
                  style={{ background: 'rgba(129,140,248,0.15)', color: '#818cf8', border: '1px solid rgba(129,140,248,0.25)' }}
                >
                  AI
                </span>
                <h3 className="text-[11px] font-semibold" style={{ color: '#818cf8' }}>
                  Model Notes
                </h3>
              </div>
              <p className="text-[11px] leading-relaxed" style={{ color: '#6b82a0' }}>
                AWP scope pricing is within 4% of the HCA Brandon comparable (2023). ACT pricing
                appears slightly high vs. market — consider verifying the T-bar grid inclusion.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Sticky export bar */}
      <div
        className="fixed bottom-0 left-56 right-0 px-8 py-3 flex items-center justify-between"
        style={{
          background: '#0e1219',
          borderTop: '1px solid rgba(255,255,255,0.08)',
          boxShadow: '0 -8px 32px rgba(0,0,0,0.4)',
        }}
      >
        <div className="flex items-center gap-5">
          <div>
            <p className="text-[10px] uppercase tracking-[0.09em] font-semibold" style={{ color: '#3a4f6a' }}>
              Estimated total
            </p>
            <p
              className="text-[20px] font-bold tabular-nums leading-tight"
              style={{
                fontFamily: 'var(--font-jetbrains-mono), monospace',
                color: '#a1d67c',
                letterSpacing: '-0.03em',
              }}
            >
              {formatCurrency(estimate.total_cost)}
            </p>
          </div>
          <div
            className="h-8 w-px"
            style={{ background: 'rgba(255,255,255,0.08)' }}
          />
          <div>
            <p className="text-[10px] uppercase tracking-[0.09em] font-semibold" style={{ color: '#3a4f6a' }}>
              Accepted scopes
            </p>
            <p
              className="text-[14px] font-semibold tabular-nums"
              style={{
                fontFamily: 'var(--font-jetbrains-mono), monospace',
                color: '#d8e4f5',
              }}
            >
              {estimate.scopes.filter((s) => s.is_accepted).length}
              <span style={{ color: '#3a4f6a' }}> / {estimate.scopes.length}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleExport}
            className="flex items-center gap-2 px-4 py-2 text-[13px] font-medium rounded-[6px] transition-all"
            style={{
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.12)',
              color: '#6b82a0',
            }}
            onMouseEnter={(e) => {
              const el = e.currentTarget as HTMLButtonElement
              el.style.background = 'rgba(255,255,255,0.08)'
              el.style.color = '#d8e4f5'
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget as HTMLButtonElement
              el.style.background = 'rgba(255,255,255,0.05)'
              el.style.color = '#6b82a0'
            }}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                d="M12 10v6m0 0l-3-3m3 3l3-3M3 17V7a2 2 0 0 1 2-2h6l2 2h6a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"
                strokeWidth="2"
              />
            </svg>
            Export Excel
          </button>
          <button
            onClick={handleGenerateQuote}
            className="flex items-center gap-2 px-4 py-2 text-[13px] font-semibold rounded-[6px] transition-all duration-100"
            style={{
              background: 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
              color: '#080b10',
              boxShadow: '0 0 20px rgba(161,214,124,0.2)',
            }}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z"
                strokeWidth="2"
              />
            </svg>
            Generate Quote
          </button>
        </div>
      </div>
    </div>
  )
}
