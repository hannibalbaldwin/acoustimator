'use client'

import { useState } from 'react'
import { formatCurrency, formatCurrencyFull } from '@/lib/utils'
import { ScopeTypeBadge } from './ScopeTypeBadge'
import type { ComparableProject } from '@/lib/types'

interface ComparableProjectsProps {
  projects: ComparableProject[]
  isLight?: boolean
}

export function ComparableProjects({ projects, isLight }: ComparableProjectsProps) {
  const [open, setOpen] = useState(true)

  return (
    <div
      className="rounded-[8px] overflow-hidden"
      style={{
        background: isLight ? '#ffffff' : '#131822',
        border: `1px solid ${isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)'}`,
      }}
    >
      {/* Header */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 transition-colors"
        style={{ borderBottom: open ? `1px solid ${isLight ? 'rgba(0,0,0,0.07)' : 'rgba(255,255,255,0.07)'}` : 'none' }}
        onMouseEnter={(e) =>
          ((e.currentTarget as HTMLButtonElement).style.background = isLight ? 'rgba(0,0,0,0.02)' : 'rgba(255,255,255,0.02)')
        }
        onMouseLeave={(e) =>
          ((e.currentTarget as HTMLButtonElement).style.background = 'transparent')
        }
      >
        <div className="flex items-center gap-2">
          <h3 className="text-[12px] font-semibold" style={{ color: isLight ? '#0f1923' : '#d8e4f5' }}>
            Comparable Projects
          </h3>
          <span
            className="text-[10px] px-1.5 py-0.5 rounded-[3px] font-mono font-semibold"
            style={{ color: isLight ? '#4a5e7a' : '#6b82a0', background: 'rgba(107,130,160,0.12)' }}
          >
            {projects.length}
          </span>
        </div>
        <svg
          className="w-3.5 h-3.5 transition-transform"
          style={{
            color: isLight ? '#7890aa' : '#3a4f6a',
            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
          }}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path d="M19 9l-7 7-7-7" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>

      {open && (
        <div className="divide-y" style={{ borderColor: isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.05)' }}>
          {projects.map((p) => (
            <div key={p.id} className="px-4 py-3">
              {/* Project name + similarity */}
              <div className="flex items-start justify-between gap-2 mb-2">
                <p
                  className="text-[12px] font-medium leading-tight"
                  style={{ color: isLight ? '#0f1923' : '#d8e4f5' }}
                >
                  {p.folder_name}
                </p>
                {p.similarity_score != null && (
                  <span
                    className="text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded-[3px] flex-shrink-0"
                    style={{
                      color: '#a1d67c',
                      background: 'rgba(161,214,124,0.10)',
                      border: '1px solid rgba(161,214,124,0.18)',
                    }}
                  >
                    {Math.round(p.similarity_score * 100)}%
                  </span>
                )}
              </div>

              {/* Scope badge + year */}
              <div className="flex items-center gap-2 mb-2">
                <ScopeTypeBadge type={p.scope_type} />
                {p.year != null && (
                  <span
                    className="text-[11px] tabular-nums"
                    style={{ color: isLight ? '#7890aa' : '#3a4f6a', fontFamily: 'var(--font-jetbrains-mono), monospace' }}
                  >
                    {p.year}
                  </span>
                )}
              </div>

              {/* Cost metrics */}
              <div className="flex items-center gap-4">
                {p.total_cost != null && (
                  <div>
                    <p
                      className="text-[10px] uppercase tracking-wide font-semibold"
                      style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}
                    >
                      Total
                    </p>
                    <p
                      className="text-[12px] font-semibold tabular-nums"
                      style={{
                        color: isLight ? '#0f1923' : '#d8e4f5',
                        fontFamily: 'var(--font-jetbrains-mono), monospace',
                      }}
                    >
                      {formatCurrency(p.total_cost)}
                    </p>
                  </div>
                )}
                {p.cost_per_sf != null && (
                  <div>
                    <p
                      className="text-[10px] uppercase tracking-wide font-semibold"
                      style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}
                    >
                      $/SF
                    </p>
                    <p
                      className="text-[12px] font-semibold tabular-nums"
                      style={{
                        color: isLight ? '#0f1923' : '#d8e4f5',
                        fontFamily: 'var(--font-jetbrains-mono), monospace',
                      }}
                    >
                      {formatCurrencyFull(p.cost_per_sf)}
                    </p>
                  </div>
                )}
              </div>
            </div>
          ))}

          {projects.length === 0 && (
            <div className="px-4 py-6 text-center">
              <p className="text-[12px]" style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}>
                No comparable projects found
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
