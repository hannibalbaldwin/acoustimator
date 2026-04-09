'use client'

import { useState, useEffect } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import type { TrendDataPoint } from '@/lib/types'
import { useTheme } from '@/components/ThemeProvider'
import { getCostTrends } from '@/lib/api'
import { WaveformLoader } from '@/components/ui/WaveformLoader'

// CA brand green for AWP, blue for ACT, teal for FW, amber for SM
const SCOPE_COLORS = {
  ACT: '#60a5fa',  // blue-400
  AWP: '#a1d67c',  // CA green
  FW:  '#2dd4bf',  // teal-400
  SM:  '#c084fc',  // purple-400
}

interface CustomTooltipProps {
  active?: boolean
  payload?: { name: string; value: number; color: string }[]
  label?: string
  isLight?: boolean
}

function CustomTooltip({ active, payload, label, isLight }: CustomTooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div
      className="px-3 py-2.5 text-xs shadow-xl"
      style={{
        background: isLight ? '#ffffff' : '#1e2638',
        border: `1px solid ${isLight ? 'rgba(0,0,0,0.12)' : 'rgba(255,255,255,0.12)'}`,
        borderRadius: '7px',
        fontFamily: 'var(--font-jetbrains-mono), monospace',
        boxShadow: isLight ? '0 4px 12px rgba(0,0,0,0.12)' : undefined,
      }}
    >
      <p
        className="font-semibold mb-1.5 text-[11px] uppercase tracking-widest"
        style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}
      >
        {label}
      </p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex items-center gap-2 mb-0.5">
          <span
            className="w-2 h-2 rounded-full flex-shrink-0"
            style={{ background: entry.color }}
          />
          <span style={{ color: '#6b82a0' }}>{entry.name}</span>
          <span className="ml-auto font-semibold" style={{ color: isLight ? '#1a2335' : '#d8e4f5' }}>
            ${entry.value.toFixed(2)}/SF
          </span>
        </div>
      ))}
    </div>
  )
}

const MONO = 'var(--font-jetbrains-mono), monospace'

type Granularity = 'year' | 'quarter' | 'month'

const SUBTITLES: Record<Granularity, string> = {
  year: 'Historical $/SF by scope type · 2024 – 2026',
  quarter: 'Quarterly average $/SF by scope type',
  month: 'Monthly average $/SF · muted dots = < 3 jobs',
}

const TOGGLE_LABELS: { key: Granularity; label: string }[] = [
  { key: 'year', label: 'Year' },
  { key: 'quarter', label: 'Quarter' },
  { key: 'month', label: 'Month' },
]

export function CostTrendChart() {
  const { theme } = useTheme()
  const isLight = theme === 'light'
  const [granularity, setGranularity] = useState<Granularity>('quarter')
  const [data, setData] = useState<TrendDataPoint[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    getCostTrends(granularity)
      .then(setData)
      .catch(() => setData([]))
      .finally(() => setLoading(false))
  }, [granularity])

  return (
    <div
      className="px-6 py-5 rounded-[8px]"
      style={{
        background: isLight ? '#ffffff' : '#131822',
        border: `1px solid ${isLight ? 'rgba(0,0,0,0.09)' : 'rgba(255,255,255,0.08)'}`,
      }}
    >
      <div className="flex items-start justify-between mb-5">
        <div>
          <h2 className="text-[13px] font-semibold" style={{ color: isLight ? '#1a2335' : '#d8e4f5' }}>
            Cost / SF Trends
          </h2>
          <p className="text-[12px] mt-0.5" style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}>
            {SUBTITLES[granularity]}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Granularity toggle */}
          <div className="flex items-center gap-1">
            {TOGGLE_LABELS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setGranularity(key)}
                className="text-[11px] font-medium px-2.5 py-1 rounded-[4px] transition-all"
                style={
                  granularity === key
                    ? isLight
                      ? { background: 'rgba(82,155,30,0.12)', border: '1px solid rgba(82,155,30,0.28)', color: '#3d7010' }
                      : { background: 'rgba(161,214,124,0.12)', border: '1px solid rgba(161,214,124,0.22)', color: '#a1d67c' }
                    : { background: 'transparent', border: `1px solid ${isLight ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.1)'}`, color: isLight ? '#7890aa' : '#3a4f6a' }
                }
              >
                {label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1 text-[11px] font-mono" style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}>
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: '#a1d67c' }}
            />
            <span>Live data</span>
          </div>
        </div>
      </div>

      {loading && <WaveformLoader variant="block" className="py-16" />}
      <div className={loading ? 'hidden' : undefined}>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke={isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.04)'}
              vertical={false}
            />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: isLight ? '#7890aa' : '#3a4f6a', fontFamily: MONO }}
              axisLine={{ stroke: isLight ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.07)' }}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: isLight ? '#7890aa' : '#3a4f6a', fontFamily: MONO }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => `$${v}`}
              width={38}
            />
            <Tooltip
              content={<CustomTooltip isLight={isLight} />}
              cursor={{ stroke: isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)', strokeWidth: 1 }}
            />
            <Legend
              wrapperStyle={{ fontSize: 11, fontFamily: MONO, paddingTop: 16 }}
              iconType="circle"
              iconSize={7}
              formatter={(value) => (
                <span style={{ color: isLight ? '#4a5e7a' : '#6b82a0' }}>{value}</span>
              )}
            />
            {(Object.entries(SCOPE_COLORS) as [keyof typeof SCOPE_COLORS, string][]).map(
              ([key, color]) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={color}
                  strokeWidth={2}
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  dot={(props: any) => {
                    const sparse = granularity === 'month' && (props.payload._count ?? 99) < 3
                    return (
                      <circle
                        key={`dot-${props.cx}-${props.cy}`}
                        cx={props.cx}
                        cy={props.cy}
                        r={sparse ? 2.5 : 3}
                        fill={color}
                        opacity={sparse ? 0.35 : 1}
                      />
                    )
                  }}
                  activeDot={{ r: 5, fill: color, stroke: isLight ? 'rgba(0,0,0,0.15)' : 'rgba(255,255,255,0.2)', strokeWidth: 2 }}
                />
              )
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
