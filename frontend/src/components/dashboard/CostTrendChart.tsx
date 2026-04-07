'use client'

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

interface CostTrendChartProps {
  data: TrendDataPoint[]
}

const SCOPE_COLORS = {
  ACT: '#2563eb',  // blue-600
  AWP: '#16a34a',  // green-600
  FW: '#0d9488',   // teal-600
  SM: '#9333ea',   // purple-600
}

interface CustomTooltipProps {
  active?: boolean
  payload?: { name: string; value: number; color: string }[]
  label?: string
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-zinc-200 rounded shadow-md px-3 py-2 text-xs font-mono">
      <p className="font-semibold text-zinc-700 mb-1">{label}</p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: entry.color }} />
          <span className="text-zinc-500">{entry.name}:</span>
          <span className="font-semibold text-zinc-800">${entry.value.toFixed(2)}/SF</span>
        </div>
      ))}
    </div>
  )
}

export function CostTrendChart({ data }: CostTrendChartProps) {
  return (
    <div className="bg-white border border-zinc-200 rounded-lg px-5 py-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-semibold text-zinc-800">Cost / SF Trends</h2>
          <p className="text-xs text-zinc-400 mt-0.5">Historical $/SF by scope type (2020–2024)</p>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: '#71717a', fontFamily: 'ui-monospace, monospace' }}
            axisLine={{ stroke: '#e4e4e7' }}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 11, fill: '#71717a', fontFamily: 'ui-monospace, monospace' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => `$${v}`}
            width={36}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ fontSize: 11, fontFamily: 'ui-monospace, monospace' }}
            iconType="circle"
            iconSize={8}
          />
          {(Object.entries(SCOPE_COLORS) as [keyof typeof SCOPE_COLORS, string][]).map(
            ([key, color]) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={color}
                strokeWidth={2}
                dot={{ r: 3, fill: color, strokeWidth: 0 }}
                activeDot={{ r: 5 }}
              />
            )
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
