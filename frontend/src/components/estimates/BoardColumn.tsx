'use client'

import type { ReactNode } from 'react'
import { useTheme } from '@/components/ThemeProvider'
import { useDroppable } from '@dnd-kit/core'

interface BoardColumnProps {
  columnKey: string
  name: string
  count: number
  accentBorderColor: string
  isOver: boolean
  isBlocked?: boolean      // dragging over this column but drop will fail
  blockReason?: string     // why it's blocked — shown inline
  children: ReactNode
}

export function BoardColumn({
  columnKey, name, count, accentBorderColor,
  isOver, isBlocked, blockReason, children,
}: BoardColumnProps) {
  const { theme } = useTheme()
  const isLight = theme === 'light'

  const { setNodeRef } = useDroppable({ id: columnKey })

  const headerBg = isLight ? 'rgba(0,0,0,0.025)' : 'rgba(255,255,255,0.025)'
  const labelColor = isLight ? '#4a5e7a' : '#6b82a0'
  const badgeBg = isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.08)'
  const badgeColor = isLight ? '#7890aa' : '#3a4f6a'
  const emptyColor = isLight ? '#7890aa' : '#3a4f6a'

  // Green = valid drop, amber = blocked, transparent = idle
  const columnBg = isOver
    ? (isBlocked ? 'rgba(245,158,11,0.07)' : 'rgba(161,214,124,0.06)')
    : 'transparent'
  const columnOutline = isOver
    ? (isBlocked ? '1px solid rgba(245,158,11,0.4)' : '1px solid rgba(161,214,124,0.3)')
    : '1px solid transparent'

  return (
    <div
      style={{
        minWidth: '280px',
        width: '280px',
        flexShrink: 0,
        borderRadius: '8px',
        background: columnBg,
        outline: columnOutline,
        transition: 'background 0.15s, outline 0.15s',
      }}
    >
      {/* Column header */}
      <div
        style={{
          borderTop: `2px solid ${accentBorderColor}`,
          borderRadius: '6px 6px 0 0',
          background: headerBg,
          paddingLeft: '12px',
          paddingRight: '12px',
          paddingTop: '10px',
          paddingBottom: '10px',
          marginBottom: '8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <span
          style={{
            fontSize: '12px',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.07em',
            color: labelColor,
          }}
        >
          {name}
        </span>
        <span
          style={{
            fontSize: '10px',
            fontFamily: 'monospace',
            padding: '2px 6px',
            borderRadius: '3px',
            background: badgeBg,
            color: badgeColor,
          }}
        >
          {count}
        </span>
      </div>

      {/* Card list — droppable target */}
      <div
        ref={setNodeRef}
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
          overflowY: 'auto',
          maxHeight: 'calc(100vh - 340px)',
          minHeight: '80px',
          padding: '0 4px 4px',
        }}
      >
        {/* Blocked reason pill — shown while hovering an invalid target */}
        {isOver && isBlocked && blockReason && (
          <div
            style={{
              margin: '4px 0 2px',
              padding: '6px 10px',
              borderRadius: '6px',
              background: 'rgba(245,158,11,0.12)',
              border: '1px solid rgba(245,158,11,0.35)',
              fontSize: '11px',
              color: '#d97706',
              textAlign: 'center',
              lineHeight: 1.4,
            }}
          >
            ⚠ {blockReason}
          </div>
        )}

        {count === 0 && !(isOver && isBlocked) ? (
          <div
            style={{
              paddingTop: '32px',
              paddingBottom: '32px',
              textAlign: 'center',
              fontSize: '12px',
              color: emptyColor,
            }}
          >
            No estimates
          </div>
        ) : (
          children
        )}
      </div>
    </div>
  )
}
