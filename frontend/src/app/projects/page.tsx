'use client'

import { useState, useMemo } from 'react'
import Link from 'next/link'
import { mockProjects } from '@/lib/mock-data'
import { formatCurrency, formatCurrencyFull, formatSF } from '@/lib/utils'
import { ScopeTypeBadge } from '@/components/estimates/ScopeTypeBadge'
import type { ScopeType } from '@/lib/types'

const ALL_GCS = ['All GCs', 'Skanska USA', 'Turner Construction', 'DPR Construction', 'Balfour Beatty', 'Hensel Phelps']
const ALL_SCOPES = ['All Scopes', 'ACT', 'AWP', 'FW', 'SM', 'WW', 'Baffles', 'RPG']
const ALL_YEARS = ['All Years', '2021', '2022', '2023', '2024']

const inputStyle: React.CSSProperties = {
  background: '#0e1219',
  border: '1px solid rgba(255,255,255,0.12)',
  color: '#d8e4f5',
  borderRadius: '6px',
  fontSize: '13px',
  padding: '8px 12px',
  outline: 'none',
}

const selectStyle: React.CSSProperties = {
  ...inputStyle,
  appearance: 'none',
  paddingRight: '28px',
  cursor: 'pointer',
}

export default function ProjectsPage() {
  const [gcFilter, setGcFilter] = useState('All GCs')
  const [scopeFilter, setScopeFilter] = useState('All Scopes')
  const [yearFilter, setYearFilter] = useState('All Years')
  const [search, setSearch] = useState('')

  const filtered = useMemo(() => {
    return mockProjects.filter((p) => {
      if (gcFilter !== 'All GCs' && p.gc_name !== gcFilter) return false
      if (scopeFilter !== 'All Scopes' && !p.scopes.some((s) => s.scope_type === scopeFilter)) return false
      if (yearFilter !== 'All Years' && p.quote_date && !p.quote_date.startsWith(yearFilter)) return false
      if (search.trim() && !p.folder_name.toLowerCase().includes(search.toLowerCase())) return false
      return true
    })
  }, [gcFilter, scopeFilter, yearFilter, search])

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
    <div className="px-8 py-8 max-w-7xl">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1
            className="text-[22px] font-semibold tracking-tight leading-tight"
            style={{ color: '#d8e4f5' }}
          >
            Projects
          </h1>
          <p className="text-[13px] mt-1" style={{ color: '#3a4f6a' }}>
            Historical project database · {mockProjects.length} projects total
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
      <div className="flex items-center gap-3 mb-5">
        {/* Search */}
        <div className="relative flex-1 max-w-xs">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5"
            style={{ color: '#3a4f6a' }}
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
        <div className="relative">
          <select
            value={scopeFilter}
            onChange={(e) => setScopeFilter(e.target.value)}
            style={selectStyle}
          >
            {ALL_SCOPES.map((s) => (
              <option key={s} value={s} style={{ background: '#0e1219', color: '#d8e4f5' }}>
                {s}
              </option>
            ))}
          </select>
          <svg
            className="absolute right-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 pointer-events-none"
            style={{ color: '#3a4f6a' }}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path d="M19 9l-7 7-7-7" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </div>

        {/* GC filter */}
        <div className="relative">
          <select
            value={gcFilter}
            onChange={(e) => setGcFilter(e.target.value)}
            style={selectStyle}
          >
            {ALL_GCS.map((g) => (
              <option key={g} value={g} style={{ background: '#0e1219', color: '#d8e4f5' }}>
                {g}
              </option>
            ))}
          </select>
          <svg
            className="absolute right-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 pointer-events-none"
            style={{ color: '#3a4f6a' }}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path d="M19 9l-7 7-7-7" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </div>

        {/* Year filter */}
        <div className="relative">
          <select
            value={yearFilter}
            onChange={(e) => setYearFilter(e.target.value)}
            style={selectStyle}
          >
            {ALL_YEARS.map((y) => (
              <option key={y} value={y} style={{ background: '#0e1219', color: '#d8e4f5' }}>
                {y}
              </option>
            ))}
          </select>
          <svg
            className="absolute right-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 pointer-events-none"
            style={{ color: '#3a4f6a' }}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path d="M19 9l-7 7-7-7" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </div>

        {hasActiveFilter && (
          <button
            onClick={clearFilters}
            className="text-[12px] font-medium transition-colors"
            style={{ color: '#3a4f6a' }}
            onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.color = '#a1d67c')}
            onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.color = '#3a4f6a')}
          >
            Clear filters ×
          </button>
        )}
      </div>

      {/* Summary row */}
      <div className="flex items-center gap-5 mb-4">
        <span className="text-[12px]" style={{ color: '#3a4f6a' }}>
          Showing{' '}
          <span className="font-semibold" style={{ color: '#6b82a0' }}>
            {filtered.length}
          </span>{' '}
          of {mockProjects.length} projects
        </span>
        {avgCostPerSF != null && (
          <span
            className="text-[12px] tabular-nums"
            style={{ color: '#3a4f6a', fontFamily: 'var(--font-jetbrains-mono), monospace' }}
          >
            Avg $/SF:{' '}
            <span style={{ color: '#6b82a0', fontWeight: 600 }}>
              {formatCurrencyFull(avgCostPerSF)}
            </span>
          </span>
        )}
        <span
          className="text-[12px] tabular-nums"
          style={{ color: '#3a4f6a', fontFamily: 'var(--font-jetbrains-mono), monospace' }}
        >
          Total:{' '}
          <span style={{ color: '#6b82a0', fontWeight: 600 }}>{formatCurrency(totalValue)}</span>
        </span>
      </div>

      {/* Table */}
      <div
        className="rounded-[8px] overflow-hidden"
        style={{
          background: '#131822',
          border: '1px solid rgba(255,255,255,0.08)',
        }}
      >
        <table className="w-full text-[13px]">
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
              {[
                { label: 'Project / Folder', align: 'left' },
                { label: 'GC', align: 'left' },
                { label: 'Scopes', align: 'left' },
                { label: 'Total SF', align: 'right' },
                { label: 'Total Cost', align: 'right' },
                { label: 'Avg $/SF', align: 'right' },
                { label: 'Date', align: 'left' },
                { label: '', align: 'left' },
              ].map((col, i) => (
                <th
                  key={i}
                  className={`px-4 py-2.5 text-[10px] font-semibold uppercase tracking-[0.09em] ${
                    col.align === 'right' ? 'text-right' : 'text-left'
                  }`}
                  style={{ color: '#3a4f6a' }}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
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
                  style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}
                  onMouseEnter={(e) =>
                    ((e.currentTarget as HTMLTableRowElement).style.background =
                      'rgba(255,255,255,0.025)')
                  }
                  onMouseLeave={(e) =>
                    ((e.currentTarget as HTMLTableRowElement).style.background = 'transparent')
                  }
                >
                  <td className="px-4 py-2.5">
                    <p className="font-medium" style={{ color: '#d8e4f5' }}>
                      {project.folder_name}
                    </p>
                    {project.address && (
                      <p className="text-[11px] mt-0.5" style={{ color: '#3a4f6a' }}>
                        {project.address}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-2.5" style={{ color: '#6b82a0' }}>
                    {project.gc_name ?? '—'}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex flex-wrap gap-1">
                      {project.scopes.map((s, i) => (
                        <ScopeTypeBadge key={i} type={s.scope_type as ScopeType} />
                      ))}
                    </div>
                  </td>
                  <td
                    className="px-4 py-2.5 text-right tabular-nums"
                    style={{
                      fontFamily: 'var(--font-jetbrains-mono), monospace',
                      fontSize: '12px',
                      color: '#6b82a0',
                    }}
                  >
                    {totalSF > 0 ? formatSF(totalSF) : '—'}
                  </td>
                  <td
                    className="px-4 py-2.5 text-right tabular-nums font-semibold"
                    style={{
                      fontFamily: 'var(--font-jetbrains-mono), monospace',
                      color: '#d8e4f5',
                    }}
                  >
                    {formatCurrency(project.total_cost)}
                  </td>
                  <td
                    className="px-4 py-2.5 text-right tabular-nums"
                    style={{
                      fontFamily: 'var(--font-jetbrains-mono), monospace',
                      fontSize: '12px',
                      color: '#6b82a0',
                    }}
                  >
                    {avgCPS != null ? formatCurrencyFull(avgCPS) : '—'}
                  </td>
                  <td
                    className="px-4 py-2.5 tabular-nums"
                    style={{
                      fontFamily: 'var(--font-jetbrains-mono), monospace',
                      fontSize: '11px',
                      color: '#3a4f6a',
                    }}
                  >
                    {project.quote_date ?? '—'}
                  </td>
                  <td className="px-4 py-2.5">
                    <Link
                      href={`/projects/${project.id}`}
                      className="text-[12px] font-medium opacity-0 group-hover:opacity-100 transition-opacity"
                      style={{ color: '#a1d67c' }}
                    >
                      View →
                    </Link>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>

        {filtered.length === 0 && (
          <div className="py-16 text-center">
            <p className="text-[13px]" style={{ color: '#3a4f6a' }}>
              No projects match the current filters
            </p>
            <button
              onClick={clearFilters}
              className="mt-2 text-[12px] font-medium transition-colors"
              style={{ color: '#3a4f6a' }}
              onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.color = '#a1d67c')}
              onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.color = '#3a4f6a')}
            >
              Clear all filters
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
