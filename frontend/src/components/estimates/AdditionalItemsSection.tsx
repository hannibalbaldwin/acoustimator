'use client'

import { useState, useEffect } from 'react'
import type { AdditionalItem, AdditionalItemType } from '@/lib/types'
import {
  listAdditionalItems,
  createAdditionalItem,
  updateAdditionalItem,
  deleteAdditionalItem,
} from '@/lib/api'
import { FilterSelect } from '@/components/ui/FilterSelect'
import { formatCurrency } from '@/lib/utils'

const ITEM_TYPE_LABELS: Record<string, string> = {
  lift_rental: 'Lift Rental',
  travel_per_diem: 'Travel / Per Diem',
  travel_hotels: 'Hotel',
  travel_flights: 'Flights',
  equipment: 'Equipment',
  consumables: 'Consumables',
  commission: 'Commission',
  punch_list: 'Punch List / Go-back',
  site_visit: 'Site Visit',
  setup_unload: 'Setup / Unload',
  bond: 'P&P Bond',
  other: 'Other',
}

const ITEM_TYPE_OPTIONS = Object.keys(ITEM_TYPE_LABELS)

interface AdditionalItemsSectionProps {
  estimateId: string
  isLight?: boolean
  onTotalChange?: (total: number) => void
}

interface ItemRowProps {
  item: AdditionalItem
  isLight: boolean
  onEdit: (item: AdditionalItem) => void
  onDelete: (id: string) => void
}

function ItemRow({ item, isLight, onEdit, onDelete }: ItemRowProps) {
  const [hovered, setHovered] = useState(false)
  const textPrimary = isLight ? '#0f1923' : '#d8e4f5'
  const textMuted = isLight ? '#7890aa' : '#3a4f6a'

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        padding: '8px 0',
        borderBottom: `1px solid ${isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.04)'}`,
        position: 'relative',
      }}
    >
      {/* Type badge */}
      <span
        style={{
          fontSize: '11px',
          fontWeight: 600,
          padding: '2px 8px',
          borderRadius: '4px',
          background: isLight ? 'rgba(161,214,124,0.12)' : 'rgba(161,214,124,0.1)',
          color: isLight ? '#3d7010' : '#a1d67c',
          border: `1px solid ${isLight ? 'rgba(161,214,124,0.3)' : 'rgba(161,214,124,0.2)'}`,
          flexShrink: 0,
          whiteSpace: 'nowrap',
        }}
      >
        {ITEM_TYPE_LABELS[item.item_type] ?? item.item_type}
      </span>

      {/* Description */}
      <span
        style={{
          fontSize: '12px',
          color: item.description ? textPrimary : textMuted,
          flex: 1,
          minWidth: 0,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          fontStyle: item.description ? 'normal' : 'italic',
        }}
      >
        {item.description ?? '—'}
      </span>

      {/* Amount */}
      <span
        style={{
          fontSize: '13px',
          fontWeight: 600,
          fontFamily: 'var(--font-jetbrains-mono), monospace',
          color: textPrimary,
          flexShrink: 0,
        }}
      >
        {formatCurrency(item.amount)}
      </span>

      {/* Hover action buttons */}
      {hovered && (
        <div style={{ display: 'flex', gap: '4px', flexShrink: 0 }}>
          <button
            title="Edit item"
            onClick={() => onEdit(item)}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '3px 5px',
              borderRadius: '4px',
              color: textMuted,
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
            </svg>
          </button>
          <button
            title="Delete item"
            onClick={() => onDelete(item.id)}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '3px 5px',
              borderRadius: '4px',
              color: textMuted,
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
              <path d="M10 11v6M14 11v6" />
              <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
            </svg>
          </button>
        </div>
      )}
    </div>
  )
}

export function AdditionalItemsSection({
  estimateId,
  isLight = false,
  onTotalChange,
}: AdditionalItemsSectionProps) {
  const [items, setItems] = useState<AdditionalItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Add form state
  const [addType, setAddType] = useState<string>(ITEM_TYPE_OPTIONS[0])
  const [addDesc, setAddDesc] = useState('')
  const [addAmount, setAddAmount] = useState('')
  const [addSubmitting, setAddSubmitting] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)

  // Edit state
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editType, setEditType] = useState<string>(ITEM_TYPE_OPTIONS[0])
  const [editDesc, setEditDesc] = useState('')
  const [editAmount, setEditAmount] = useState('')
  const [editSaving, setEditSaving] = useState(false)

  const textPrimary = isLight ? '#0f1923' : '#d8e4f5'
  const textMuted = isLight ? '#7890aa' : '#3a4f6a'
  const cardBg = isLight ? '#ffffff' : '#131822'
  const cardBorder = isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)'
  const inputBg = isLight ? '#f5f7fa' : '#0e1219'
  const inputBorder = isLight ? 'rgba(0,0,0,0.12)' : 'rgba(255,255,255,0.15)'
  const dividerColor = isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.06)'

  const inputStyle: React.CSSProperties = {
    background: inputBg,
    border: `1px solid ${inputBorder}`,
    color: textPrimary,
    borderRadius: '6px',
    fontSize: '12px',
    padding: '5px 8px',
    height: '30px',
    outline: 'none',
    boxSizing: 'border-box',
  }

  // Load items on mount
  useEffect(() => {
    setLoading(true)
    listAdditionalItems(estimateId)
      .then((data) => {
        setItems(data)
        setLoading(false)
        const total = data.reduce((sum, i) => sum + i.amount, 0)
        onTotalChange?.(total)
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Failed to load additional items')
        setLoading(false)
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [estimateId])

  const updateTotal = (updated: AdditionalItem[]) => {
    const total = updated.reduce((sum, i) => sum + i.amount, 0)
    onTotalChange?.(total)
  }

  const handleAdd = async () => {
    const amount = parseFloat(addAmount)
    if (!addType || isNaN(amount) || amount <= 0) {
      setAddError('Please select a type and enter a valid amount.')
      return
    }
    setAddSubmitting(true)
    setAddError(null)
    try {
      const created = await createAdditionalItem(estimateId, {
        item_type: addType,
        description: addDesc.trim() || null,
        amount,
      })
      const updated = [...items, created]
      setItems(updated)
      updateTotal(updated)
      setAddDesc('')
      setAddAmount('')
      setAddType(ITEM_TYPE_OPTIONS[0])
    } catch (err: unknown) {
      setAddError(err instanceof Error ? err.message : 'Failed to add item')
    } finally {
      setAddSubmitting(false)
    }
  }

  const handleDelete = (id: string) => {
    // Optimistic remove
    const updated = items.filter((i) => i.id !== id)
    setItems(updated)
    updateTotal(updated)
    deleteAdditionalItem(estimateId, id).catch(() => {
      // Revert on failure
      setItems(items)
      updateTotal(items)
    })
  }

  const handleEditStart = (item: AdditionalItem) => {
    setEditingId(item.id)
    setEditType(item.item_type)
    setEditDesc(item.description ?? '')
    setEditAmount(String(item.amount))
  }

  const handleEditSave = async (itemId: string) => {
    const amount = parseFloat(editAmount)
    if (!editType || isNaN(amount) || amount <= 0) return
    setEditSaving(true)
    try {
      const updated_item = await updateAdditionalItem(estimateId, itemId, {
        item_type: editType,
        description: editDesc.trim() || null,
        amount,
      })
      const updated = items.map((i) => (i.id === itemId ? updated_item : i))
      setItems(updated)
      updateTotal(updated)
      setEditingId(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update item')
    } finally {
      setEditSaving(false)
    }
  }

  const total = items.reduce((sum, i) => sum + i.amount, 0)

  return (
    <div
      style={{
        borderRadius: '8px',
        background: cardBg,
        border: `1px solid ${cardBorder}`,
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 16px',
          borderBottom: `1px solid ${dividerColor}`,
        }}
      >
        <h2 style={{ fontSize: '13px', fontWeight: 600, color: textPrimary, margin: 0 }}>
          Additional Cost Items
        </h2>
        <span style={{ fontSize: '11px', color: textMuted }}>
          {items.length} item{items.length !== 1 ? 's' : ''}
          {total > 0 && ` · ${formatCurrency(total)}`}
        </span>
      </div>

      <div style={{ padding: '12px 16px' }}>
        {error && (
          <p style={{ fontSize: '12px', color: '#f05252', margin: '0 0 8px 0' }}>{error}</p>
        )}

        {/* Item list */}
        {loading ? (
          <p style={{ fontSize: '12px', color: textMuted }}>Loading...</p>
        ) : items.length === 0 ? (
          <p
            style={{
              fontSize: '12px',
              color: textMuted,
              fontStyle: 'italic',
              margin: '0 0 12px 0',
            }}
          >
            No additional items — add lift, travel, bond, or other costs below.
          </p>
        ) : (
          <div style={{ marginBottom: '12px' }}>
            {items.map((item) =>
              editingId === item.id ? (
                /* Inline edit form */
                <div
                  key={item.id}
                  style={{
                    padding: '8px 0',
                    borderBottom: `1px solid ${dividerColor}`,
                  }}
                >
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <div style={{ width: '160px', flexShrink: 0 }}>
                      <FilterSelect
                        value={ITEM_TYPE_LABELS[editType] ?? editType}
                        onChange={(label) => {
                          const key = Object.keys(ITEM_TYPE_LABELS).find((k) => ITEM_TYPE_LABELS[k] === label) ?? label
                          setEditType(key)
                        }}
                        options={ITEM_TYPE_OPTIONS.map((k) => ITEM_TYPE_LABELS[k])}
                        className="w-full"
                      />
                    </div>
                    <input
                      type="text"
                      placeholder="Description (optional)"
                      value={editDesc}
                      onChange={(e) => setEditDesc(e.target.value)}
                      style={{ ...inputStyle, flex: 1, minWidth: '120px' }}
                    />
                    <input
                      type="number"
                      placeholder="Amount"
                      value={editAmount}
                      onChange={(e) => setEditAmount(e.target.value)}
                      min="0"
                      step="0.01"
                      style={{ ...inputStyle, width: '100px', flexShrink: 0, fontFamily: 'var(--font-jetbrains-mono), monospace' }}
                    />
                    <button
                      onClick={() => void handleEditSave(item.id)}
                      disabled={editSaving || !editAmount}
                      style={{
                        fontSize: '12px',
                        fontWeight: 600,
                        padding: '4px 12px',
                        borderRadius: '6px',
                        border: 'none',
                        cursor: editSaving || !editAmount ? 'not-allowed' : 'pointer',
                        background:
                          editSaving || !editAmount
                            ? 'rgba(161,214,124,0.3)'
                            : 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
                        color: '#080b10',
                        height: '30px',
                      }}
                    >
                      {editSaving ? 'Saving...' : 'Save'}
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      style={{
                        fontSize: '12px',
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        color: textMuted,
                        padding: '4px 8px',
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <ItemRow
                  key={item.id}
                  item={item}
                  isLight={isLight}
                  onEdit={handleEditStart}
                  onDelete={handleDelete}
                />
              )
            )}
          </div>
        )}

        {/* Divider */}
        <div style={{ height: '1px', background: dividerColor, margin: '8px 0 12px' }} />

        {/* Add form */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ width: '160px', flexShrink: 0 }}>
            <FilterSelect
              value={ITEM_TYPE_LABELS[addType] ?? addType}
              onChange={(label) => {
                const key = Object.keys(ITEM_TYPE_LABELS).find((k) => ITEM_TYPE_LABELS[k] === label) ?? label
                setAddType(key)
              }}
              options={ITEM_TYPE_OPTIONS.map((k) => ITEM_TYPE_LABELS[k])}
              className="w-full"
            />
          </div>
          <input
            type="text"
            placeholder="Description (optional)"
            value={addDesc}
            onChange={(e) => setAddDesc(e.target.value)}
            style={{ ...inputStyle, flex: 1, minWidth: '120px' }}
          />
          <input
            type="number"
            placeholder="Amount ($)"
            value={addAmount}
            onChange={(e) => setAddAmount(e.target.value)}
            min="0"
            step="0.01"
            style={{ ...inputStyle, width: '100px', flexShrink: 0, fontFamily: 'var(--font-jetbrains-mono), monospace' }}
          />
          <button
            onClick={() => void handleAdd()}
            disabled={addSubmitting || !addAmount}
            style={{
              fontSize: '12px',
              fontWeight: 600,
              padding: '4px 14px',
              borderRadius: '6px',
              border: 'none',
              cursor: addSubmitting || !addAmount ? 'not-allowed' : 'pointer',
              background:
                addSubmitting || !addAmount
                  ? 'rgba(161,214,124,0.3)'
                  : 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
              color: '#080b10',
              height: '30px',
              flexShrink: 0,
            }}
            onMouseEnter={(e) => {
              if (!addSubmitting && addAmount) {
                (e.currentTarget as HTMLButtonElement).style.opacity = '0.85'
              }
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.opacity = '1'
            }}
          >
            {addSubmitting ? 'Adding...' : 'Add Item'}
          </button>
        </div>

        {addError && (
          <p style={{ fontSize: '12px', color: '#f05252', margin: '6px 0 0 0' }}>{addError}</p>
        )}
      </div>
    </div>
  )
}
