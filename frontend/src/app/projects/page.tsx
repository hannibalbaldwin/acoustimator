'use client'

import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import Link from 'next/link'
import { formatCurrency, formatCurrencyFull, formatSF } from '@/lib/utils'
import { ScopeTypeBadge } from '@/components/estimates/ScopeTypeBadge'
import { FilterSelect } from '@/components/ui/FilterSelect'
import { listProjects, getProjectGcNames } from '@/lib/api'
import type { ProjectResponse, ScopeType } from '@/lib/types'
import { useTheme } from '@/components/ThemeProvider'
import { WaveformLoader } from '@/components/ui/WaveformLoader'

const ALL_SCOPES = ['All Scopes', 'ACT', 'AP', 'AWP', 'FW', 'SM', 'WW', 'Baffles', 'RPG']
const ALL_YEARS = ['All Years', '2026', '2025', '2024']
const PAGE_SIZE = 50

export default function ProjectsPage() {
  const { theme } = useTheme()
  const isLight = theme === 'light'

  const [gcFilter, setGcFilter] = useState('All GCs')
  const [scopeFilter, setScopeFilter] = useState('All Scopes')
  const [yearFilter, setYearFilter] = useState('All Years')
  const [search, setSearch] = useState('')
  const [gcOptions, setGcOptions] = useState<string[]>(['All GCs'])

  const [projects, setProjects] = useState<ProjectResponse[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const hasMore = projects.length < totalCount

  const sentinelRef = useRef<HTMLDivElement>(null)

  // Theme-aware colors
  const textPrimary = isLight ? '#0f1923' : '#d8e4f5'
  const textSubtitle = isLight ? '#5a7a9a' : '#3a4f6a'
  const textMuted = isLight ? '#7890aa' : '#3a4f6a'
  const textSecondary = isLight ? '#4a5e7a' : '#6b82a0'
  const tableBg = isLight ? '#ffffff' : '#131822'
  const inputBg = isLight ? '#f7f9fc' : '#0e1219'
  const borderDefault = isLight ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.12)'
  const borderHairline = isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.04)'
  const borderFaint = isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.06)'
  const tableBorderOuter = isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)'
  const rowHoverBg = isLight ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.025)'
  const clearFilterColor = isLight ? '#4a5e7a' : '#6b82a0'

  const inputStyle: React.CSSProperties = {
    background: inputBg,
    border: `1px solid ${borderDefault}`,
    color: textPrimary,
    borderRadius: '6px',
    fontSize: '13px',
    padding: '8px 12px',
    outline: 'none',
  }

  // Load GC names once on mount
  useEffect(() => {
    getProjectGcNames()
      .then((names) => setGcOptions(['All GCs', ...names]))
      .catch(() => {}) // non-fatal
  }, [])

  // Reset + reload when filters change
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setOffset(0)

    const params: Parameters<typeof listProjects>[0] = { limit: PAGE_SIZE, offset: 0 }
    if (scopeFilter !== 'All Scopes') params.scope_type = scopeFilter
    if (gcFilter !== 'All GCs') params.gc_name = gcFilter
    if (yearFilter !== 'All Years') params.year = yearFilter

    listProjects(params)
      .then((res) => {
        if (cancelled) return
        setProjects(res.items)
        setTotalCount(res.total)
        setOffset(res.items.length)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load projects')
        setLoading(false)
      })

    return () => { cancelled = true }
  }, [gcFilter, scopeFilter, yearFilter])

  // Load more — called by infinite scroll sentinel
  const loadMore = useCallback(() => {
    if (loadingMore || !hasMore) return
    setLoadingMore(true)

    const params: Parameters<typeof listProjects>[0] = { limit: PAGE_SIZE, offset }
    if (scopeFilter !== 'All Scopes') params.scope_type = scopeFilter
    if (gcFilter !== 'All GCs') params.gc_name = gcFilter
    if (yearFilter !== 'All Years') params.year = yearFilter

    listProjects(params)
      .then((res) => {
        setProjects((prev) => [...prev, ...res.items])
        setTotalCount(res.total)
        setOffset((prev) => prev + res.items.length)
        setLoadingMore(false)
      })
      .catch(() => setLoadingMore(false))
  }, [loadingMore, hasMore, offset, scopeFilter, gcFilter, yearFilter])

  // Infinite scroll via IntersectionObserver
  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return
    const observer = new IntersectionObserver(
      (entries) => { if (entries[0].isIntersecting) loadMore() },
      { rootMargin: '200px' }
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [loadMore])

  // Client-side search filter (applied on top of server-side results)
  const filtered = useMemo(() => {
    if (!search.trim()) return projects
    const q = search.toLowerCase()
    return projects.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        (p.gc_name ?? '').toLowerCase().includes(q)
    )
  }, [projects, search])

  const avgCostPerSF = useMemo(() => {
    const rows = filtered.flatMap((p) =>
      p.scopes.filter((s) => s.cost_per_sf != null).map((s) => s.cost_per_sf!)
    )
    if (!rows.length) return null
    return rows.reduce((a, b) => a + b, 0) / rows.length
  }, [filtered])

  const totalValue = useMemo(
    () => filtered.reduce((sum, p) => sum + (p.total_cost ?? 0), 0),
    [filtered]
  )

  const hasActiveFilter =
    gcFilter !== 'All GCs' || scopeFilter !== 'All Scopes' || yearFilter !== 'All Years' || !!search

  const clearFilters = () => {
    setGcFilter('All GCs')
    setScopeFilter('All Scopes')
    setYearFilter('All Years')
    setSearch('')
  }

  return (
    <div className="px-4 py-6 md:px-8 md:py-8 w-full max-w-screen-2xl">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1
            className="text-[22px] font-semibold tracking-tight leading-tight"
            style={{ color: textPrimary }}
          >
            Projects
          </h1>
          <p className="text-[13px] mt-1" style={{ color: textSubtitle }}>
            Historical project database · {totalCount} projects total
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

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-3 mb-5">
        {/* Search */}
        <div className="relative flex-1 max-w-xs">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5"
            style={{ color: textMuted }}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <circle cx="11" cy="11" r="8" strokeWidth="2" />
            <path d="M21 21l-4.35-4.35" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <input
            type="text"
            placeholder="Search projects..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ ...inputStyle, paddingLeft: '32px', width: '100%' }}
          />
        </div>

        {/* Scope filter */}
        <FilterSelect value={scopeFilter} onChange={setScopeFilter} options={ALL_SCOPES} />

        {/* GC filter — dynamic from DB */}
        <FilterSelect value={gcFilter} onChange={setGcFilter} options={gcOptions} />

        {/* Year filter */}
        <FilterSelect value={yearFilter} onChange={setYearFilter} options={ALL_YEARS} />

        {hasActiveFilter && (
          <button
            onClick={clearFilters}
            className="text-[12px] font-medium transition-colors"
            style={{ color: clearFilterColor }}
          >
            Clear filters ×
          </button>
        )}
      </div>

      {/* Summary row */}
      <div className="flex items-center gap-5 mb-4">
        <span className="text-[12px]" style={{ color: textMuted }}>
          Showing{' '}
          <span className="font-semibold" style={{ color: textSecondary }}>
            {search ? filtered.length : projects.length}
          </span>
          {search ? ` of ${projects.length}` : ''}{' '}
          of {totalCount} projects
        </span>
        {avgCostPerSF != null && (
          <span className="text-[12px] tabular-nums" style={{ color: textMuted, fontFamily: 'var(--font-jetbrains-mono), monospace' }}>
            Avg $/SF:{' '}
            <span style={{ color: textSecondary, fontWeight: 600 }}>{formatCurrencyFull(avgCostPerSF)}</span>
          </span>
        )}
        <span className="text-[12px] tabular-nums" style={{ color: textMuted, fontFamily: 'var(--font-jetbrains-mono), monospace' }}>
          Total:{' '}
          <span style={{ color: textSecondary, fontWeight: 600 }}>{formatCurrency(totalValue)}</span>
        </span>
      </div>

      {error && (
        <div className="mb-4 text-[13px]" style={{ color: '#f05252' }}>{error}</div>
      )}

      {/* Table */}
      {loading && projects.length > 0 && (
        <div className="flex justify-center mb-3">
          <WaveformLoader variant="inline" />
        </div>
      )}
      <div
        className={`rounded-[8px] overflow-x-auto ${loading ? 'opacity-40 pointer-events-none' : ''}`}
        style={{ background: tableBg, border: `1px solid ${tableBorderOuter}` }}
      >
        <table className="w-full text-[13px]">
          <thead>
            <tr style={{ borderBottom: `1px solid ${borderFaint}` }}>
              {[
                { label: 'Project / Folder', align: 'left' },
                { label: 'GC', align: 'left' },
                { label: 'Type', align: 'left' },
                { label: 'Scopes', align: 'left' },
                { label: 'Total SF', align: 'right' },
                { label: 'Total Cost', align: 'right' },
                { label: 'Avg $/SF', align: 'right' },
                { label: 'Date', align: 'left' },
                { label: '', align: 'left' },
              ].map((col, i) => (
                <th
                  key={i}
                  className={`px-4 py-2.5 text-[10px] font-semibold uppercase tracking-[0.09em] ${col.align === 'right' ? 'text-right' : 'text-left'}`}
                  style={{ color: textMuted }}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && projects.length === 0 && (
              <tr>
                <td colSpan={9}>
                  <WaveformLoader variant="block" />
                </td>
              </tr>
            )}
            {filtered.map((project) => {
              const totalSF = project.scopes.reduce((s, sc) => s + (sc.area_sf ?? 0), 0)
              const validScopes = project.scopes.filter((s) => s.cost_per_sf != null)
              const avgCPS =
                validScopes.length > 0
                  ? validScopes.reduce((a, s) => a + s.cost_per_sf!, 0) / validScopes.length
                  : null

              return (
                <tr
                  key={project.id}
                  className="group transition-colors"
                  style={{ borderBottom: `1px solid ${borderHairline}` }}
                  onMouseEnter={(e) => ((e.currentTarget as HTMLTableRowElement).style.background = rowHoverBg)}
                  onMouseLeave={(e) => ((e.currentTarget as HTMLTableRowElement).style.background = 'transparent')}
                >
                  <td className="px-4 py-2.5">
                    <p className="font-medium" style={{ color: textPrimary }}>{project.name}</p>
                    {project.address && (
                      <p className="text-[11px] mt-0.5" style={{ color: textMuted }}>{project.address}</p>
                    )}
                  </td>
                  <td className="px-4 py-2.5" style={{ color: (project.gc_name ? textSecondary : textMuted), fontSize: '12px' }}>
                    {project.gc_name ?? '—'}
                  </td>
                  <td className="px-4 py-2.5">
                    {project.project_type ? (
                      <span
                        className="text-[10px] px-2 py-0.5 rounded-[4px] font-medium uppercase tracking-wide"
                        style={{ color: textSecondary, background: isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.06)', border: `1px solid ${isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)'}` }}
                      >
                        {project.project_type.replace('_', ' ')}
                      </span>
                    ) : (
                      <span style={{ color: textMuted, fontSize: '12px' }}>—</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex flex-wrap gap-1">
                      {project.scope_types.map((s) => (
                        <ScopeTypeBadge key={s} type={s as ScopeType} />
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums" style={{ fontFamily: 'var(--font-jetbrains-mono), monospace', fontSize: '12px', color: textSecondary }}>
                    {totalSF > 0 ? formatSF(totalSF) : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums font-semibold" style={{ fontFamily: 'var(--font-jetbrains-mono), monospace', color: textPrimary }}>
                    {formatCurrency(project.total_cost)}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums" style={{ fontFamily: 'var(--font-jetbrains-mono), monospace', fontSize: '12px', color: textSecondary }}>
                    {avgCPS != null ? formatCurrencyFull(avgCPS) : '—'}
                  </td>
                  <td className="px-4 py-2.5 tabular-nums" style={{ fontFamily: 'var(--font-jetbrains-mono), monospace', fontSize: '11px', color: textMuted }}>
                    {project.quote_date ?? '—'}
                  </td>
                  <td className="px-4 py-2.5">
                    <Link
                      href={`/projects/${project.id}`}
                      className="text-[12px] font-medium opacity-0 group-hover:opacity-100 transition-opacity"
                      style={{ color: isLight ? '#4a8a10' : '#a1d67c' }}
                    >
                      View →
                    </Link>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>

        {!loading && filtered.length === 0 && (
          <div className="py-16 text-center">
            <p className="text-[13px]" style={{ color: textMuted }}>
              No projects match the current filters
            </p>
            {hasActiveFilter && (
              <button onClick={clearFilters} className="mt-2 text-[12px] font-medium" style={{ color: clearFilterColor }}>
                Clear all filters
              </button>
            )}
          </div>
        )}
      </div>

      {/* Infinite scroll sentinel + loading indicator */}
      <div ref={sentinelRef} className="h-1" />
      {loadingMore && (
        <div className="flex justify-center">
          <WaveformLoader variant="inline" />
        </div>
      )}
      {!loading && !loadingMore && hasMore && !search && (
        <p className="text-center text-[11px] mt-3" style={{ color: textMuted }}>
          Scroll to load more · {projects.length} of {totalCount} shown
        </p>
      )}
    </div>
  )
}
