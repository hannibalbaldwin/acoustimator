'use client'

import { useState } from 'react'
import type { ScopeResponse, ScopeType } from '@/lib/types'
import { formatCurrency, formatPct, cn } from '@/lib/utils'
import { ScopeTypeBadge } from './ScopeTypeBadge'
import { ConfidenceBadge } from './ConfidenceBadge'
import { Input } from '@/components/ui/input'

interface EditState {
  product_name: string
  area_sf: string
  material_cost_per_sf: string
  markup_pct: string
  labor_days: string
}

interface RowProps {
  scope: ScopeResponse
  onAccept: (id: string, accepted: boolean) => void
  onSave: (id: string, edits: EditState) => void
}

function ScopeRow({ scope, onAccept, onSave }: RowProps) {
  const [editing, setEditing] = useState(false)
  const [edits, setEdits] = useState<EditState>({
    product_name: scope.product_name ?? '',
    area_sf: scope.area_sf?.toString() ?? '',
    material_cost_per_sf: scope.material_cost_per_sf?.toString() ?? '',
    markup_pct: scope.markup_pct != null ? (scope.markup_pct * 100).toFixed(1) : '',
    labor_days: scope.labor_days?.toString() ?? '',
  })

  const borderColor = scope.is_accepted
    ? 'border-l-2 border-l-green-500'
    : 'border-l-2 border-l-amber-400'

  const handleSave = () => {
    onSave(scope.id, edits)
    setEditing(false)
  }

  return (
    <tr className={cn('hover:bg-zinc-50 transition-colors group', borderColor)}>
      {/* Scope Type */}
      <td className="px-3 py-2 whitespace-nowrap">
        <div className="flex items-center gap-1.5">
          <ScopeTypeBadge type={scope.scope_type} />
          {scope.is_ai_suggested && (
            <span className="text-[9px] font-semibold bg-blue-600 text-white px-1 py-0.5 rounded uppercase tracking-wide">
              AI
            </span>
          )}
        </div>
      </td>

      {/* Product */}
      <td className="px-3 py-2 max-w-[200px]">
        {editing ? (
          <Input
            value={edits.product_name}
            onChange={(e) => setEdits((p) => ({ ...p, product_name: e.target.value }))}
            className="h-6 text-xs px-1.5 py-0"
          />
        ) : (
          <span
            className="text-xs text-zinc-700 cursor-pointer hover:text-blue-600 truncate block"
            onClick={() => setEditing(true)}
            title={scope.product_name ?? undefined}
          >
            {scope.product_name ?? <span className="text-zinc-400 italic">— click to set —</span>}
          </span>
        )}
      </td>

      {/* SF */}
      <td className="px-3 py-2 text-right font-mono text-xs">
        {editing ? (
          <Input
            value={edits.area_sf}
            onChange={(e) => setEdits((p) => ({ ...p, area_sf: e.target.value }))}
            className="h-6 text-xs px-1.5 py-0 text-right w-24"
          />
        ) : (
          <span
            className="cursor-pointer hover:text-blue-600"
            onClick={() => setEditing(true)}
          >
            {scope.area_sf != null
              ? new Intl.NumberFormat('en-US').format(scope.area_sf)
              : '—'}
          </span>
        )}
      </td>

      {/* Mat $/SF */}
      <td className="px-3 py-2 text-right font-mono text-xs">
        {editing ? (
          <Input
            value={edits.material_cost_per_sf}
            onChange={(e) => setEdits((p) => ({ ...p, material_cost_per_sf: e.target.value }))}
            className="h-6 text-xs px-1.5 py-0 text-right w-20"
          />
        ) : (
          <span
            className="cursor-pointer hover:text-blue-600"
            onClick={() => setEditing(true)}
          >
            {scope.material_cost_per_sf != null
              ? `$${scope.material_cost_per_sf.toFixed(2)}`
              : '—'}
          </span>
        )}
      </td>

      {/* Markup % */}
      <td className="px-3 py-2 text-right font-mono text-xs">
        {editing ? (
          <Input
            value={edits.markup_pct}
            onChange={(e) => setEdits((p) => ({ ...p, markup_pct: e.target.value }))}
            className="h-6 text-xs px-1.5 py-0 text-right w-16"
          />
        ) : (
          <span
            className="cursor-pointer hover:text-blue-600"
            onClick={() => setEditing(true)}
          >
            {formatPct(scope.markup_pct)}
          </span>
        )}
      </td>

      {/* Labor Days */}
      <td className="px-3 py-2 text-right font-mono text-xs">
        {editing ? (
          <Input
            value={edits.labor_days}
            onChange={(e) => setEdits((p) => ({ ...p, labor_days: e.target.value }))}
            className="h-6 text-xs px-1.5 py-0 text-right w-16"
          />
        ) : (
          <span
            className="cursor-pointer hover:text-blue-600"
            onClick={() => setEditing(true)}
          >
            {scope.labor_days != null ? scope.labor_days.toFixed(1) : '—'}
          </span>
        )}
      </td>

      {/* Total */}
      <td className="px-3 py-2 text-right font-mono text-xs font-semibold text-zinc-900">
        {formatCurrency(scope.total_cost)}
      </td>

      {/* Confidence */}
      <td className="px-3 py-2">
        <ConfidenceBadge level={scope.confidence_level} score={scope.confidence_score} />
      </td>

      {/* Actions */}
      <td className="px-3 py-2">
        <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
          {editing ? (
            <>
              <button
                onClick={handleSave}
                className="text-[11px] px-2 py-0.5 bg-blue-600 text-white rounded hover:bg-blue-700 font-medium"
              >
                Save
              </button>
              <button
                onClick={() => setEditing(false)}
                className="text-[11px] px-2 py-0.5 bg-zinc-100 text-zinc-700 rounded hover:bg-zinc-200 font-medium"
              >
                Cancel
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setEditing(true)}
                className="text-[11px] px-2 py-0.5 bg-zinc-100 text-zinc-700 rounded hover:bg-zinc-200 font-medium"
              >
                Edit
              </button>
              <button
                onClick={() => onAccept(scope.id, !scope.is_accepted)}
                className={cn(
                  'text-[11px] px-2 py-0.5 rounded font-medium',
                  scope.is_accepted
                    ? 'bg-amber-100 text-amber-700 hover:bg-amber-200'
                    : 'bg-green-100 text-green-700 hover:bg-green-200'
                )}
              >
                {scope.is_accepted ? 'Unaccept' : 'Accept'}
              </button>
            </>
          )}
        </div>
      </td>
    </tr>
  )
}

interface EstimateTableProps {
  scopes: ScopeResponse[]
  onScopesChange?: (scopes: ScopeResponse[]) => void
}

const BLANK_SCOPE_TYPES: ScopeType[] = ['ACT', 'AWP', 'FW', 'SM', 'WW', 'Baffles', 'RPG', 'Other']

export function EstimateTable({ scopes, onScopesChange }: EstimateTableProps) {
  const [localScopes, setLocalScopes] = useState<ScopeResponse[]>(scopes)

  const handleAccept = (id: string, accepted: boolean) => {
    const updated = localScopes.map((s) =>
      s.id === id ? { ...s, is_accepted: accepted } : s
    )
    setLocalScopes(updated)
    onScopesChange?.(updated)
  }

  const handleSave = (id: string, edits: EditState) => {
    const updated = localScopes.map((s) => {
      if (s.id !== id) return s
      return {
        ...s,
        product_name: edits.product_name || null,
        area_sf: edits.area_sf ? parseFloat(edits.area_sf) : null,
        material_cost_per_sf: edits.material_cost_per_sf
          ? parseFloat(edits.material_cost_per_sf)
          : null,
        markup_pct: edits.markup_pct ? parseFloat(edits.markup_pct) / 100 : null,
        labor_days: edits.labor_days ? parseFloat(edits.labor_days) : null,
      }
    })
    setLocalScopes(updated)
    onScopesChange?.(updated)
  }

  const handleAddScope = () => {
    const newScope: ScopeResponse = {
      id: `scope-new-${Date.now()}`,
      scope_type: BLANK_SCOPE_TYPES[0],
      product_name: null,
      area_sf: null,
      material_cost_per_sf: null,
      markup_pct: null,
      labor_days: null,
      total_cost: null,
      confidence_score: null,
      confidence_level: 'low',
      is_ai_suggested: false,
      is_accepted: false,
    }
    setLocalScopes([...localScopes, newScope])
  }

  const totalCost = localScopes.reduce((sum, s) => sum + (s.total_cost ?? 0), 0)
  const totalSF = localScopes.reduce((sum, s) => sum + (s.area_sf ?? 0), 0)
  const totalDays = localScopes.reduce((sum, s) => sum + (s.labor_days ?? 0), 0)
  const acceptedCount = localScopes.filter((s) => s.is_accepted).length

  return (
    <div className="bg-white border border-zinc-200 rounded-lg overflow-hidden">
      {/* Table header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-zinc-200 bg-zinc-50">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold text-zinc-800">Scope Line Items</h2>
          <span className="text-xs text-zinc-500">
            {localScopes.length} scopes — {acceptedCount} accepted
          </span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-200 bg-zinc-50/50">
              <th className="px-3 py-2 text-left text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Scope
              </th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Product / Description
              </th>
              <th className="px-3 py-2 text-right text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                SF
              </th>
              <th className="px-3 py-2 text-right text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Mat $/SF
              </th>
              <th className="px-3 py-2 text-right text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Markup
              </th>
              <th className="px-3 py-2 text-right text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Labor Days
              </th>
              <th className="px-3 py-2 text-right text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Total
              </th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Confidence
              </th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {localScopes.map((scope) => (
              <ScopeRow
                key={scope.id}
                scope={scope}
                onAccept={handleAccept}
                onSave={handleSave}
              />
            ))}
          </tbody>

          {/* Totals row */}
          <tfoot>
            <tr className="border-t-2 border-zinc-300 bg-zinc-50 font-semibold">
              <td className="px-3 py-2 text-xs text-zinc-600 font-semibold" colSpan={2}>
                Totals
              </td>
              <td className="px-3 py-2 text-right font-mono text-xs text-zinc-700">
                {totalSF > 0 ? new Intl.NumberFormat('en-US').format(totalSF) : '—'}
              </td>
              <td className="px-3 py-2" />
              <td className="px-3 py-2" />
              <td className="px-3 py-2 text-right font-mono text-xs text-zinc-700">
                {totalDays > 0 ? totalDays.toFixed(1) : '—'}
              </td>
              <td className="px-3 py-2 text-right font-mono text-xs text-zinc-900 font-bold">
                {formatCurrency(totalCost)}
              </td>
              <td className="px-3 py-2" colSpan={2} />
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Add scope */}
      <div className="px-4 py-3 border-t border-zinc-200">
        <button
          onClick={handleAddScope}
          className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-800 font-medium transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path d="M12 5v14M5 12h14" strokeWidth="2.5" strokeLinecap="round" />
          </svg>
          Add Scope Line
        </button>
      </div>
    </div>
  )
}
