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
      {/* Content */}
      <div className="px-8 py-8">
        {/* Breadcrumb */}
        <div className="flex items-center gap-1.5 text-xs text-zinc-400 mb-5 font-mono">
          <a href="/dashboard" className="hover:text-zinc-700">Dashboard</a>
          <span>/</span>
          <span className="text-zinc-600">Estimates</span>
          <span>/</span>
          <span className="text-zinc-800 font-medium">{estimate.id}</span>
        </div>

        {/* Summary */}
        <div className="mb-6">
          <EstimateSummary estimate={estimate} />
        </div>

        {/* Main grid */}
        <div className="flex gap-5">
          {/* Table — main content */}
          <div className="flex-1 min-w-0">
            <EstimateTable scopes={estimate.scopes} />
          </div>

          {/* Sidebar */}
          <div className="w-72 flex-shrink-0 space-y-4">
            <ComparableProjects projects={estimate.comparable_projects} />

            {/* Notes card */}
            <div className="bg-white border border-zinc-200 rounded-lg p-4">
              <h3 className="text-xs font-semibold text-zinc-600 uppercase tracking-wide mb-2">
                Estimate Notes
              </h3>
              <textarea
                placeholder="Add notes for this estimate..."
                className="w-full text-xs text-zinc-700 border border-zinc-200 rounded p-2 resize-none focus:outline-none focus:ring-1 focus:ring-blue-500 placeholder:text-zinc-400"
                rows={4}
              />
            </div>

            {/* AI hint card */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-center gap-1.5 mb-2">
                <span className="text-[10px] font-semibold bg-blue-600 text-white px-1.5 py-0.5 rounded uppercase tracking-wide">
                  AI
                </span>
                <h3 className="text-xs font-semibold text-blue-800">Model Notes</h3>
              </div>
              <p className="text-[11px] text-blue-700 leading-relaxed">
                AWP scope pricing is within 4% of the HCA Brandon comparable (2023). ACT pricing
                appears slightly high vs. market — consider verifying the T-bar grid inclusion.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Sticky export bar */}
      <div className="fixed bottom-0 left-56 right-0 bg-white border-t border-zinc-200 px-8 py-3 flex items-center justify-between shadow-lg">
        <div className="flex items-center gap-4">
          <div>
            <p className="text-xs text-zinc-500">Estimated total</p>
            <p className="text-lg font-mono font-bold text-zinc-900 tabular-nums">
              {formatCurrency(estimate.total_cost)}
            </p>
          </div>
          <div className="h-8 w-px bg-zinc-200" />
          <div>
            <p className="text-xs text-zinc-500">Accepted scopes</p>
            <p className="text-sm font-mono font-semibold text-zinc-800">
              {estimate.scopes.filter((s) => s.is_accepted).length} / {estimate.scopes.length}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleExport}
            className="flex items-center gap-2 px-4 py-2 border border-zinc-300 text-zinc-700 text-sm font-medium rounded-lg hover:bg-zinc-50 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M12 10v6m0 0l-3-3m3 3l3-3M3 17V7a2 2 0 0 1 2-2h6l2 2h6a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" strokeWidth="2" />
            </svg>
            Export Excel (.xlsx)
          </button>
          <button
            onClick={handleGenerateQuote}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" strokeWidth="2" />
            </svg>
            Generate Quote
          </button>
        </div>
      </div>
    </div>
  )
}
