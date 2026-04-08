import type { ReactNode } from 'react'

interface BoardColumnProps {
  name: string
  count: number
  accentBorderColor: string
  children: ReactNode
}

export function BoardColumn({ name, count, accentBorderColor, children }: BoardColumnProps) {
  return (
    <div
      style={{
        minWidth: '280px',
        width: '280px',
        flexShrink: 0,
      }}
    >
      {/* Column header */}
      <div
        style={{
          borderTop: `2px solid ${accentBorderColor}`,
          borderRadius: '6px 6px 0 0',
          background: 'rgba(255,255,255,0.025)',
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
            color: '#6b82a0',
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
            background: 'rgba(255,255,255,0.08)',
            color: '#3a4f6a',
          }}
        >
          {count}
        </span>
      </div>

      {/* Card list */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
          overflowY: 'auto',
          maxHeight: 'calc(100vh - 340px)',
        }}
      >
        {count === 0 ? (
          <div
            style={{
              paddingTop: '32px',
              paddingBottom: '32px',
              textAlign: 'center',
              fontSize: '12px',
              color: '#3a4f6a',
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
