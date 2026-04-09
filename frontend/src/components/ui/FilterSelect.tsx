'use client'

import { useState, useRef, useEffect } from 'react'
import { useTheme } from '@/components/ThemeProvider'
import { cn } from '@/lib/utils'

interface FilterSelectProps {
  value: string
  onChange: (value: string) => void
  options: string[]
  className?: string
}

export function FilterSelect({ value, onChange, options, className }: FilterSelectProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const { theme } = useTheme()
  const isLight = theme === 'light'

  // Close on outside click
  useEffect(() => {
    function handle(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [])

  const bg = isLight ? '#ffffff' : '#0e1219'
  const border = isLight ? 'rgba(0,0,0,0.12)' : 'rgba(255,255,255,0.12)'
  const text = isLight ? '#1a2335' : '#d8e4f5'
  const muted = isLight ? '#7890aa' : '#3a4f6a'
  const dropdownBg = isLight ? '#ffffff' : '#1e2638'
  const hoverBg = isLight ? '#f0f4f8' : 'rgba(255,255,255,0.06)'
  const activeBg = isLight ? 'rgba(82,155,30,0.1)' : 'rgba(161,214,124,0.1)'
  const activeText = '#6c992a'

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }} className={className}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 6,
          width: '100%',
          background: bg,
          border: `1px solid ${border}`,
          borderRadius: 6,
          color: text,
          fontSize: 13,
          fontWeight: 500,
          padding: '8px 10px 8px 12px',
          cursor: 'pointer',
          whiteSpace: 'nowrap',
          transition: 'border-color 150ms',
        }}
      >
        {value}
        <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: muted, transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 150ms', flexShrink: 0 }}>
          <path d="M19 9l-7 7-7-7" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>

      {open && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            left: 0,
            right: 0,
            zIndex: 50,
            background: dropdownBg,
            border: `1px solid ${border}`,
            borderRadius: 8,
            boxShadow: isLight
              ? '0 8px 24px rgba(0,0,0,0.12), 0 1px 4px rgba(0,0,0,0.06)'
              : '0 8px 32px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.06)',
            minWidth: '100%',
            padding: '4px',
            overflow: 'hidden',
          }}
        >
          {options.map((opt) => {
            const isSelected = opt === value
            return (
              <button
                key={opt}
                type="button"
                onClick={() => { onChange(opt); setOpen(false) }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  width: '100%',
                  padding: '7px 10px',
                  borderRadius: 5,
                  background: isSelected ? activeBg : 'transparent',
                  color: isSelected ? activeText : text,
                  fontSize: 13,
                  fontWeight: isSelected ? 600 : 400,
                  cursor: 'pointer',
                  textAlign: 'left',
                  border: 'none',
                  whiteSpace: 'nowrap',
                  transition: 'background 100ms',
                }}
                onMouseEnter={(e) => { if (!isSelected) (e.currentTarget as HTMLButtonElement).style.background = hoverBg }}
                onMouseLeave={(e) => { if (!isSelected) (e.currentTarget as HTMLButtonElement).style.background = 'transparent' }}
              >
                {isSelected && (
                  <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ flexShrink: 0 }}>
                    <path d="M20 6L9 17l-5-5" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
                {!isSelected && <span style={{ width: 12, flexShrink: 0 }} />}
                {opt}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
