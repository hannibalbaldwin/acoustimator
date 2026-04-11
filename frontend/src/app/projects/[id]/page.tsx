'use client'

import React, { useState, useEffect, useMemo } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { getProject } from '@/lib/api'
import type { ProjectResponse, ProjectScopeSummary } from '@/lib/types'
import { useTheme } from '@/components/ThemeProvider'
import { ScopeTypeBadge } from '@/components/estimates/ScopeTypeBadge'
import { ProjectTypeBadge } from '@/components/ui/ProjectTypeBadge'
import { formatCurrency, formatCurrencyFull, formatSF } from '@/lib/utils'
import type { ScopeType } from '@/lib/types'
import { WaveformLoader } from '@/components/ui/WaveformLoader'

// ── Constants ─────────────────────────────────────────────────────────────────

const LABOR_RATE_PER_DAY = 725 // loaded rate per man-day

// ── Helpers ───────────────────────────────────────────────────────────────────

function groupScopesByType(scopes: ProjectScopeSummary[]): Map<string, ProjectScopeSummary[]> {
  const map = new Map<string, ProjectScopeSummary[]>()
  for (const scope of scopes) {
    const key = scope.scope_type ?? 'Other'
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(scope)
  }
  return map
}

function formatPctDisplay(value: number | null | undefined): string {
  if (value == null) return '—'
  // The API stores markup_pct as a ratio (e.g. 0.33) or as a percent integer — we display as %
  const pct = value > 1 ? value : value * 100
  return pct.toFixed(0) + '%'
}

// ── Sub-components ────────────────────────────────────────────────────────────

interface StatBlockProps {
  label: string
  value: string
  isLight: boolean
}

function StatBlock({ label, value, isLight }: StatBlockProps) {
  const textPrimary = isLight ? '#0f1923' : '#d8e4f5'
  const textMuted = isLight ? '#7890aa' : '#3a4f6a'
  return (
    <div className="flex flex-col gap-0.5">
      <span
        className="text-[10px] font-semibold uppercase tracking-[0.1em]"
        style={{ color: textMuted }}
      >
        {label}
      </span>
      <span
        className="text-[18px] font-semibold tabular-nums leading-tight"
        style={{
          color: textPrimary,
          fontFamily: 'var(--font-jetbrains-mono), monospace',
        }}
      >
        {value}
      </span>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>()
  const id = params.id
  const { theme } = useTheme()
  const isLight = theme === 'light'

  const [project, setProject] = useState<ProjectResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // ── Theme tokens ─────────────────────────────────────────────────────────
  const pageBg = isLight ? '#f5f7fa' : '#0b0f17'
  const cardBg = isLight ? '#ffffff' : '#131822'
  const borderOuter = isLight ? 'rgba(0,0,0,0.09)' : 'rgba(255,255,255,0.08)'
  const borderInner = isLight ? 'rgba(0,0,0,0.07)' : 'rgba(255,255,255,0.07)'
  const borderHairline = isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.05)'
  const textPrimary = isLight ? '#0f1923' : '#d8e4f5'
  const textSecondary = isLight ? '#4a5e7a' : '#6b82a0'
  const textMuted = isLight ? '#7890aa' : '#3a4f6a'
  const rowHoverBg = isLight ? 'rgba(0,0,0,0.025)' : 'rgba(255,255,255,0.02)'
  const subtotalBg = isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.04)'
  const groupHeaderBg = isLight ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.03)'
  const caGreen = isLight ? '#3d7010' : '#a1d67c'
  const ctaBg = 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)'

  // ── Fetch ─────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!id) return
    let cancelled = false
    setLoading(true)
    setNotFound(false)
    setError(null)

    getProject(id)
      .then((data) => {
        if (cancelled) return
        setProject(data)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const msg = err instanceof Error ? err.message : 'Failed to load project'
        if (msg.includes('404')) {
          setNotFound(true)
        } else {
          setError(msg)
        }
        setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [id])

  // ── Derived metrics ────────────────────────────────────────────────────────
  const derived = useMemo(() => {
    if (!project) return null

    const scopes = project.scopes ?? []
    const totalCost = project.total_cost ?? scopes.reduce((s, sc) => s + (sc.total ?? 0), 0)
    const totalSF = scopes.reduce((s, sc) => s + (sc.area_sf ?? 0), 0)
    const avgCostPerSF = totalSF > 0 && totalCost > 0 ? totalCost / totalSF : null

    // The schemas.py doesn't expose man_days on scopes, so we can't compute labor from that.
    // We approximate: labor = totalCost × 0.35 (industry thumb) when man_days unknown.
    // However if any scope has cost_per_sf we can derive material vs labor differently.
    // For now we show what we have and skip labor breakdown if data isn't present.

    return {
      totalCost,
      totalSF,
      avgCostPerSF,
      scopeCount: scopes.length,
      grouped: groupScopesByType(scopes),
    }
  }, [project])

  // ── Loading / error states ─────────────────────────────────────────────────
  if (loading) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ background: pageBg }}
      >
        <div className="flex flex-col items-center gap-3">
          <WaveformLoader variant="block" className="w-48" />
          <p className="text-[13px]" style={{ color: textMuted }}>
            Loading project…
          </p>
        </div>
      </div>
    )
  }

  if (notFound) {
    return (
      <div
        className="min-h-screen flex items-center justify-center px-6"
        style={{ background: pageBg }}
      >
        <div className="text-center max-w-sm">
          <p className="text-[32px] font-bold mb-2" style={{ color: textMuted }}>
            404
          </p>
          <p className="text-[15px] font-semibold mb-1" style={{ color: textPrimary }}>
            Project not found
          </p>
          <p className="text-[13px] mb-5" style={{ color: textMuted }}>
            This project doesn&apos;t exist or has been removed.
          </p>
          <Link
            href="/projects"
            className="inline-block px-4 py-2 text-[13px] font-semibold rounded-[6px] transition-all"
            style={{ background: ctaBg, color: '#080b10' }}
          >
            ← Back to Projects
          </Link>
        </div>
      </div>
    )
  }

  if (error || !project || !derived) {
    return (
      <div
        className="min-h-screen flex items-center justify-center px-6"
        style={{ background: pageBg }}
      >
        <div className="text-center max-w-sm">
          <p className="text-[15px] font-semibold mb-1" style={{ color: '#f05252' }}>
            Failed to load project
          </p>
          <p className="text-[13px] mb-5" style={{ color: textMuted }}>
            {error ?? 'Unknown error'}
          </p>
          <Link href="/projects" style={{ color: caGreen }} className="text-[13px] font-medium">
            ← Back to Projects
          </Link>
        </div>
      </div>
    )
  }

  const { totalCost, totalSF, avgCostPerSF, scopeCount, grouped } = derived
  const scopes = project.scopes ?? []

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div
      className="min-h-screen px-4 py-6 md:px-8 md:py-8 w-full max-w-screen-2xl"
      style={{ background: pageBg }}
    >
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 text-[12px] mb-5" style={{ color: textMuted }}>
        <Link
          href="/dashboard"
          className="transition-colors hover:underline"
          style={{ color: textMuted }}
          onMouseEnter={(e) => ((e.currentTarget as HTMLAnchorElement).style.color = caGreen)}
          onMouseLeave={(e) => ((e.currentTarget as HTMLAnchorElement).style.color = textMuted)}
        >
          Dashboard
        </Link>
        <span style={{ color: textMuted }}>/</span>
        <Link
          href="/projects"
          className="transition-colors hover:underline"
          style={{ color: textMuted }}
          onMouseEnter={(e) => ((e.currentTarget as HTMLAnchorElement).style.color = caGreen)}
          onMouseLeave={(e) => ((e.currentTarget as HTMLAnchorElement).style.color = textMuted)}
        >
          Projects
        </Link>
        <span style={{ color: textMuted }}>/</span>
        <span
          className="truncate max-w-[200px]"
          style={{ color: textSecondary }}
          title={project.name}
        >
          {project.name}
        </span>
      </nav>

      {/* Hero card */}
      <div
        className="rounded-[8px] p-5 mb-5"
        style={{
          background: cardBg,
          border: `1px solid ${borderOuter}`,
        }}
      >
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          {/* Title block */}
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <h1
                className="text-[22px] font-semibold tracking-tight leading-tight truncate"
                style={{ color: textPrimary }}
              >
                {project.name}
              </h1>
              <ProjectTypeBadge type={project.project_type} />
            </div>
            {project.gc_name && (
              <p className="text-[13px] mb-0.5" style={{ color: textSecondary }}>
                {project.gc_name}
              </p>
            )}
            {project.address && (
              <p className="text-[12px]" style={{ color: textMuted }}>
                {project.address}
              </p>
            )}
          </div>

          {/* Stat blocks */}
          <div
            className="flex flex-wrap gap-6 sm:gap-8 shrink-0 pt-1"
            style={{ borderLeft: `1px solid ${borderInner}`, paddingLeft: '24px' }}
          >
            <StatBlock
              label="Total Cost"
              value={formatCurrency(totalCost)}
              isLight={isLight}
            />
            <StatBlock
              label="Total SF"
              value={totalSF > 0 ? formatSF(totalSF) : '—'}
              isLight={isLight}
            />
            <StatBlock
              label="Scopes"
              value={String(scopeCount)}
              isLight={isLight}
            />
            <StatBlock
              label="Quote Date"
              value={project.quote_date ?? '—'}
              isLight={isLight}
            />
          </div>
        </div>
      </div>

      {/* Main content — 2-column */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-5">

        {/* Left: Scope Breakdown table */}
        <div
          className="rounded-[8px] overflow-hidden"
          style={{
            background: cardBg,
            border: `1px solid ${borderOuter}`,
          }}
        >
          <div className="px-5 py-3.5" style={{ borderBottom: `1px solid ${borderInner}` }}>
            <h2 className="text-[13px] font-semibold" style={{ color: textPrimary }}>
              Scope Breakdown
            </h2>
          </div>

          {scopes.length === 0 ? (
            <div className="py-12 text-center">
              <p className="text-[13px]" style={{ color: textMuted }}>
                No scopes recorded for this project.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr style={{ borderBottom: `1px solid ${borderHairline}` }}>
                    {['Scope Type', 'Product', 'SF', '$/SF', 'Total'].map((col, i) => (
                      <th
                        key={col}
                        className={`px-4 py-2.5 text-[10px] font-semibold uppercase tracking-[0.09em] ${
                          i >= 2 ? 'text-right' : 'text-left'
                        }`}
                        style={{ color: textMuted }}
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Array.from(grouped.entries()).map(([type, typeScopes]) => {
                    const showGroupHeader = grouped.size > 1 || typeScopes.length > 1
                    return (
                      <React.Fragment key={type}>
                        {showGroupHeader && (
                          <tr
                            key={`header-${type}`}
                            style={{ background: groupHeaderBg, borderBottom: `1px solid ${borderHairline}` }}
                          >
                            <td
                              colSpan={5}
                              className="px-4 py-1.5 text-[10px] font-semibold uppercase tracking-[0.1em]"
                              style={{ color: textMuted }}
                            >
                              {type}
                            </td>
                          </tr>
                        )}
                        {typeScopes.map((scope) => {
                          const sf = scope.area_sf
                          return (
                            <tr
                              key={scope.id}
                              className="transition-colors"
                              style={{ borderBottom: `1px solid ${borderHairline}` }}
                              onMouseEnter={(e) =>
                                ((e.currentTarget as HTMLTableRowElement).style.background = rowHoverBg)
                              }
                              onMouseLeave={(e) =>
                                ((e.currentTarget as HTMLTableRowElement).style.background = 'transparent')
                              }
                            >
                              <td className="px-4 py-2.5">
                                <ScopeTypeBadge type={scope.scope_type as ScopeType} />
                              </td>
                              <td className="px-4 py-2.5" style={{ color: textSecondary }}>
                                {scope.product_name ?? (
                                  <span style={{ color: textMuted }}>—</span>
                                )}
                              </td>
                              <td
                                className="px-4 py-2.5 text-right tabular-nums"
                                style={{
                                  fontFamily: 'var(--font-jetbrains-mono), monospace',
                                  fontSize: '12px',
                                  color: textSecondary,
                                }}
                              >
                                {sf != null && sf > 0 ? formatSF(sf) : '—'}
                              </td>
                              <td
                                className="px-4 py-2.5 text-right tabular-nums"
                                style={{
                                  fontFamily: 'var(--font-jetbrains-mono), monospace',
                                  fontSize: '12px',
                                  color: textSecondary,
                                }}
                              >
                                {scope.cost_per_sf != null ? formatCurrencyFull(scope.cost_per_sf) : '—'}
                              </td>
                              <td
                                className="px-4 py-2.5 text-right tabular-nums font-semibold"
                                style={{
                                  fontFamily: 'var(--font-jetbrains-mono), monospace',
                                  color: textPrimary,
                                }}
                              >
                                {formatCurrency(scope.total)}
                              </td>
                            </tr>
                          )
                        })}
                      </React.Fragment>
                    )
                  })}

                  {/* Subtotal row */}
                  <tr style={{ background: subtotalBg, borderTop: `1px solid ${borderInner}` }}>
                    <td
                      colSpan={2}
                      className="px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.06em]"
                      style={{ color: textMuted }}
                    >
                      Subtotal
                    </td>
                    <td
                      className="px-4 py-2.5 text-right tabular-nums text-[12px] font-semibold"
                      style={{
                        fontFamily: 'var(--font-jetbrains-mono), monospace',
                        color: textSecondary,
                      }}
                    >
                      {totalSF > 0 ? formatSF(totalSF) : '—'}
                    </td>
                    <td
                      className="px-4 py-2.5 text-right tabular-nums text-[12px] font-semibold"
                      style={{
                        fontFamily: 'var(--font-jetbrains-mono), monospace',
                        color: textSecondary,
                      }}
                    >
                      {avgCostPerSF != null ? formatCurrencyFull(avgCostPerSF) : '—'}
                    </td>
                    <td
                      className="px-4 py-2.5 text-right tabular-nums font-bold"
                      style={{
                        fontFamily: 'var(--font-jetbrains-mono), monospace',
                        color: textPrimary,
                      }}
                    >
                      {formatCurrency(totalCost)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right sidebar */}
        <div className="flex flex-col gap-4">

          {/* Project Info card */}
          <div
            className="rounded-[8px] p-5"
            style={{
              background: cardBg,
              border: `1px solid ${borderOuter}`,
            }}
          >
            <h3
              className="text-[11px] font-semibold uppercase tracking-[0.1em] mb-3"
              style={{ color: textMuted }}
            >
              Project Info
            </h3>
            <div className="flex flex-col gap-2.5">
              {[
                { label: 'Project Name', value: project.name },
                { label: 'General Contractor', value: project.gc_name },
                { label: 'Quote Date', value: project.quote_date },
                { label: 'Address', value: project.address },
                { label: 'Status', value: project.status },
              ].map(({ label, value }) =>
                value ? (
                  <div key={label} className="flex flex-col gap-0.5">
                    <span className="text-[10px] font-medium uppercase tracking-[0.08em]" style={{ color: textMuted }}>
                      {label}
                    </span>
                    <span className="text-[13px]" style={{ color: textSecondary }}>
                      {value}
                    </span>
                  </div>
                ) : null
              )}
              {project.project_type && (
                <div className="flex flex-col gap-0.5">
                  <span className="text-[10px] font-medium uppercase tracking-[0.08em]" style={{ color: textMuted }}>
                    Project Type
                  </span>
                  <ProjectTypeBadge type={project.project_type} />
                </div>
              )}
            </div>
          </div>

          {/* Cost Summary card */}
          <div
            className="rounded-[8px] p-5"
            style={{
              background: cardBg,
              border: `1px solid ${borderOuter}`,
            }}
          >
            <h3
              className="text-[11px] font-semibold uppercase tracking-[0.1em] mb-3"
              style={{ color: textMuted }}
            >
              Cost Summary
            </h3>
            <div className="flex flex-col gap-3">
              <CostRow
                label="Total Cost"
                value={formatCurrency(totalCost)}
                bold
                textPrimary={textPrimary}
                textMuted={textMuted}
              />
              <CostRow
                label="Avg $/SF"
                value={avgCostPerSF != null ? formatCurrencyFull(avgCostPerSF) : '—'}
                textPrimary={textPrimary}
                textMuted={textMuted}
              />
              <CostRow
                label="Total SF"
                value={totalSF > 0 ? formatSF(totalSF) : '—'}
                textPrimary={textPrimary}
                textMuted={textMuted}
              />
              <CostRow
                label="Scope Count"
                value={String(scopeCount)}
                textPrimary={textPrimary}
                textMuted={textMuted}
              />
              <div
                style={{
                  height: '1px',
                  background: borderHairline,
                  margin: '2px 0',
                }}
              />
              <div>
                <span
                  className="text-[10px] font-medium uppercase tracking-[0.08em] block mb-1"
                  style={{ color: textMuted }}
                >
                  Scope Types
                </span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {project.scope_types.length > 0 ? (
                    project.scope_types.map((st) => (
                      <ScopeTypeBadge key={st} type={st as ScopeType} />
                    ))
                  ) : (
                    <span style={{ color: textMuted, fontSize: '13px' }}>—</span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* CTA card */}
          <div
            className="rounded-[8px] p-5"
            style={{
              background: cardBg,
              border: `1px solid ${borderOuter}`,
            }}
          >
            <p className="text-[12px] mb-3" style={{ color: textMuted }}>
              Use this project as a comparable for a new estimate.
            </p>
            <Link
              href="/estimates/new"
              className="flex items-center justify-center gap-2 px-4 py-2.5 text-[13px] font-semibold rounded-[6px] transition-all duration-100 hover:scale-[1.01] w-full"
              style={{
                background: ctaBg,
                color: '#080b10',
                boxShadow: '0 0 16px rgba(161,214,124,0.18)',
              }}
            >
              Estimate Similar Project →
            </Link>
            <Link
              href="/projects"
              className="flex items-center justify-center mt-2 text-[12px] font-medium transition-colors"
              style={{ color: textMuted }}
              onMouseEnter={(e) => ((e.currentTarget as HTMLAnchorElement).style.color = caGreen)}
              onMouseLeave={(e) => ((e.currentTarget as HTMLAnchorElement).style.color = textMuted)}
            >
              ← Back to Projects
            </Link>
          </div>

        </div>
      </div>
    </div>
  )
}

// ── CostRow helper ─────────────────────────────────────────────────────────────

interface CostRowProps {
  label: string
  value: string
  bold?: boolean
  textPrimary: string
  textMuted: string
}

function CostRow({ label, value, bold, textPrimary, textMuted }: CostRowProps) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[12px]" style={{ color: textMuted }}>
        {label}
      </span>
      <span
        className={`text-[13px] tabular-nums ${bold ? 'font-bold' : 'font-medium'}`}
        style={{
          fontFamily: 'var(--font-jetbrains-mono), monospace',
          color: textPrimary,
        }}
      >
        {value}
      </span>
    </div>
  )
}
