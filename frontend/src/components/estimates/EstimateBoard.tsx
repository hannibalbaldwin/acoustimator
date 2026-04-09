'use client'

import { useState, useEffect } from 'react'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
} from '@dnd-kit/core'
import type { EstimateListItem } from '@/lib/api'
import { updateEstimateStatus } from '@/lib/api'
import { BoardColumn } from './BoardColumn'
import { EstimateCard } from './EstimateCard'

interface EstimateBoardProps {
  estimates: EstimateListItem[]
  onStatusChange?: (id: string, newStatus: string) => void
}

const COLUMNS = [
  { key: 'draft',     label: 'Draft',     accent: '#3a4f6a' },
  { key: 'reviewed',  label: 'Reviewed',  accent: '#60a5fa' },
  { key: 'finalized', label: 'Finalized', accent: '#a1d67c' },
  { key: 'exported',  label: 'Exported',  accent: '#c084fc' },
]

const STATUS_ORDER = ['draft', 'reviewed', 'finalized', 'exported'] as const
const VALID_KEYS = new Set(COLUMNS.map((c) => c.key))

export function EstimateBoard({ estimates: initialEstimates, onStatusChange }: EstimateBoardProps) {
  const [localEstimates, setLocalEstimates] = useState<EstimateListItem[]>(initialEstimates)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [overColumnKey, setOverColumnKey] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  // Sync when parent passes new estimates (e.g. after a re-fetch)
  useEffect(() => {
    setLocalEstimates(initialEstimates)
  }, [initialEstimates])

  // Auto-dismiss toast after 4s
  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 4000)
    return () => clearTimeout(t)
  }, [toast])

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  )

  const grouped = new Map<string, EstimateListItem[]>()
  for (const col of COLUMNS) grouped.set(col.key, [])
  for (const est of localEstimates) {
    const key = VALID_KEYS.has(est.status) ? est.status : 'draft'
    grouped.get(key)!.push(est)
  }

  const activeEstimate = activeId ? localEstimates.find((e) => e.id === activeId) ?? null : null

  function handleDragStart(event: DragStartEvent) {
    setActiveId(event.active.id as string)
  }

  function handleDragOver(event: DragOverEvent) {
    setOverColumnKey(event.over ? String(event.over.id) : null)
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event
    setActiveId(null)
    setOverColumnKey(null)

    if (!over) return

    const draggedId = active.id as string
    const targetColumn = over.id as string

    if (!VALID_KEYS.has(targetColumn)) return

    const estimate = localEstimates.find((e) => e.id === draggedId)
    if (!estimate) return
    if (estimate.status === targetColumn) return

    // Enforce forward-only drag (backward is handled by card buttons)
    const currentIdx = STATUS_ORDER.indexOf(estimate.status as typeof STATUS_ORDER[number])
    const targetIdx = STATUS_ORDER.indexOf(targetColumn as typeof STATUS_ORDER[number])
    if (targetIdx < currentIdx) {
      setToast('Drag forward only — use the ← button on the card to move backward.')
      return
    }

    // Optimistic update
    const previousEstimates = localEstimates
    setLocalEstimates((prev) =>
      prev.map((e) => e.id === draggedId ? { ...e, status: targetColumn } : e)
    )

    try {
      await updateEstimateStatus(draggedId, targetColumn)
      onStatusChange?.(draggedId, targetColumn)
    } catch (err: unknown) {
      // Revert on error
      setLocalEstimates(previousEstimates)
      // Extract the 422 message from "API 422: {...}"
      let msg = err instanceof Error ? err.message : 'Failed to update status'
      try {
        const jsonStart = msg.indexOf('{')
        if (jsonStart !== -1) {
          const parsed = JSON.parse(msg.slice(jsonStart)) as { detail?: string }
          if (parsed.detail) msg = parsed.detail
        }
      } catch { /* ignore parse errors */ }
      setToast(msg)
    }
  }

  async function handleCardStatusChange(id: string, newStatus: string) {
    const estimate = localEstimates.find((e) => e.id === id)
    if (!estimate) return

    const previousEstimates = localEstimates
    setLocalEstimates((prev) =>
      prev.map((e) => e.id === id ? { ...e, status: newStatus } : e)
    )

    try {
      await updateEstimateStatus(id, newStatus)
      onStatusChange?.(id, newStatus)
    } catch (err: unknown) {
      setLocalEstimates(previousEstimates)
      let msg = err instanceof Error ? err.message : 'Failed to update status'
      try {
        const jsonStart = msg.indexOf('{')
        if (jsonStart !== -1) {
          const parsed = JSON.parse(msg.slice(jsonStart)) as { detail?: string }
          if (parsed.detail) msg = parsed.detail
        }
      } catch { /* ignore parse errors */ }
      setToast(msg)
    }
  }

  return (
    <div style={{ position: 'relative' }}>
      <DndContext
        sensors={sensors}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
      >
        <div
          style={{
            display: 'flex',
            gap: '16px',
            overflowX: 'auto',
            paddingBottom: '16px',
          }}
        >
          {COLUMNS.map((col) => {
            const items = grouped.get(col.key)!
            return (
              <BoardColumn
                key={col.key}
                columnKey={col.key}
                name={col.label}
                count={items.length}
                accentBorderColor={col.accent}
                isOver={overColumnKey === col.key}
              >
                {items.map((est) => (
                  <EstimateCard
                    key={est.id}
                    id={est.id}
                    project_name={est.project_name}
                    gc_name={est.gc_name}
                    scope_types={est.scope_types}
                    total_cost={est.total_cost}
                    confidence_level={est.confidence_level}
                    status={est.status}
                    created_at={est.created_at}
                    isDragging={activeId === est.id}
                    onStatusChange={handleCardStatusChange}
                  />
                ))}
              </BoardColumn>
            )
          })}
        </div>

        <DragOverlay>
          {activeEstimate ? (
            <div style={{ opacity: 0.85, transform: 'scale(1.03)', pointerEvents: 'none' }}>
              <EstimateCard
                id={activeEstimate.id}
                project_name={activeEstimate.project_name}
                gc_name={activeEstimate.gc_name}
                scope_types={activeEstimate.scope_types}
                total_cost={activeEstimate.total_cost}
                confidence_level={activeEstimate.confidence_level}
                status={activeEstimate.status}
                created_at={activeEstimate.created_at}
                isDragging={false}
                onStatusChange={handleCardStatusChange}
              />
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>

      {/* Error toast */}
      {toast && (
        <div
          style={{
            position: 'absolute',
            bottom: '24px',
            left: '50%',
            transform: 'translateX(-50%)',
            background: 'rgba(245,158,11,0.12)',
            border: '1px solid rgba(245,158,11,0.4)',
            borderRadius: '8px',
            padding: '10px 16px',
            fontSize: '13px',
            color: '#d97706',
            maxWidth: '420px',
            whiteSpace: 'pre-wrap',
            textAlign: 'center',
            zIndex: 100,
            boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
          }}
        >
          {toast}
        </div>
      )}
    </div>
  )
}
