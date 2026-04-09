'use client'

import Link from 'next/link'
import { ScopeTypeBadge } from './ScopeTypeBadge'
import { ConfidenceBadge } from './ConfidenceBadge'
import { formatCurrency } from '@/lib/utils'
import type { ScopeType, ConfidenceLevel } from '@/lib/types'
import { useState } from 'react'
import { useTheme } from '@/components/ThemeProvider'

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
  const { theme } = useTheme()
  const isLight = theme === 'light'

  const cardBg = hovered
    ? (isLight ? '#eaf0f8' : '#1f2a3d')
    : (isLight ? '#ffffff' : '#1a2235')
  const cardBorder = hovered
    ? (isLight ? 'rgba(0,0,0,0.14)' : 'rgba(255,255,255,0.15)')
    : (isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)')
  const textPrimary = isLight ? '#0f1923' : '#d8e4f5'
  const textMuted = isLight ? '#7890aa' : '#3a4f6a'
  const dividerColor = isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.06)'

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
          background: cardBg,
          border: `1px solid ${cardBorder}`,
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
              color: textPrimary,
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
              color: isLight ? '#4a8a10' : '#a1d67c',
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
            color: textMuted,
            margin: '2px 0 0 0',
          }}
        >
          {gc_name ?? '—'}
        </p>

        {/* Divider */}
        <div
          style={{
            height: '1px',
            background: dividerColor,
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
                color: textMuted,
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
                color: textPrimary,
                fontFamily: 'var(--font-jetbrains-mono), monospace',
                margin: 0,
                fontVariantNumeric: 'tabular-nums',
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
