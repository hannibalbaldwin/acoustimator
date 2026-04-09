'use client'

import { cn } from '@/lib/utils'
import { useTheme } from '@/components/ThemeProvider'
import { WaveformLoader } from '@/components/ui/WaveformLoader'

interface StatCardProps {
  label: string
  value: string
  delta?: {
    value: string
    positive?: boolean
    neutral?: boolean
  }
  accent?: boolean
  loading?: boolean
  className?: string
}

export function StatCard({ label, value, delta, accent, loading, className }: StatCardProps) {
  const { theme } = useTheme()
  const isLight = theme === 'light'

  return (
    <div
      className={cn('relative px-5 py-4 rounded-[8px] overflow-hidden', className)}
      style={{
        background: accent
          ? 'linear-gradient(135deg, rgba(90,138,30,0.25) 0%, rgba(161,214,124,0.12) 100%)'
          : isLight ? '#ffffff' : '#131822',
        border: accent
          ? `1px solid ${isLight ? 'rgba(161,214,124,0.3)' : 'rgba(161,214,124,0.25)'}`
          : `1px solid ${isLight ? 'rgba(0,0,0,0.09)' : 'rgba(255,255,255,0.08)'}`,
      }}
    >
      {/* Subtle gradient overlay */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: isLight
            ? 'linear-gradient(145deg, rgba(0,0,0,0.015) 0%, rgba(0,0,0,0) 60%)'
            : 'linear-gradient(145deg, rgba(255,255,255,0.025) 0%, rgba(255,255,255,0) 60%)',
        }}
      />

      <p
        className="text-[11px] font-semibold uppercase tracking-[0.09em] mb-2"
        style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}
      >
        {label}
      </p>

      <div className="flex items-end gap-2">
        {loading ? (
          <WaveformLoader variant="inline" className="mt-1" />
        ) : (
          <p
            className="text-[28px] leading-none font-[--font-jetbrains-mono] tabular-nums"
            style={{
              fontFamily: 'var(--font-jetbrains-mono), monospace',
              fontWeight: 600,
              color: accent ? '#a1d67c' : isLight ? '#1a2335' : '#d8e4f5',
              letterSpacing: '-0.03em',
            }}
          >
            {value}
          </p>
        )}

        {!loading && delta && (
          <span
            className="text-[11px] font-medium rounded-[4px] px-1.5 py-0.5 mb-0.5 font-mono"
            style={
              delta.neutral
                ? { color: '#6b82a0', background: 'rgba(107,130,160,0.12)' }
                : delta.positive
                  ? { color: '#a1d67c', background: 'rgba(161,214,124,0.12)' }
                  : { color: '#f59e0b', background: 'rgba(245,158,11,0.12)' }
            }
          >
            {delta.positive && '+'}
            {delta.value}
          </span>
        )}
      </div>
    </div>
  )
}
