'use client'

import { useState } from 'react'
import type { ScopeResponse, ScopeType } from '@/lib/types'
import { formatCurrency, formatPct, cn } from '@/lib/utils'
import { ScopeTypeBadge } from './ScopeTypeBadge'
import { ConfidenceBadge } from './ConfidenceBadge'

interface EditState {
  product_name: string
  area_sf: string
  material_cost_per_sf: string
  markup_pct: string
  labor_days: string
  scope_type: string
}

interface RowProps {
  scope: ScopeResponse
  isLight?: boolean
  onAccept: (id: string, accepted: boolean) => void
  onSave: (id: string, edits: EditState) => void
  onDelete: (id: string) => void
}

function ScopeRow({ scope, isLight, onAccept, onSave, onDelete }: RowProps) {
  const [editing, setEditing] = useState(false)
  const [edits, setEdits] = useState<EditState>({
    product_name: scope.product_name ?? '',
    area_sf: scope.area_sf?.toString() ?? '',
    material_cost_per_sf: scope.material_cost_per_sf?.toString() ?? '',
    markup_pct: scope.markup_pct != null ? (scope.markup_pct * 100).toFixed(1) : '',
    labor_days: scope.labor_days?.toString() ?? '',
    scope_type: scope.scope_type ?? 'ACT',
  })

  const inputStyle: React.CSSProperties = {
    background: isLight ? '#f5f7fa' : '#0e1219',
    border: `1px solid ${isLight ? 'rgba(0,0,0,0.12)' : 'rgba(255,255,255,0.15)'}`,
    color: isLight ? '#0f1923' : '#d8e4f5',
    borderRadius: '4px',
    fontSize: '11px',
    padding: '2px 6px',
    height: '24px',
    outline: 'none',
    fontFamily: 'var(--font-jetbrains-mono), monospace',
    width: '100%',
  }

  const accentColor = scope.is_accepted ? '#a1d67c' : '#f59e0b'

  const handleSave = () => {
    onSave(scope.id, edits)
    setEditing(false)
  }

  const isNewBlank = scope.is_ai_suggested === false && scope.confidence_score === null

  return (
    <tr
      className="group transition-colors"
      style={{
        borderBottom: `1px solid ${isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.04)'}`,
        borderLeft: `2px solid ${accentColor}`,
      }}
      onMouseEnter={(e) =>
        ((e.currentTarget as HTMLTableRowElement).style.background = isLight ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.025)')
      }
      onMouseLeave={(e) =>
        ((e.currentTarget as HTMLTableRowElement).style.background = 'transparent')
      }
    >
      {/* Scope Type */}
      <td className="px-3 py-2 whitespace-nowrap">
        <div className="flex items-center gap-1.5">
          {(editing || isNewBlank) ? (
            <select
              value={edits.scope_type}
              onChange={(e) => setEdits((p) => ({ ...p, scope_type: e.target.value }))}
              style={{
                background: isLight ? '#f5f7fa' : '#0e1219',
                border: `1px solid ${isLight ? 'rgba(0,0,0,0.12)' : 'rgba(255,255,255,0.15)'}`,
                color: isLight ? '#0f1923' : '#d8e4f5',
                borderRadius: '4px',
                fontSize: '11px',
                padding: '2px 4px',
                height: '24px',
                outline: 'none',
              }}
            >
              {['ACT', 'AWP', 'FW', 'SM', 'WW', 'Baffles', 'RPG', 'Other'].map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          ) : (
            <>
              <ScopeTypeBadge type={scope.scope_type} />
              {scope.is_ai_suggested && (
                <span
                  className="text-[9px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wide"
                  style={{ background: 'rgba(129,140,248,0.15)', color: '#818cf8', border: '1px solid rgba(129,140,248,0.25)' }}
                >
                  AI
                </span>
              )}
            </>
          )}
        </div>
      </td>

      {/* Product */}
      <td className="px-3 py-2 max-w-[200px]">
        {editing ? (
          <input
            value={edits.product_name}
            onChange={(e) => setEdits((p) => ({ ...p, product_name: e.target.value }))}
            style={inputStyle}
            className={cn('tabular-nums')}
          />
        ) : (
          <span
            className="text-[12px] truncate block cursor-pointer transition-colors"
            style={{ color: scope.product_name ? (isLight ? '#0f1923' : '#d8e4f5') : (isLight ? '#7890aa' : '#3a4f6a') }}
            onClick={() => setEditing(true)}
            title={scope.product_name ?? undefined}
          >
            {scope.product_name ?? <em style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}>— click to set —</em>}
          </span>
        )}
      </td>

      {/* SF */}
      <td className="px-3 py-2 text-right" style={{ fontFamily: 'var(--font-jetbrains-mono), monospace', fontSize: '12px' }}>
        {editing ? (
          <input
            value={edits.area_sf}
            onChange={(e) => setEdits((p) => ({ ...p, area_sf: e.target.value }))}
            style={inputStyle}
            className={cn('tabular-nums', 'text-right w-24')}
          />
        ) : (
          <span
            className="cursor-pointer transition-colors"
            style={{ color: isLight ? '#0f1923' : '#d8e4f5' }}
            onClick={() => setEditing(true)}
          >
            {scope.area_sf != null ? new Intl.NumberFormat('en-US').format(scope.area_sf) : '—'}
          </span>
        )}
      </td>

      {/* Mat $/SF */}
      <td className="px-3 py-2 text-right" style={{ fontFamily: 'var(--font-jetbrains-mono), monospace', fontSize: '12px' }}>
        {editing ? (
          <input
            value={edits.material_cost_per_sf}
            onChange={(e) => setEdits((p) => ({ ...p, material_cost_per_sf: e.target.value }))}
            style={inputStyle}
            className={cn('tabular-nums', 'text-right w-20')}
          />
        ) : (
          <span
            className="cursor-pointer transition-colors"
            style={{ color: isLight ? '#0f1923' : '#d8e4f5' }}
            onClick={() => setEditing(true)}
          >
            {scope.material_cost_per_sf != null ? `$${scope.material_cost_per_sf.toFixed(2)}` : '—'}
          </span>
        )}
      </td>

      {/* Markup % */}
      <td className="px-3 py-2 text-right" style={{ fontFamily: 'var(--font-jetbrains-mono), monospace', fontSize: '12px' }}>
        {editing ? (
          <input
            value={edits.markup_pct}
            onChange={(e) => setEdits((p) => ({ ...p, markup_pct: e.target.value }))}
            style={inputStyle}
            className={cn('tabular-nums', 'text-right w-16')}
          />
        ) : (
          <span
            className="cursor-pointer transition-colors"
            style={{ color: isLight ? '#0f1923' : '#d8e4f5' }}
            onClick={() => setEditing(true)}
          >
            {formatPct(scope.markup_pct)}
          </span>
        )}
      </td>

      {/* Labor Days */}
      <td className="px-3 py-2 text-right" style={{ fontFamily: 'var(--font-jetbrains-mono), monospace', fontSize: '12px' }}>
        {editing ? (
          <input
            value={edits.labor_days}
            onChange={(e) => setEdits((p) => ({ ...p, labor_days: e.target.value }))}
            style={inputStyle}
            className={cn('tabular-nums', 'text-right w-16')}
          />
        ) : (
          <span
            className="cursor-pointer transition-colors"
            style={{ color: isLight ? '#0f1923' : '#d8e4f5' }}
            onClick={() => setEditing(true)}
          >
            {scope.labor_days != null ? scope.labor_days.toFixed(1) : '—'}
          </span>
        )}
      </td>

      {/* Total */}
      <td
        className="px-3 py-2 text-right font-semibold tabular-nums"
        style={{
          fontFamily: 'var(--font-jetbrains-mono), monospace',
          fontSize: '12px',
          color: isLight ? '#0f1923' : '#d8e4f5',
        }}
      >
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
                className="text-[11px] px-2 py-0.5 rounded-[4px] font-semibold transition-all"
                style={{
                  background: 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
                  color: '#080b10',
                }}
              >
                Save
              </button>
              <button
                onClick={() => setEditing(false)}
                className="text-[11px] px-2 py-0.5 rounded-[4px] font-medium transition-all"
                style={{
                  background: isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.07)',
                  color: isLight ? '#4a5e7a' : '#6b82a0',
                  border: `1px solid ${isLight ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.1)'}`,
                }}
              >
                Cancel
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setEditing(true)}
                className="text-[11px] px-2 py-0.5 rounded-[4px] font-medium transition-all"
                style={{
                  background: isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.07)',
                  color: isLight ? '#4a5e7a' : '#6b82a0',
                  border: `1px solid ${isLight ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.1)'}`,
                }}
              >
                Edit
              </button>
              <button
                onClick={() => onAccept(scope.id, !scope.is_accepted)}
                className="text-[11px] px-2 py-0.5 rounded-[4px] font-medium transition-all"
                style={
                  scope.is_accepted
                    ? {
                        background: 'rgba(245,158,11,0.12)',
                        color: '#f59e0b',
                        border: '1px solid rgba(245,158,11,0.22)',
                      }
                    : {
                        background: 'rgba(161,214,124,0.12)',
                        color: '#a1d67c',
                        border: '1px solid rgba(161,214,124,0.22)',
                      }
                }
              >
                {scope.is_accepted ? 'Unaccept' : 'Accept'}
              </button>
              <button
                onClick={() => onDelete(scope.id)}
                className="text-[11px] px-2 py-0.5 rounded-[4px] font-medium transition-all"
                style={{
                  background: 'rgba(240,82,82,0.10)',
                  color: '#f05252',
                  border: '1px solid rgba(240,82,82,0.20)',
                }}
                title="Delete scope"
              >
                ✕
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
  isLight?: boolean
  onScopesChange?: (scopes: ScopeResponse[]) => void
  onScopeUpdate?: (scopeId: string, edits: EditState) => void
  onScopeDelete?: (scopeId: string) => void
}

const BLANK_SCOPE_TYPES: ScopeType[] = ['ACT', 'AWP', 'FW', 'SM', 'WW', 'Baffles', 'RPG', 'Other']

export function EstimateTable({ scopes, isLight, onScopesChange, onScopeUpdate, onScopeDelete }: EstimateTableProps) {
  const [localScopes, setLocalScopes] = useState<ScopeResponse[]>(scopes)

  const handleAccept = (id: string, accepted: boolean) => {
    const updated = localScopes.map((s) => (s.id === id ? { ...s, is_accepted: accepted } : s))
    setLocalScopes(updated)
    onScopesChange?.(updated)
  }

  const handleSave = (id: string, edits: EditState) => {
    const updated = localScopes.map((s) => {
      if (s.id !== id) return s
      return {
        ...s,
        scope_type: edits.scope_type as ScopeType,
        product_name: edits.product_name || null,
        area_sf: edits.area_sf ? parseFloat(edits.area_sf) : null,
        material_cost_per_sf: edits.material_cost_per_sf ? parseFloat(edits.material_cost_per_sf) : null,
        markup_pct: edits.markup_pct ? parseFloat(edits.markup_pct) / 100 : null,
        labor_days: edits.labor_days ? parseFloat(edits.labor_days) : null,
      }
    })
    setLocalScopes(updated)
    onScopesChange?.(updated)
    onScopeUpdate?.(id, edits)
  }

  const handleDelete = (id: string) => {
    const updated = localScopes.filter((s) => s.id !== id)
    setLocalScopes(updated)
    onScopesChange?.(updated)
    if (!id.startsWith('scope-new-')) {
      onScopeDelete?.(id)
    }
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

  const thStyle: React.CSSProperties = {
    color: isLight ? '#7890aa' : '#3a4f6a',
    fontSize: '10px',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.09em',
    padding: '10px 12px',
  }

  return (
    <div
      className="rounded-[8px] overflow-hidden"
      style={{
        background: isLight ? '#ffffff' : '#131822',
        border: `1px solid ${isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)'}`,
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3"
        style={{ borderBottom: `1px solid ${isLight ? 'rgba(0,0,0,0.07)' : 'rgba(255,255,255,0.07)'}` }}
      >
        <div className="flex items-center gap-3">
          <h2 className="text-[13px] font-semibold" style={{ color: isLight ? '#0f1923' : '#d8e4f5' }}>
            Scope Line Items
          </h2>
          <span className="text-[11px]" style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}>
            {localScopes.length} scopes · {acceptedCount} accepted
          </span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr style={{ borderBottom: `1px solid ${isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.06)'}` }}>
              <th style={{ ...thStyle, textAlign: 'left' }}>Scope</th>
              <th style={{ ...thStyle, textAlign: 'left' }}>Product / Description</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>SF</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>Mat $/SF</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>Markup</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>Labor Days</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>Total</th>
              <th style={{ ...thStyle, textAlign: 'left' }}>Confidence</th>
              <th style={{ ...thStyle, textAlign: 'left' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {localScopes.map((scope) => (
              <ScopeRow
                key={scope.id}
                scope={scope}
                isLight={isLight}
                onAccept={handleAccept}
                onSave={handleSave}
                onDelete={handleDelete}
              />
            ))}
          </tbody>

          {/* Totals row */}
          <tfoot>
            <tr
              style={{
                borderTop: `2px solid ${isLight ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.1)'}`,
                background: isLight ? 'rgba(0,0,0,0.02)' : 'rgba(255,255,255,0.02)',
              }}
            >
              <td
                colSpan={2}
                className="px-3 py-2.5 text-[12px] font-semibold"
                style={{ color: isLight ? '#4a5e7a' : '#6b82a0' }}
              >
                Totals
              </td>
              <td
                className="px-3 py-2.5 text-right tabular-nums"
                style={{
                  fontFamily: 'var(--font-jetbrains-mono), monospace',
                  fontSize: '12px',
                  color: isLight ? '#4a5e7a' : '#6b82a0',
                }}
              >
                {totalSF > 0 ? new Intl.NumberFormat('en-US').format(totalSF) : '—'}
              </td>
              <td className="px-3 py-2.5" />
              <td className="px-3 py-2.5" />
              <td
                className="px-3 py-2.5 text-right tabular-nums"
                style={{
                  fontFamily: 'var(--font-jetbrains-mono), monospace',
                  fontSize: '12px',
                  color: isLight ? '#4a5e7a' : '#6b82a0',
                }}
              >
                {totalDays > 0 ? totalDays.toFixed(1) : '—'}
              </td>
              <td
                className="px-3 py-2.5 text-right tabular-nums font-bold"
                style={{
                  fontFamily: 'var(--font-jetbrains-mono), monospace',
                  fontSize: '13px',
                  color: '#a1d67c',
                }}
              >
                {formatCurrency(totalCost)}
              </td>
              <td colSpan={2} className="px-3 py-2.5" />
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Add scope */}
      <div
        className="px-4 py-3"
        style={{ borderTop: `1px solid ${isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.06)'}` }}
      >
        <button
          onClick={handleAddScope}
          className="flex items-center gap-1.5 text-[12px] font-medium transition-colors"
          style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}
          onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.color = '#a1d67c')}
          onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.color = isLight ? '#7890aa' : '#3a4f6a')}
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
