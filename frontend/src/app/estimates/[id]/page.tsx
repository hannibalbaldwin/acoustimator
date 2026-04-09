'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import { EstimateSummary } from '@/components/estimates/EstimateSummary'
import { EstimateTable } from '@/components/estimates/EstimateTable'
import { ComparableProjects } from '@/components/estimates/ComparableProjects'
import { formatCurrency } from '@/lib/utils'
import { getEstimate, updateScope, exportEstimate, generateQuote, deleteScope } from '@/lib/api'
import type { EstimateResponse, ScopeResponse, UpdateScopeRequest } from '@/lib/types'
import { useTheme } from '@/components/ThemeProvider'

export default function EstimateDetailPage() {
  const params = useParams<{ id: string }>()
  const id = params.id
  const { theme } = useTheme()
  const isLight = theme === 'light'

  const [estimate, setEstimate] = useState<EstimateResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [quoteLoading, setQuoteLoading] = useState(false)
  const [quoteSuccess, setQuoteSuccess] = useState<string | null>(null)
  const [quoteTemplate, setQuoteTemplate] = useState<'T-004A' | 'T-004B' | 'T-004E'>('T-004B')

  useEffect(() => {
    if (!id) return
    let cancelled = false
    getEstimate(id)
      .then((data) => {
        if (cancelled) return
        setEstimate(data)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load estimate')
        setLoading(false)
      })
    return () => { cancelled = true }
  }, [id])

  const handleScopesChange = (scopes: ScopeResponse[]) => {
    if (!estimate) return
    setEstimate({ ...estimate, scopes })
  }

  const handleScopeUpdate = async (scopeId: string, edits: {
    product_name: string
    area_sf: string
    material_cost_per_sf: string
    markup_pct: string
    labor_days: string
  }) => {
    if (!estimate) return
    setSaveError(null)
    const body: UpdateScopeRequest = {}
    if (edits.product_name) body.product_name = edits.product_name
    if (edits.area_sf) body.area_sf = parseFloat(edits.area_sf)
    if (edits.material_cost_per_sf) body.material_cost_per_sf = parseFloat(edits.material_cost_per_sf)
    if (edits.markup_pct) body.markup_pct = parseFloat(edits.markup_pct) / 100
    if (edits.labor_days) body.labor_days = parseFloat(edits.labor_days)

    try {
      const updated = await updateScope(estimate.id, scopeId, body)
      setEstimate(updated)
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save scope')
    }
  }

  const handleScopeDelete = async (scopeId: string) => {
    if (!estimate) return
    try {
      await deleteScope(estimate.id, scopeId)
    } catch {
      // Fire-and-forget — backend endpoint may not exist yet; don't surface the error
    }
  }

  const handleExport = async () => {
    if (!id) return
    try {
      await exportEstimate(id)
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : 'Export failed')
    }
  }

  const handleGenerateQuote = async () => {
    if (!id) return
    setQuoteLoading(true)
    setSaveError(null)
    setQuoteSuccess(null)
    try {
      await generateQuote(id, quoteTemplate)
      setQuoteSuccess('Quote downloaded')
      setTimeout(() => setQuoteSuccess(null), 4000)
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : 'Quote generation failed')
    } finally {
      setQuoteLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="px-4 py-6 md:px-8 md:py-8 animate-pulse">
        <div className="h-4 w-48 rounded mb-5" style={{ background: 'rgba(255,255,255,0.07)' }} />
        <div className="h-28 rounded-[8px] mb-5" style={{ background: 'rgba(255,255,255,0.05)' }} />
        <div className="flex gap-5">
          <div className="flex-1 h-64 rounded-[8px]" style={{ background: 'rgba(255,255,255,0.05)' }} />
          <div className="w-72 h-64 rounded-[8px]" style={{ background: 'rgba(255,255,255,0.05)' }} />
        </div>
      </div>
    )
  }

  if (error || !estimate) {
    return (
      <div className="px-4 py-6 md:px-8 md:py-8">
        <p className="text-[13px]" style={{ color: '#f05252' }}>
          {error ?? 'Estimate not found'}
        </p>
      </div>
    )
  }

  return (
    <div className="pb-24">
      <div className="px-4 py-6 md:px-8 md:py-8">
        {/* Breadcrumb */}
        <div
          className="flex items-center gap-1.5 text-[11px] mb-5"
          style={{
            color: isLight ? '#7890aa' : '#3a4f6a',
            fontFamily: 'var(--font-jetbrains-mono), monospace',
          }}
        >
          <a
            href="/dashboard"
            className="transition-colors"
            style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}
            onMouseEnter={(e) => ((e.currentTarget as HTMLAnchorElement).style.color = isLight ? '#4a6a8a' : '#6b82a0')}
            onMouseLeave={(e) => ((e.currentTarget as HTMLAnchorElement).style.color = isLight ? '#7890aa' : '#3a4f6a')}
          >
            Dashboard
          </a>
          <span style={{ color: isLight ? 'rgba(0,0,0,0.2)' : 'rgba(255,255,255,0.12)' }}>/</span>
          <span style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}>Estimates</span>
          <span style={{ color: isLight ? 'rgba(0,0,0,0.2)' : 'rgba(255,255,255,0.12)' }}>/</span>
          <span style={{ color: isLight ? '#4a6a8a' : '#6b82a0' }}>{estimate.id}</span>
        </div>

        {/* Summary */}
        <div className="mb-5">
          <EstimateSummary estimate={estimate} />
        </div>

        {/* Main grid */}
        <div className="flex flex-col md:flex-row gap-5">
          {/* Table */}
          <div className="flex-1 min-w-0">
            <EstimateTable
              scopes={estimate.scopes}
              isLight={isLight}
              onScopesChange={handleScopesChange}
              onScopeUpdate={handleScopeUpdate}
              onScopeDelete={handleScopeDelete}
            />
          </div>

          {/* Sidebar */}
          <div className="w-full md:w-72 flex-shrink-0 space-y-4">
            <ComparableProjects projects={estimate.comparable_projects} isLight={isLight} />

            {/* Notes card */}
            <div
              className="rounded-[8px] p-4"
              style={{
                background: isLight ? '#ffffff' : '#131822',
                border: `1px solid ${isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)'}`,
              }}
            >
              <h3
                className="text-[10px] font-semibold uppercase tracking-[0.09em] mb-2.5"
                style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}
              >
                Estimate Notes
              </h3>
              <textarea
                placeholder="Add notes for this estimate..."
                rows={4}
                className="w-full text-[12px] resize-none rounded-[6px] p-2.5 transition-all focus:outline-none"
                style={{
                  background: isLight ? '#f5f7fa' : '#0e1219',
                  border: `1px solid ${isLight ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.1)'}`,
                  color: isLight ? '#0f1923' : '#d8e4f5',
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
        className="fixed bottom-0 left-0 md:left-56 right-0 px-4 md:px-8 py-3 flex items-center justify-between"
        style={{
          background: isLight ? '#ffffff' : '#0e1219',
          borderTop: `1px solid ${isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)'}`,
          boxShadow: isLight ? '0 -8px 32px rgba(0,0,0,0.08)' : '0 -8px 32px rgba(0,0,0,0.4)',
        }}
      >
        <div className="flex items-center gap-5">
          <div>
            <p className="text-[10px] uppercase tracking-[0.09em] font-semibold" style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}>
              Estimated total
            </p>
            <p
              className="text-[20px] font-bold tabular-nums leading-tight"
              style={{
                fontFamily: 'var(--font-jetbrains-mono), monospace',
                color: isLight ? '#3d7010' : '#a1d67c',
                letterSpacing: '-0.03em',
              }}
            >
              {formatCurrency(estimate.total_cost)}
            </p>
          </div>
          <div
            className="h-8 w-px"
            style={{ background: isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)' }}
          />
          <div>
            <p className="text-[10px] uppercase tracking-[0.09em] font-semibold" style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}>
              Accepted scopes
            </p>
            <p
              className="text-[14px] font-semibold tabular-nums"
              style={{
                fontFamily: 'var(--font-jetbrains-mono), monospace',
                color: isLight ? '#0f1923' : '#d8e4f5',
              }}
            >
              {estimate.scopes.filter((s) => s.is_accepted).length}
              <span style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}> / {estimate.scopes.length}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {saveError && (
            <span className="text-[12px]" style={{ color: '#f05252' }}>{saveError}</span>
          )}
          {quoteSuccess && (
            <span className="text-[12px]" style={{ color: isLight ? '#3d7010' : '#a1d67c' }}>{quoteSuccess}</span>
          )}
          <button
            onClick={handleExport}
            className="flex items-center gap-2 px-4 py-2 text-[13px] font-medium rounded-[6px] transition-all"
            style={{
              background: isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.05)',
              border: `1px solid ${isLight ? 'rgba(0,0,0,0.12)' : 'rgba(255,255,255,0.12)'}`,
              color: isLight ? '#7890aa' : '#6b82a0',
            }}
            onMouseEnter={(e) => {
              const el = e.currentTarget as HTMLButtonElement
              el.style.background = isLight ? 'rgba(0,0,0,0.07)' : 'rgba(255,255,255,0.08)'
              el.style.color = isLight ? '#0f1923' : '#d8e4f5'
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget as HTMLButtonElement
              el.style.background = isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.05)'
              el.style.color = isLight ? '#7890aa' : '#6b82a0'
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

          {/* Template picker */}
          <div className="flex items-center gap-1">
            {(['T-004A', 'T-004B', 'T-004E'] as const).map((tpl) => (
              <button
                key={tpl}
                onClick={() => setQuoteTemplate(tpl)}
                className="text-[11px] font-medium px-2.5 py-1.5 rounded-[5px] transition-all"
                style={
                  quoteTemplate === tpl
                    ? isLight
                      ? { background: 'rgba(82,155,30,0.12)', border: '1px solid rgba(82,155,30,0.28)', color: '#3d7010' }
                      : { background: 'rgba(161,214,124,0.12)', border: '1px solid rgba(161,214,124,0.22)', color: '#a1d67c' }
                    : {
                        background: 'transparent',
                        border: `1px solid ${isLight ? 'rgba(0,0,0,0.10)' : 'rgba(255,255,255,0.08)'}`,
                        color: isLight ? '#7890aa' : '#3a4f6a',
                      }
                }
              >
                {tpl}
              </button>
            ))}
          </div>

          <button
            onClick={handleGenerateQuote}
            disabled={quoteLoading}
            className="flex items-center gap-2 px-4 py-2 text-[13px] font-semibold rounded-[6px] transition-all duration-100"
            style={{
              background: quoteLoading
                ? 'rgba(161,214,124,0.4)'
                : 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
              color: '#080b10',
              boxShadow: quoteLoading ? 'none' : '0 0 20px rgba(161,214,124,0.2)',
              cursor: quoteLoading ? 'not-allowed' : 'pointer',
            }}
          >
            {quoteLoading ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    d="M12 2a10 10 0 1 0 10 10"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                </svg>
                Generating...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z"
                    strokeWidth="2"
                  />
                </svg>
                Generate Quote
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
