'use client'

import Link from 'next/link'
import { ScopeTypeBadge } from './ScopeTypeBadge'
import { ConfidenceBadge } from './ConfidenceBadge'
import { formatCurrency } from '@/lib/utils'
import type { ScopeType } from '@/lib/types'
import { useState } from 'react'
import { useTheme } from '@/components/ThemeProvider'
import { useDraggable } from '@dnd-kit/core'

const STATUS_ORDER = ['draft', 'reviewed', 'finalized', 'exported'] as const

interface EstimateCardProps {
  id: string
  project_name: string
  gc_name: string | null
  scope_types: string[]
  total_cost: number | null
  confidence_level: string | null
  status: string
  created_at: string
  isDragging?: boolean
  onStatusChange?: (id: string, newStatus: string) => void
}

export function EstimateCard({
  id,
  project_name,
  gc_name,
  scope_types,
  total_cost,
  confidence_level,
  status,
  created_at,
  isDragging = false,
  onStatusChange,
}: EstimateCardProps) {
  const [hovered, setHovered] = useState(false)
  const [btnHovered, setBtnHovered] = useState<'prev' | 'next' | null>(null)
  const { theme } = useTheme()
  const isLight = theme === 'light'

  const { attributes, listeners, setNodeRef, transform } = useDraggable({ id })

  const currentIdx = STATUS_ORDER.indexOf(status as typeof STATUS_ORDER[number])
  const hasPrev = currentIdx > 0
  const hasNext = currentIdx < STATUS_ORDER.length - 1

  const prevStatus = hasPrev ? STATUS_ORDER[currentIdx - 1] : null
  const nextStatus = hasNext ? STATUS_ORDER[currentIdx + 1] : null

  const cardBg = hovered
    ? (isLight ? '#eaf0f8' : '#1f2a3d')
    : (isLight ? '#ffffff' : '#1a2235')
  const cardBorder = hovered
    ? (isLight ? 'rgba(0,0,0,0.14)' : 'rgba(255,255,255,0.15)')
    : (isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)')
  const textPrimary = isLight ? '#0f1923' : '#d8e4f5'
  const textMuted = isLight ? '#7890aa' : '#3a4f6a'
  const dividerColor = isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.06)'
  const chevronColor = isLight ? '#7890aa' : '#3a4f6a'

  // dnd-kit transform style
  const dragStyle: React.CSSProperties = transform
    ? {
        transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
        opacity: isDragging ? 0.5 : 1,
      }
    : { opacity: isDragging ? 0.5 : 1 }

  return (
    <div
      ref={setNodeRef}
      style={{ ...dragStyle, touchAction: 'none' }}
      {...attributes}
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
          cursor: 'grab',
        }}
        {...listeners}
      >
        {/* Top row: project name + hover link — Link wraps only this clickable part */}
        <Link
          href={`/estimates/${id}`}
          style={{ textDecoration: 'none', cursor: 'pointer' }}
          onClick={(e) => {
            // Prevent navigation if user was dragging
            if (isDragging) e.preventDefault()
          }}
          draggable={false}
        >
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
        </Link>

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
              <ConfidenceBadge level={(confidence_level ?? 'low') as 'high' | 'medium' | 'low'} />
            </div>
          </div>
        </div>

        {/* Status chevron row */}
        {onStatusChange && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              gap: '6px',
              marginTop: '8px',
              paddingTop: '6px',
              borderTop: `1px solid ${dividerColor}`,
              opacity: hovered ? 0.7 : 0,
              transition: 'opacity 0.15s',
            }}
          >
            <button
              title={prevStatus ? `Move to ${prevStatus}` : undefined}
              disabled={!hasPrev}
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                if (prevStatus) onStatusChange(id, prevStatus)
              }}
              onMouseDown={(e) => e.stopPropagation()}
              onMouseEnter={() => hasPrev && setBtnHovered('prev')}
              onMouseLeave={() => setBtnHovered(null)}
              style={{
                width: '20px',
                height: '20px',
                borderRadius: '4px',
                border: `1px solid ${btnHovered === 'prev' && hasPrev ? 'rgba(161,214,124,0.6)' : chevronColor}`,
                background: btnHovered === 'prev' && hasPrev ? 'rgba(161,214,124,0.12)' : 'transparent',
                color: btnHovered === 'prev' && hasPrev ? '#a1d67c' : chevronColor,
                fontSize: '12px',
                cursor: hasPrev ? 'pointer' : 'not-allowed',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: 0,
                opacity: hasPrev ? 1 : 0.3,
                lineHeight: 1,
                transition: 'background 0.1s, border-color 0.1s, color 0.1s',
              }}
            >
              ←
            </button>
            <button
              title={nextStatus ? `Move to ${nextStatus}` : undefined}
              disabled={!hasNext}
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                if (nextStatus) onStatusChange(id, nextStatus)
              }}
              onMouseDown={(e) => e.stopPropagation()}
              onMouseEnter={() => hasNext && setBtnHovered('next')}
              onMouseLeave={() => setBtnHovered(null)}
              style={{
                width: '20px',
                height: '20px',
                borderRadius: '4px',
                border: `1px solid ${btnHovered === 'next' && hasNext ? 'rgba(161,214,124,0.6)' : chevronColor}`,
                background: btnHovered === 'next' && hasNext ? 'rgba(161,214,124,0.12)' : 'transparent',
                color: btnHovered === 'next' && hasNext ? '#a1d67c' : chevronColor,
                fontSize: '12px',
                cursor: hasNext ? 'pointer' : 'not-allowed',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: 0,
                opacity: hasNext ? 1 : 0.3,
                lineHeight: 1,
                transition: 'background 0.1s, border-color 0.1s, color 0.1s',
              }}
            >
              →
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
