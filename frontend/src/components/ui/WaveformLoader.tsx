'use client'

import { cn } from '@/lib/utils'

// Block wave path — 4 sinusoidal cycles in a 300×60 viewBox
const WAVE_BLOCK = 'M10 30 Q35 12 60 30 Q85 48 110 30 Q135 12 160 30 Q185 48 210 30 Q235 12 260 30 Q285 48 310 30'

// Inline wave path — 4 cycles in an 84×24 viewBox
const WAVE_INLINE = 'M4 12 Q14 4 24 12 Q34 20 44 12 Q54 4 64 12 Q74 20 84 12'

// Always uses the bright CA electric green — intentionally vivid
const COLOR = '#a1d67c'

interface WaveformLoaderProps {
  /**
   * inline — small fixed-size loader for stat cards (84×24)
   * block  — full-width loader for charts, tables, and card bodies
   */
  variant?: 'inline' | 'block'
  className?: string
}

export function WaveformLoader({ variant = 'inline', className }: WaveformLoaderProps) {
  const color = COLOR

  if (variant === 'block') {
    return (
      <div className={cn('flex items-center justify-center py-10', className)}>
        <svg
          viewBox="0 0 300 60"
          fill="none"
          style={{ width: '100%', maxWidth: 360, height: 60 }}
          aria-label="Loading…"
        >
          {/* Ghost base wave */}
          <path
            d={WAVE_BLOCK}
            stroke={color}
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity={0.12}
          />
          {/* Soft glow aura (wide, low opacity, travels with the pulse) */}
          <path
            d={WAVE_BLOCK}
            stroke={color}
            strokeWidth="10"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray="80 220"
            opacity={0.08}
            className="wave-anim"
          />
          {/* Main traveling pulse */}
          <path
            d={WAVE_BLOCK}
            stroke={color}
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray="80 220"
            className="wave-anim"
          />
        </svg>
      </div>
    )
  }

  // inline — stat card placeholder
  return (
    <svg
      viewBox="0 0 84 24"
      fill="none"
      style={{ width: 84, height: 24 }}
      className={className}
      aria-label="Loading…"
    >
      {/* Ghost base */}
      <path
        d={WAVE_INLINE}
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.15}
      />
      {/* Glow aura */}
      <path
        d={WAVE_INLINE}
        stroke={color}
        strokeWidth="6"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray="25 55"
        opacity={0.1}
        className="wave-anim-sm"
      />
      {/* Main pulse */}
      <path
        d={WAVE_INLINE}
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray="25 55"
        className="wave-anim-sm"
      />
    </svg>
  )
}
