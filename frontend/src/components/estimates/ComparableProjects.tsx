'use client'

import { useState } from 'react'
import type { ComparableProject } from '@/lib/types'
import { formatCurrency, formatCurrencyFull, formatSF, cn } from '@/lib/utils'
import { ScopeTypeBadge } from './ScopeTypeBadge'

interface ComparableProjectsProps {
  projects: ComparableProject[]
}

export function ComparableProjects({ projects }: ComparableProjectsProps) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="bg-white border border-zinc-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="flex items-center justify-between w-full px-4 py-3 border-b border-zinc-200 bg-zinc-50 hover:bg-zinc-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          <svg
            className="w-3.5 h-3.5 text-zinc-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              d="M9 19v-6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2zm0 0V9a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v10m-6 0a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2m0 0V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-2a2 2 0 0 1-2-2z"
              strokeWidth="2"
            />
          </svg>
          <h3 className="text-sm font-semibold text-zinc-800">Comparable Projects</h3>
          <span className="text-xs text-zinc-400">({projects.length})</span>
        </div>
        <svg
          className={cn('w-4 h-4 text-zinc-400 transition-transform', collapsed && 'rotate-180')}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path d="M5 15l7-7 7 7" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>

      {!collapsed && (
        <div className="divide-y divide-zinc-100">
          {projects.map((project) => (
            <div key={project.id} className="px-4 py-3 hover:bg-zinc-50 transition-colors">
              <div className="flex items-start justify-between gap-2 mb-1.5">
                <span className="text-xs font-medium text-zinc-800 leading-tight flex-1">
                  {project.folder_name}
                </span>
                <span
                  className={cn(
                    'text-[10px] font-mono px-1.5 py-0.5 rounded-full flex-shrink-0',
                    project.similarity_score >= 0.85
                      ? 'bg-green-100 text-green-700'
                      : project.similarity_score >= 0.75
                      ? 'bg-amber-100 text-amber-700'
                      : 'bg-zinc-100 text-zinc-600'
                  )}
                >
                  {Math.round(project.similarity_score * 100)}% match
                </span>
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                <ScopeTypeBadge type={project.scope_type} />
                {project.year && (
                  <span className="text-[11px] text-zinc-400 font-mono">{project.year}</span>
                )}
              </div>

              <div className="grid grid-cols-3 gap-2 mt-2">
                <div>
                  <p className="text-[10px] text-zinc-400 uppercase tracking-wide">SF</p>
                  <p className="text-xs font-mono text-zinc-700 font-medium">
                    {formatSF(project.area_sf)}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] text-zinc-400 uppercase tracking-wide">$/SF</p>
                  <p className="text-xs font-mono text-zinc-700 font-medium">
                    {formatCurrencyFull(project.cost_per_sf)}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] text-zinc-400 uppercase tracking-wide">Total</p>
                  <p className="text-xs font-mono text-zinc-700 font-medium">
                    {formatCurrency(project.total_cost)}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
