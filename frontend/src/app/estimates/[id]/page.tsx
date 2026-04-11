'use client'

import { useState, useEffect, useRef } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { EstimateSummary } from '@/components/estimates/EstimateSummary'
import { EstimateTable } from '@/components/estimates/EstimateTable'
import { ComparableProjects } from '@/components/estimates/ComparableProjects'
import { formatCurrency } from '@/lib/utils'
import { getEstimate, updateScope, exportEstimate, generateQuote, deleteScope, recordActual, deleteEstimate, updateEstimateStatus, saveEstimateNotes } from '@/lib/api'
import type { EstimateResponse, ScopeResponse, UpdateScopeRequest } from '@/lib/types'
import { useTheme } from '@/components/ThemeProvider'
import { CatalogEntryModal } from '@/components/estimates/CatalogEntryModal'

export default function EstimateDetailPage() {
  const params = useParams<{ id: string }>()
  const id = params.id
  const router = useRouter()
  const { theme } = useTheme()
  const isLight = theme === 'light'

  const [estimate, setEstimate] = useState<EstimateResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [quoteLoading, setQuoteLoading] = useState(false)
  const [quoteSuccess, setQuoteSuccess] = useState<string | null>(null)
  const [quoteTemplate, setQuoteTemplate] = useState<'T-004A' | 'T-004B' | 'T-004E'>('T-004B')
  // Actuals panel state
  const [actualsOpen, setActualsOpen] = useState(false)
  const [actualCost, setActualCost] = useState('')
  const [actualDate, setActualDate] = useState('')
  const [actualNote, setActualNote] = useState('')
  const [actualsLoading, setActualsLoading] = useState(false)
  const [actualsError, setActualsError] = useState<string | null>(null)

  // Unknown-product banner + Add to Catalog modal state
  const [unknownBannerDismissed, setUnknownBannerDismissed] = useState(false)
  const [catalogModalScope, setCatalogModalScope] = useState<ScopeResponse | null>(null)
  const [catalogModalOpen, setCatalogModalOpen] = useState(false)
  const [catalogToast, setCatalogToast] = useState<string | null>(null)

  // Status bar state
  const [statusChanging, setStatusChanging] = useState(false)
  const [statusError, setStatusError] = useState<string | null>(null)

  // Estimate notes — local state synced from estimate, debounce-saved on change
  const [notes, setNotes] = useState('')
  const notesSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const loadEstimate = (estimateId: string) => {
    setLoading(true)
    setError(null)
    getEstimate(estimateId)
      .then((data) => {
        setEstimate(data)
        setNotes(data.notes ?? '')
        setLoading(false)
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Failed to load estimate')
        setLoading(false)
      })
  }

  const handleNotesChange = (value: string) => {
    setNotes(value)
    if (notesSaveTimer.current) clearTimeout(notesSaveTimer.current)
    notesSaveTimer.current = setTimeout(() => {
      saveEstimateNotes(id, value).catch(() => {})
    }, 800)
  }

  useEffect(() => {
    if (!id) return
    loadEstimate(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  const handleDeleteEstimate = async () => {
    if (!id) return
    if (!window.confirm('Delete this estimate?')) return
    try {
      await deleteEstimate(id)
      router.push('/estimates')
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : 'Failed to delete estimate')
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

  const handleRecordActual = async () => {
    if (!id || !actualCost || !actualDate) return
    setActualsLoading(true)
    setActualsError(null)
    try {
      const updated = await recordActual(id, {
        actual_total_cost: parseFloat(actualCost),
        actual_cost_date: actualDate,
        accuracy_note: actualNote || undefined,
      })
      setEstimate(updated)
      setActualsOpen(false)
    } catch (err: unknown) {
      setActualsError(err instanceof Error ? err.message : 'Failed to save actuals')
    } finally {
      setActualsLoading(false)
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

  const handleOpenCatalogModal = (scope: ScopeResponse) => {
    setCatalogModalScope(scope)
    setCatalogModalOpen(true)
  }

  const handleCatalogSaved = (productName: string) => {
    setCatalogModalOpen(false)
    setCatalogToast(`"${productName}" added to catalog`)
    setTimeout(() => setCatalogToast(null), 3500)
    // Re-fetch the estimate to update the unknown_products list
    if (id) loadEstimate(id)
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
    <>
    <div className="pb-24">
      <div className="px-4 py-6 md:px-8 md:py-8">
        {/* Breadcrumb + delete */}
        <div className="flex items-center justify-between mb-5">
          <div
            className="flex items-center gap-1.5 text-[11px]"
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
          <button
            onClick={handleDeleteEstimate}
            className="flex items-center gap-1.5 text-[12px] font-medium px-3 py-1.5 rounded-[6px] transition-all"
            style={{
              background: isLight ? 'rgba(239,68,68,0.07)' : 'rgba(239,68,68,0.08)',
              border: `1px solid ${isLight ? 'rgba(239,68,68,0.2)' : 'rgba(239,68,68,0.18)'}`,
              color: isLight ? '#dc2626' : '#f87171',
            }}
            onMouseEnter={(e) => {
              const el = e.currentTarget as HTMLButtonElement
              el.style.background = isLight ? 'rgba(239,68,68,0.13)' : 'rgba(239,68,68,0.14)'
              el.style.borderColor = isLight ? 'rgba(239,68,68,0.35)' : 'rgba(239,68,68,0.3)'
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget as HTMLButtonElement
              el.style.background = isLight ? 'rgba(239,68,68,0.07)' : 'rgba(239,68,68,0.08)'
              el.style.borderColor = isLight ? 'rgba(239,68,68,0.2)' : 'rgba(239,68,68,0.18)'
            }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
              <path d="M10 11v6M14 11v6" />
              <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
            </svg>
            Delete
          </button>
        </div>

        {/* ── Status transition bar ── */}
        {(() => {
          const STATUS_ORDER_PAGE = ['draft', 'reviewed', 'finalized', 'exported'] as const
          type PageStatus = typeof STATUS_ORDER_PAGE[number]
          const STATUS_LABELS: Record<PageStatus, string> = {
            draft: 'Draft',
            reviewed: 'Reviewed',
            finalized: 'Finalized',
            exported: 'Exported',
          }
          const STATUS_COLORS: Record<PageStatus, string> = {
            draft: isLight ? '#4a5e7a' : '#6b82a0',
            reviewed: '#60a5fa',
            finalized: '#a1d67c',
            exported: '#c084fc',
          }
          const STATUS_BG: Record<PageStatus, string> = {
            draft: isLight ? 'rgba(74,94,122,0.10)' : 'rgba(107,130,160,0.12)',
            reviewed: 'rgba(96,165,250,0.10)',
            finalized: 'rgba(161,214,124,0.10)',
            exported: 'rgba(192,132,252,0.10)',
          }
          const STATUS_BORDER: Record<PageStatus, string> = {
            draft: isLight ? 'rgba(74,94,122,0.2)' : 'rgba(107,130,160,0.2)',
            reviewed: 'rgba(96,165,250,0.25)',
            finalized: 'rgba(161,214,124,0.25)',
            exported: 'rgba(192,132,252,0.25)',
          }
          const FORWARD_LABELS: Partial<Record<PageStatus, string>> = {
            draft: 'Mark Reviewed',
            reviewed: 'Finalize',
            finalized: 'Mark Exported',
          }
          const currentStatus = (estimate.status ?? 'draft') as PageStatus
          const currentIdx = STATUS_ORDER_PAGE.indexOf(currentStatus)
          const prevStatus = currentIdx > 0 ? STATUS_ORDER_PAGE[currentIdx - 1] : null
          const nextStatus = currentIdx < STATUS_ORDER_PAGE.length - 1 ? STATUS_ORDER_PAGE[currentIdx + 1] : null
          const forwardLabel = nextStatus ? FORWARD_LABELS[currentStatus] : null

          const handleStatusTransition = async (targetStatus: string) => {
            if (!id) return
            setStatusChanging(true)
            setStatusError(null)
            try {
              await updateEstimateStatus(id, targetStatus)
              loadEstimate(id)
            } catch (err: unknown) {
              let msg = err instanceof Error ? err.message : 'Failed to update status'
              try {
                const jsonStart = msg.indexOf('{')
                if (jsonStart !== -1) {
                  const parsed = JSON.parse(msg.slice(jsonStart)) as { detail?: string }
                  if (parsed.detail) msg = parsed.detail
                }
              } catch { /* ignore */ }
              setStatusError(msg)
            } finally {
              setStatusChanging(false)
            }
          }

          return (
            <div style={{ marginBottom: '16px' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  flexWrap: 'wrap',
                }}
              >
                {/* Current status pill */}
                <span
                  style={{
                    fontSize: '12px',
                    fontWeight: 600,
                    padding: '4px 10px',
                    borderRadius: '6px',
                    color: STATUS_COLORS[currentStatus],
                    background: STATUS_BG[currentStatus],
                    border: `1px solid ${STATUS_BORDER[currentStatus]}`,
                    textTransform: 'capitalize',
                  }}
                >
                  {STATUS_LABELS[currentStatus]}
                </span>

                {/* Forward button */}
                {nextStatus && forwardLabel && (
                  <button
                    disabled={statusChanging}
                    onClick={() => void handleStatusTransition(nextStatus)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      fontSize: '13px',
                      fontWeight: 600,
                      padding: '5px 14px',
                      borderRadius: '6px',
                      border: 'none',
                      cursor: statusChanging ? 'wait' : 'pointer',
                      background: 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
                      color: '#080b10',
                      opacity: statusChanging ? 0.7 : 1,
                      transition: 'opacity 0.15s',
                    }}
                  >
                    {statusChanging ? (
                      <span
                        style={{
                          width: '12px',
                          height: '12px',
                          border: '2px solid rgba(0,0,0,0.3)',
                          borderTopColor: '#080b10',
                          borderRadius: '50%',
                          display: 'inline-block',
                          animation: 'spin 0.7s linear infinite',
                        }}
                      />
                    ) : '→'}
                    {forwardLabel}
                  </button>
                )}

                {/* Backward button */}
                {prevStatus && (
                  <button
                    disabled={statusChanging}
                    onClick={() => void handleStatusTransition(prevStatus)}
                    style={{
                      fontSize: '12px',
                      fontWeight: 500,
                      padding: '4px 10px',
                      borderRadius: '6px',
                      border: `1px solid ${isLight ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.1)'}`,
                      cursor: statusChanging ? 'wait' : 'pointer',
                      background: 'transparent',
                      color: isLight ? '#7890aa' : '#6b82a0',
                      opacity: statusChanging ? 0.5 : 1,
                      transition: 'opacity 0.15s',
                    }}
                  >
                    ← Back to {STATUS_LABELS[prevStatus]}
                  </button>
                )}
              </div>

              {/* Inline error */}
              {statusError && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    marginTop: '8px',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    background: 'rgba(245,158,11,0.08)',
                    border: '1px solid rgba(245,158,11,0.3)',
                    fontSize: '13px',
                    color: '#d97706',
                  }}
                >
                  <span style={{ flex: 1 }}>{statusError}</span>
                  <button
                    onClick={() => setStatusError(null)}
                    style={{
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      color: '#d97706',
                      fontSize: '14px',
                      padding: '0 2px',
                      opacity: 0.7,
                      lineHeight: 1,
                    }}
                  >
                    ×
                  </button>
                </div>
              )}

              <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
            </div>
          )
        })()}

        {/* Unknown-product banner */}
        {(() => {
          const unknownCount = estimate.scopes.filter((s) => s.unknown_product).length
          if (unknownCount === 0 || unknownBannerDismissed) return null
          return (
            <div
              className="flex items-center justify-between rounded-[8px] px-4 py-3 mb-4"
              style={{
                background: 'rgba(245,158,11,0.1)',
                border: '1px solid rgba(245,158,11,0.3)',
              }}
            >
              <div className="flex items-center gap-2">
                <span style={{ color: '#f59e0b', fontSize: '15px' }}>⚠</span>
                <span className="text-[13px] font-medium" style={{ color: '#f59e0b' }}>
                  {unknownCount} scope{unknownCount !== 1 ? 's' : ''} use{unknownCount === 1 ? 's' : ''} products not in the catalog. Verify pricing or add them.
                </span>
              </div>
              <button
                onClick={() => setUnknownBannerDismissed(true)}
                className="text-[12px] font-medium ml-4 flex-shrink-0"
                style={{ color: '#f59e0b', opacity: 0.7 }}
              >
                Dismiss
              </button>
            </div>
          )
        })()}

        {/* Summary */}
        <div className="mb-5">
          <EstimateSummary estimate={estimate} />
        </div>

        {/* Main grid */}
        <div className="flex flex-col md:flex-row gap-5">
          {/* Table */}
          <div className="flex-1 min-w-0 space-y-3">
            <EstimateTable
              estimateId={estimate.id}
              scopes={estimate.scopes}
              isLight={isLight}
              onScopesChange={handleScopesChange}
              onScopeUpdate={handleScopeUpdate}
              onScopeDelete={handleScopeDelete}
              onAddToCatalog={handleOpenCatalogModal}
            />
            {estimate.unknown_products && estimate.unknown_products.length > 0 && (
              <div
                className="rounded-[8px] px-4 py-3 flex items-start gap-2.5"
                style={{
                  background: 'rgba(245,158,11,0.08)',
                  border: '1px solid rgba(245,158,11,0.28)',
                }}
              >
                <span style={{ color: '#f59e0b', fontSize: '15px', lineHeight: '1.4', flexShrink: 0 }}>⚠</span>
                <div>
                  <span className="text-[13px] font-medium" style={{ color: '#f59e0b' }}>
                    Unknown products — these items aren&apos;t in the catalog and may affect pricing accuracy:
                  </span>
                  <span className="text-[13px] ml-1" style={{ color: '#d97706' }}>
                    {estimate.unknown_products.join(', ')}
                  </span>
                </div>
              </div>
            )}
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
                value={notes}
                onChange={(e) => handleNotesChange(e.target.value)}
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

      {/* ── Actuals panel ── */}
      {(estimate.status === 'finalized' || estimate.status === 'exported' || estimate.actual_total_cost != null) && (
        <div className="px-4 md:px-8 pb-4">
          <div
            className="rounded-[8px] overflow-hidden"
            style={{
              background: isLight ? '#ffffff' : '#131822',
              border: `1px solid ${isLight ? 'rgba(0,0,0,0.09)' : 'rgba(255,255,255,0.08)'}`,
            }}
          >
            {/* Panel header (always visible) */}
            <button
              className="w-full flex items-center justify-between px-5 py-3.5 transition-colors"
              style={{ borderBottom: actualsOpen || estimate.actual_total_cost != null ? `1px solid ${isLight ? 'rgba(0,0,0,0.07)' : 'rgba(255,255,255,0.06)'}` : 'none' }}
              onClick={() => setActualsOpen(!actualsOpen)}
            >
              <div className="flex items-center gap-2.5">
                <span
                  className="text-[9px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wide"
                  style={{ background: isLight ? 'rgba(61,112,16,0.12)' : 'rgba(161,214,124,0.12)', color: isLight ? '#3d7010' : '#a1d67c', border: `1px solid ${isLight ? 'rgba(61,112,16,0.2)' : 'rgba(161,214,124,0.2)'}` }}
                >
                  Actuals
                </span>
                <span className="text-[13px] font-semibold" style={{ color: isLight ? '#1a2335' : '#d8e4f5' }}>
                  {estimate.actual_total_cost != null ? 'Actual Cost Recorded' : 'Record Actual Cost'}
                </span>
              </div>
              <svg
                className="w-4 h-4 transition-transform"
                style={{ transform: actualsOpen ? 'rotate(180deg)' : 'rotate(0deg)', color: isLight ? '#7890aa' : '#3a4f6a' }}
                fill="none" stroke="currentColor" viewBox="0 0 24 24"
              >
                <path d="M19 9l-7 7-7-7" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>

            {/* Read-only card when actuals exist and panel is collapsed */}
            {estimate.actual_total_cost != null && !actualsOpen && (() => {
              const vp = estimate.variance_pct ?? 0
              const varColor = Math.abs(vp) <= 10
                ? (isLight ? '#3d7010' : '#a1d67c')
                : Math.abs(vp) <= 25
                  ? '#f59e0b'
                  : '#f05252'
              return (
                <div className="px-5 py-4 flex flex-wrap items-center gap-6">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.09em] font-semibold mb-0.5" style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}>Estimated</p>
                    <p className="text-[16px] font-bold tabular-nums" style={{ fontFamily: 'var(--font-jetbrains-mono), monospace', color: isLight ? '#1a2335' : '#d8e4f5' }}>
                      {estimate.total_cost != null ? `$${estimate.total_cost.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'}
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.09em] font-semibold mb-0.5" style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}>Actual</p>
                    <p className="text-[16px] font-bold tabular-nums" style={{ fontFamily: 'var(--font-jetbrains-mono), monospace', color: isLight ? '#1a2335' : '#d8e4f5' }}>
                      ${estimate.actual_total_cost.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.09em] font-semibold mb-0.5" style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}>Variance</p>
                    <p className="text-[16px] font-bold tabular-nums" style={{ fontFamily: 'var(--font-jetbrains-mono), monospace', color: varColor }}>
                      {vp > 0 ? '+' : ''}{vp.toFixed(1)}%
                    </p>
                  </div>
                  {estimate.actual_cost_date && (
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.09em] font-semibold mb-0.5" style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}>Completed</p>
                      <p className="text-[13px] tabular-nums" style={{ fontFamily: 'var(--font-jetbrains-mono), monospace', color: isLight ? '#1a2335' : '#d8e4f5' }}>
                        {estimate.actual_cost_date}
                      </p>
                    </div>
                  )}
                  {estimate.accuracy_note && (
                    <div className="flex-1 min-w-[160px]">
                      <p className="text-[10px] uppercase tracking-[0.09em] font-semibold mb-0.5" style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}>Notes</p>
                      <p className="text-[12px] leading-relaxed" style={{ color: isLight ? '#3a4f6a' : '#6b82a0' }}>{estimate.accuracy_note}</p>
                    </div>
                  )}
                  <button
                    className="text-[12px] font-medium ml-auto"
                    style={{ color: isLight ? '#4a8a10' : '#a1d67c' }}
                    onClick={() => { setActualCost(String(estimate.actual_total_cost)); setActualDate(estimate.actual_cost_date ?? ''); setActualNote(estimate.accuracy_note ?? ''); setActualsOpen(true) }}
                  >
                    Edit
                  </button>
                </div>
              )
            })()}

            {/* Form — visible when panel is open */}
            {actualsOpen && (
              <div className="px-5 py-4 space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-[10px] uppercase tracking-[0.09em] font-semibold mb-1.5" style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}>
                      Actual Total Cost ($)
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      placeholder="e.g. 48500.00"
                      value={actualCost}
                      onChange={(e) => setActualCost(e.target.value)}
                      className="w-full text-[13px] rounded-[6px] px-3 py-2 focus:outline-none"
                      style={{
                        background: isLight ? '#f5f7fa' : '#0e1219',
                        border: `1px solid ${isLight ? 'rgba(0,0,0,0.12)' : 'rgba(255,255,255,0.1)'}`,
                        color: isLight ? '#0f1923' : '#d8e4f5',
                        fontFamily: 'var(--font-jetbrains-mono), monospace',
                      }}
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] uppercase tracking-[0.09em] font-semibold mb-1.5" style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}>
                      Date Completed
                    </label>
                    <input
                      type="date"
                      value={actualDate}
                      onChange={(e) => setActualDate(e.target.value)}
                      className="w-full text-[13px] rounded-[6px] px-3 py-2 focus:outline-none"
                      style={{
                        background: isLight ? '#f5f7fa' : '#0e1219',
                        border: `1px solid ${isLight ? 'rgba(0,0,0,0.12)' : 'rgba(255,255,255,0.1)'}`,
                        color: isLight ? '#0f1923' : '#d8e4f5',
                        fontFamily: 'var(--font-jetbrains-mono), monospace',
                        colorScheme: isLight ? 'light' : 'dark',
                      }}
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] uppercase tracking-[0.09em] font-semibold mb-1.5" style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}>
                      Notes (optional)
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. Material overrun on ACT"
                      value={actualNote}
                      onChange={(e) => setActualNote(e.target.value)}
                      className="w-full text-[13px] rounded-[6px] px-3 py-2 focus:outline-none"
                      style={{
                        background: isLight ? '#f5f7fa' : '#0e1219',
                        border: `1px solid ${isLight ? 'rgba(0,0,0,0.12)' : 'rgba(255,255,255,0.1)'}`,
                        color: isLight ? '#0f1923' : '#d8e4f5',
                      }}
                    />
                  </div>
                </div>
                {actualsError && (
                  <p className="text-[12px]" style={{ color: '#f05252' }}>{actualsError}</p>
                )}
                <div className="flex items-center gap-3">
                  <button
                    onClick={handleRecordActual}
                    disabled={actualsLoading || !actualCost || !actualDate}
                    className="flex items-center gap-2 px-4 py-2 text-[13px] font-semibold rounded-[6px] transition-all duration-100"
                    style={{
                      background: actualsLoading || !actualCost || !actualDate
                        ? 'rgba(161,214,124,0.3)'
                        : 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
                      color: '#080b10',
                      cursor: actualsLoading || !actualCost || !actualDate ? 'not-allowed' : 'pointer',
                    }}
                  >
                    {actualsLoading ? 'Saving...' : 'Save Actuals'}
                  </button>
                  <button
                    onClick={() => setActualsOpen(false)}
                    className="text-[13px] font-medium"
                    style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

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

      {/* ── Add to Catalog toast ── */}
      {catalogToast && (
        <div
          className="fixed bottom-20 right-6 px-4 py-2.5 rounded-[8px] text-[13px] font-semibold shadow-lg z-50"
          style={{
            background: isLight ? '#ffffff' : '#1e2638',
            border: '1px solid rgba(245,158,11,0.4)',
            color: '#f59e0b',
            boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
          }}
        >
          ✓ {catalogToast}
        </div>
      )}

      {/* ── Add to Catalog modal (Phase 7.4) ── */}
      <CatalogEntryModal
        scope={catalogModalScope}
        isOpen={catalogModalOpen}
        onClose={() => setCatalogModalOpen(false)}
        onSaved={handleCatalogSaved}
        isLight={isLight}
      />
    </>
  )
}
