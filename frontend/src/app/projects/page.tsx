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
      p.scopes
        .filter((s) => s.cost_per_sf != null)
        .map((s) => s.cost_per_sf!)
    )
    if (!rows.length) return null
    return rows.reduce((a, b) => a + b, 0) / rows.length
  }, [filtered])

  const totalValue = useMemo(
    () => filtered.reduce((sum, p) => sum + (p.total_cost ?? 0), 0),
    [filtered]
  )

  return (
    <div className="px-8 py-8 max-w-7xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-900">Projects</h1>
          <p className="text-sm text-zinc-500 mt-0.5">Historical project database — {mockProjects.length} projects total</p>
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

      {/* Filter bar */}
      <div className="flex items-center gap-3 mb-5">
        <div className="relative flex-1 max-w-xs">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <circle cx="11" cy="11" r="8" strokeWidth="2" />
            <path d="M21 21l-4.35-4.35" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <input
            type="text"
            placeholder="Search projects..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-3 py-2 border border-zinc-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        <select
          value={scopeFilter}
          onChange={(e) => setScopeFilter(e.target.value)}
          className="border border-zinc-300 rounded-lg px-3 py-2 text-sm text-zinc-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
        >
          {ALL_SCOPES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>

        <select
          value={gcFilter}
          onChange={(e) => setGcFilter(e.target.value)}
          className="border border-zinc-300 rounded-lg px-3 py-2 text-sm text-zinc-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
        >
          {ALL_GCS.map((g) => (
            <option key={g} value={g}>{g}</option>
          ))}
        </select>

        <select
          value={yearFilter}
          onChange={(e) => setYearFilter(e.target.value)}
          className="border border-zinc-300 rounded-lg px-3 py-2 text-sm text-zinc-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
        >
          {ALL_YEARS.map((y) => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>

        {(gcFilter !== 'All GCs' || scopeFilter !== 'All Scopes' || yearFilter !== 'All Years' || search) && (
          <button
            onClick={() => { setGcFilter('All GCs'); setScopeFilter('All Scopes'); setYearFilter('All Years'); setSearch('') }}
            className="text-xs text-zinc-500 hover:text-zinc-800 underline font-medium"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Summary row */}
      <div className="flex items-center gap-5 mb-4">
        <span className="text-sm text-zinc-500">
          Showing <span className="font-semibold text-zinc-800">{filtered.length}</span> of {mockProjects.length} projects
        </span>
        {avgCostPerSF != null && (
          <span className="text-sm text-zinc-500 font-mono">
            Avg $/SF: <span className="font-semibold text-zinc-800">{formatCurrencyFull(avgCostPerSF)}</span>
          </span>
        )}
        <span className="text-sm text-zinc-500 font-mono">
          Total value: <span className="font-semibold text-zinc-800">{formatCurrency(totalValue)}</span>
        </span>
      </div>

      {/* Table */}
      <div className="bg-white border border-zinc-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-200 bg-zinc-50">
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Project / Folder
              </th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                GC
              </th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Scopes
              </th>
              <th className="px-4 py-2.5 text-right text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Total SF
              </th>
              <th className="px-4 py-2.5 text-right text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Total Cost
              </th>
              <th className="px-4 py-2.5 text-right text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Avg $/SF
              </th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Date
              </th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {filtered.map((project) => {
              const totalSF = project.scopes.reduce((s, sc) => s + (sc.area_sf ?? 0), 0)
              const avgCPS =
                project.scopes.filter((s) => s.cost_per_sf != null).length > 0
                  ? project.scopes
                      .filter((s) => s.cost_per_sf != null)
                      .reduce((a, s) => a + s.cost_per_sf!, 0) /
                    project.scopes.filter((s) => s.cost_per_sf != null).length
                  : null

              return (
                <tr key={project.id} className="hover:bg-zinc-50 transition-colors group">
                  <td className="px-4 py-2.5">
                    <p className="text-sm font-medium text-zinc-800">{project.folder_name}</p>
                    {project.address && (
                      <p className="text-xs text-zinc-400 mt-0.5">{project.address}</p>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-sm text-zinc-600">{project.gc_name ?? '—'}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex flex-wrap gap-1">
                      {project.scopes.map((s, i) => (
                        <ScopeTypeBadge key={i} type={s.scope_type as ScopeType} />
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-xs text-zinc-700">
                    {totalSF > 0 ? formatSF(totalSF) : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-sm font-semibold text-zinc-900 tabular-nums">
                    {formatCurrency(project.total_cost)}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-xs text-zinc-700">
                    {avgCPS != null ? formatCurrencyFull(avgCPS) : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-zinc-400 font-mono">
                    {project.quote_date ?? '—'}
                  </td>
                  <td className="px-4 py-2.5">
                    <Link
                      href={`/projects/${project.id}`}
                      className="text-xs text-blue-600 hover:text-blue-800 font-medium opacity-0 group-hover:opacity-100 transition-opacity"
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
            <p className="text-sm text-zinc-400">No projects match the current filters</p>
            <button
              onClick={() => { setGcFilter('All GCs'); setScopeFilter('All Scopes'); setYearFilter('All Years'); setSearch('') }}
              className="mt-2 text-xs text-blue-600 hover:underline"
            >
              Clear all filters
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
