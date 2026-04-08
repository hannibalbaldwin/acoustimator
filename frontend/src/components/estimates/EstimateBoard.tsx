import type { EstimateListItem } from '@/lib/api'
import { BoardColumn } from './BoardColumn'
import { EstimateCard } from './EstimateCard'

interface EstimateBoardProps {
  estimates: EstimateListItem[]
}

const COLUMNS = [
  { key: 'draft',     name: 'Draft',     accent: '#3a4f6a' },
  { key: 'reviewed',  name: 'Reviewed',  accent: '#60a5fa' },
  { key: 'finalized', name: 'Finalized', accent: '#a1d67c' },
  { key: 'exported',  name: 'Exported',  accent: '#c084fc' },
]

const VALID_KEYS = new Set(COLUMNS.map((c) => c.key))

export function EstimateBoard({ estimates }: EstimateBoardProps) {
  const grouped = new Map<string, EstimateListItem[]>()
  for (const col of COLUMNS) grouped.set(col.key, [])
  for (const est of estimates) {
    const key = VALID_KEYS.has(est.status) ? est.status : 'draft'
    grouped.get(key)!.push(est)
  }

  return (
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
            name={col.name}
            count={items.length}
            accentBorderColor={col.accent}
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
              />
            ))}
          </BoardColumn>
        )
      })}
    </div>
  )
}
