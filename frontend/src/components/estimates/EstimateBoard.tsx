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

type StatusKey = typeof STATUS_ORDER[number]

/**
 * Returns null if the move is valid, or a short reason string if it will fail
 * validation on the backend. Uses the pre-validation flags from the API so the
 * user sees feedback before they drop.
 */
function getDropBlockReason(
  estimate: EstimateListItem,
  targetColumn: string,
): string | null {
  if (targetColumn === estimate.status) return null

  if (targetColumn === 'reviewed') {
    if (!estimate.has_scope_with_sf) return 'Needs a scope with SF > 0'
  }
  // Finalized AND Exported both require accepted scope + GC name (can't skip Finalized)
  if (targetColumn === 'finalized' || targetColumn === 'exported') {
    if (!estimate.has_accepted_scope) return 'Accept at least one scope first'
    if (!estimate.gc_name) return 'GC name required'
  }
  return null
}

export function EstimateBoard({ estimates: initialEstimates, onStatusChange }: EstimateBoardProps) {
  const [localEstimates, setLocalEstimates] = useState<EstimateListItem[]>(initialEstimates)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [overColumnKey, setOverColumnKey] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  useEffect(() => {
    setLocalEstimates(initialEstimates)
  }, [initialEstimates])

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

  // Compute block reason for the column currently being hovered during drag
  const overBlockReason = (activeEstimate && overColumnKey)
    ? getDropBlockReason(activeEstimate, overColumnKey)
    : null

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

    // Block if pre-validation says it won't pass
    const blockReason = getDropBlockReason(estimate, targetColumn)
    if (blockReason) {
      setToast(blockReason)
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
            const isOver = overColumnKey === col.key
            const isSameColumn = activeEstimate?.status === col.key
            // Show amber when hovering a column that will fail validation
            const blockReason = isOver && activeEstimate && !isSameColumn
              ? getDropBlockReason(activeEstimate, col.key)
              : null

            return (
              <BoardColumn
                key={col.key}
                columnKey={col.key}
                name={col.label}
                count={items.length}
                accentBorderColor={col.accent}
                isOver={isOver && !isSameColumn}
                isBlocked={!!blockReason}
                blockReason={blockReason ?? undefined}
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

      {/* Toast */}
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
