'use client'

import Link from 'next/link'
import { ScopeTypeBadge } from './ScopeTypeBadge'
import { ConfidenceBadge } from './ConfidenceBadge'
import { formatCurrency } from '@/lib/utils'
import type { ScopeType, ConfidenceLevel } from '@/lib/types'
import { useState } from 'react'

interface EstimateCardProps {
  id: string
  project_name: string
  gc_name: string | null
  scope_types: string[]
  total_cost: number | null
  confidence_level: string | null
  status: string
  created_at: string
}

export function EstimateCard({
  id,
  project_name,
  gc_name,
  scope_types,
  total_cost,
  confidence_level,
  created_at,
}: EstimateCardProps) {
  const [hovered, setHovered] = useState(false)

  return (
    <Link
      href={`/estimates/${id}`}
      style={{ textDecoration: 'none', cursor: 'pointer' }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div
        style={{
          borderRadius: '8px',
          background: hovered ? '#1f2a3d' : '#1a2235',
          border: `1px solid ${hovered ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.08)'}`,
          padding: '12px 14px',
          transition: 'border-color 0.15s, background 0.15s',
        }}
      >
        {/* Top row: project name + hover link */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '8px' }}>
          <p
            style={{
              fontSize: '13px',
              fontWeight: 600,
              color: '#d8e4f5',
              margin: 0,
              lineHeight: '1.3',
              flex: 1,
              minWidth: 0,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {project_name}
          </p>
          <span
            style={{
              fontSize: '11px',
              color: '#a1d67c',
              opacity: hovered ? 1 : 0,
              transition: 'opacity 0.15s',
              flexShrink: 0,
              whiteSpace: 'nowrap',
            }}
          >
            Review →
          </span>
        </div>

        {/* GC name */}
        <p
          style={{
            fontSize: '11px',
            color: '#3a4f6a',
            margin: '2px 0 0 0',
          }}
        >
          {gc_name ?? '—'}
        </p>

        {/* Divider */}
        <div
          style={{
            height: '1px',
            background: 'rgba(255,255,255,0.06)',
            margin: '8px 0',
          }}
        />

        {/* Bottom row */}
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: '8px' }}>
          {/* Left: scopes + date */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
              {scope_types.map((s) => (
                <ScopeTypeBadge key={s} type={s as ScopeType} />
              ))}
            </div>
            <p
              style={{
                fontSize: '10px',
                color: '#3a4f6a',
                marginTop: '6px',
                fontFamily: 'var(--font-jetbrains-mono), monospace',
              }}
            >
              {created_at.slice(0, 10)}
            </p>
          </div>

          {/* Right: cost + confidence */}
          <div style={{ textAlign: 'right', flexShrink: 0 }}>
            <p
              style={{
                fontSize: '13px',
                fontWeight: 600,
                color: '#d8e4f5',
                fontFamily: 'var(--font-jetbrains-mono), monospace',
                margin: 0,
                tabularNums: 'tabular-nums',
              } as React.CSSProperties}
            >
              {formatCurrency(total_cost)}
            </p>
            <div style={{ marginTop: '6px' }}>
              <ConfidenceBadge level={(confidence_level ?? 'low') as ConfidenceLevel} />
            </div>
          </div>
        </div>
      </div>
    </Link>
  )
}
