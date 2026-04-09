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
  children: ReactNode
}

export function BoardColumn({ columnKey, name, count, accentBorderColor, isOver, children }: BoardColumnProps) {
  const { theme } = useTheme()
  const isLight = theme === 'light'

  const { setNodeRef } = useDroppable({ id: columnKey })

  const headerBg = isLight ? 'rgba(0,0,0,0.025)' : 'rgba(255,255,255,0.025)'
  const labelColor = isLight ? '#4a5e7a' : '#6b82a0'
  const badgeBg = isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.08)'
  const badgeColor = isLight ? '#7890aa' : '#3a4f6a'
  const emptyColor = isLight ? '#7890aa' : '#3a4f6a'

  const columnBg = isOver
    ? (isLight ? 'rgba(161,214,124,0.06)' : 'rgba(161,214,124,0.06)')
    : 'transparent'
  const columnOutline = isOver
    ? `1px solid rgba(161,214,124,0.3)`
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
        {count === 0 ? (
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
