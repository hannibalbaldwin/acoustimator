'use client'

import { useState, useEffect } from 'react'
import type { ScopeResponse } from '@/lib/types'
import { createProduct } from '@/lib/api'

const PRODUCT_CATEGORIES = [
  { value: 'ceiling_tile', label: 'Ceiling Tile' },
  { value: 'wall_panel', label: 'Wall Panel' },
  { value: 'fabric_wall', label: 'Fabric Wall' },
  { value: 'sound_masking', label: 'Sound Masking' },
  { value: 'wood_ceiling', label: 'Wood Ceiling' },
  { value: 'baffle', label: 'Baffle' },
  { value: 'diffuser', label: 'Diffuser' },
  { value: 'other', label: 'Other' },
] as const

interface Props {
  scope: ScopeResponse | null
  isOpen: boolean
  onClose: () => void
  onSaved: (productName: string) => void
  isLight?: boolean
}

export function CatalogEntryModal({ scope, isOpen, onClose, onSaved, isLight = false }: Props) {
  const [canonicalName, setCanonicalName] = useState('')
  const [manufacturer, setManufacturer] = useState('')
  const [category, setCategory] = useState<string>('ceiling_tile')
  const [typicalCostPerSf, setTypicalCostPerSf] = useState('')
  const [nrcRating, setNrcRating] = useState('')
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Reset fields whenever the modal opens with a new scope
  useEffect(() => {
    if (isOpen && scope) {
      setCanonicalName(scope.product_name ?? '')
      setManufacturer('')
      setCategory('ceiling_tile')
      setTypicalCostPerSf('')
      setNrcRating('')
      setNotes('')
      setError(null)
    }
  }, [isOpen, scope])

  if (!isOpen || !scope) return null

  const handleSubmit = async () => {
    if (!canonicalName.trim()) return
    setLoading(true)
    setError(null)

    // Build aliases from extra fields that don't map to the current API schema
    const aliases: string[] = []
    if (manufacturer.trim()) aliases.push(`manufacturer:${manufacturer.trim()}`)
    if (typicalCostPerSf.trim()) aliases.push(`typical_cost_per_sf:${typicalCostPerSf.trim()}`)
    if (nrcRating.trim()) aliases.push(`nrc:${nrcRating.trim()}`)
    if (notes.trim()) aliases.push(`notes:${notes.trim()}`)

    try {
      await createProduct({
        name: canonicalName.trim(),
        canonical_name: canonicalName.trim(),
        category: category,
        aliases,
      })
      onSaved(canonicalName.trim())
      onClose()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to add product to catalog')
    } finally {
      setLoading(false)
    }
  }

  const labelStyle: React.CSSProperties = {
    display: 'block',
    fontSize: '10px',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.09em',
    marginBottom: '6px',
    color: isLight ? '#7890aa' : '#3a4f6a',
  }

  const inputStyle: React.CSSProperties = {
    width: '100%',
    fontSize: '13px',
    borderRadius: '6px',
    padding: '8px 12px',
    outline: 'none',
    background: isLight ? '#f5f7fa' : '#0e1219',
    border: `1px solid ${isLight ? 'rgba(0,0,0,0.12)' : 'rgba(255,255,255,0.1)'}`,
    color: isLight ? '#0f1923' : '#d8e4f5',
  }

  const selectStyle: React.CSSProperties = {
    ...inputStyle,
    cursor: 'pointer',
    appearance: 'none',
    backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='${isLight ? '%237890aa' : '%233a4f6a'}' stroke-width='1.5' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")`,
    backgroundRepeat: 'no-repeat',
    backgroundPosition: 'right 10px center',
    paddingRight: '28px',
    colorScheme: isLight ? 'light' : 'dark',
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 50,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '16px',
        background: 'rgba(0,0,0,0.55)',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '480px',
          borderRadius: '8px',
          padding: '24px',
          background: isLight ? '#ffffff' : '#1e2638',
          border: `1px solid ${isLight ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.1)'}`,
          boxShadow: '0 16px 48px rgba(0,0,0,0.4)',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
          <div>
            <h2
              style={{
                fontSize: '15px',
                fontWeight: 600,
                color: isLight ? '#0f1923' : '#d8e4f5',
                margin: 0,
              }}
            >
              Add Product to Catalog
            </h2>
            <p style={{ fontSize: '12px', color: isLight ? '#7890aa' : '#6b82a0', margin: '3px 0 0' }}>
              {scope.product_name ?? 'Unknown product'}
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: '20px',
              lineHeight: 1,
              color: isLight ? '#7890aa' : '#3a4f6a',
              padding: '2px 4px',
            }}
          >
            ×
          </button>
        </div>

        {/* Fields */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Canonical name */}
          <div>
            <label style={labelStyle}>Canonical Name</label>
            <input
              type="text"
              value={canonicalName}
              onChange={(e) => setCanonicalName(e.target.value)}
              placeholder="e.g. Armstrong Ultima 2x2"
              style={inputStyle}
            />
          </div>

          {/* Manufacturer */}
          <div>
            <label style={labelStyle}>Manufacturer</label>
            <input
              type="text"
              value={manufacturer}
              onChange={(e) => setManufacturer(e.target.value)}
              placeholder="e.g. Armstrong, USG, Rockfon"
              style={inputStyle}
            />
          </div>

          {/* Category */}
          <div>
            <label style={labelStyle}>Category</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              style={selectStyle}
            >
              {PRODUCT_CATEGORIES.map((cat) => (
                <option key={cat.value} value={cat.value}>
                  {cat.label}
                </option>
              ))}
            </select>
          </div>

          {/* Cost + NRC row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label style={labelStyle}>Typical Cost / SF ($)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={typicalCostPerSf}
                onChange={(e) => setTypicalCostPerSf(e.target.value)}
                placeholder="e.g. 3.50"
                style={{ ...inputStyle, fontFamily: 'var(--font-jetbrains-mono), monospace' }}
              />
            </div>
            <div>
              <label style={labelStyle}>
                NRC Rating{' '}
                <span style={{ fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>(optional)</span>
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={nrcRating}
                onChange={(e) => setNrcRating(e.target.value)}
                placeholder="e.g. 0.75"
                style={{ ...inputStyle, fontFamily: 'var(--font-jetbrains-mono), monospace' }}
              />
            </div>
          </div>

          {/* Notes */}
          <div>
            <label style={labelStyle}>Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional notes about this product..."
              rows={3}
              style={{
                ...inputStyle,
                resize: 'vertical',
                minHeight: '72px',
              }}
            />
          </div>
        </div>

        {/* Error */}
        {error && (
          <p style={{ fontSize: '12px', color: '#f05252', marginTop: '12px' }}>{error}</p>
        )}

        {/* Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '20px' }}>
          <button
            onClick={() => void handleSubmit()}
            disabled={loading || !canonicalName.trim()}
            style={{
              flex: 1,
              padding: '9px 0',
              fontSize: '13px',
              fontWeight: 600,
              borderRadius: '6px',
              border: 'none',
              cursor: loading || !canonicalName.trim() ? 'not-allowed' : 'pointer',
              background:
                loading || !canonicalName.trim()
                  ? 'rgba(245,158,11,0.3)'
                  : 'linear-gradient(135deg, #b8760a 0%, #f59e0b 100%)',
              color: '#080b10',
              transition: 'opacity 0.15s',
            }}
          >
            {loading ? 'Adding...' : 'Add to Catalog'}
          </button>
          <button
            onClick={onClose}
            style={{
              padding: '9px 16px',
              fontSize: '13px',
              fontWeight: 500,
              borderRadius: '6px',
              cursor: 'pointer',
              background: isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.07)',
              border: `1px solid ${isLight ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.1)'}`,
              color: isLight ? '#4a5e7a' : '#6b82a0',
            }}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
