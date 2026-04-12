import React from 'react'

export interface ProjectTypeBadgeProps {
  type: string | null | undefined
  className?: string
}

interface TypeConfig {
  color: string
  label: string
  icon: React.ReactElement
}

function toTitleCase(str: string): string {
  return str
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

// 12×12 inline SVG icons
const icons: Record<string, React.ReactElement> = {
  commercial_office: (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
      {/* Building with windows */}
      <rect x="1" y="2" width="10" height="10" rx="0.5" fill="none" stroke="currentColor" strokeWidth="1" />
      <rect x="3" y="4" width="2" height="2" rx="0.3" />
      <rect x="7" y="4" width="2" height="2" rx="0.3" />
      <rect x="3" y="7" width="2" height="2" rx="0.3" />
      <rect x="7" y="7" width="2" height="2" rx="0.3" />
      <rect x="4.5" y="9" width="3" height="3" rx="0.3" />
    </svg>
  ),
  healthcare: (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
      {/* Plus / cross */}
      <rect x="4.5" y="1" width="3" height="10" rx="1" />
      <rect x="1" y="4.5" width="10" height="3" rx="1" />
    </svg>
  ),
  education: (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
      {/* Graduation cap */}
      <polygon points="6,1.5 11,4.5 6,7.5 1,4.5" />
      <path d="M3.5 5.8 v2.7 Q6 10 8.5 8.5 v-2.7" />
      <line x1="11" y1="4.5" x2="11" y2="7.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  ),
  worship: (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
      {/* Arch / chapel */}
      <path d="M2 11 L2 6 Q2 1.5 6 1.5 Q10 1.5 10 6 L10 11 Z" fill="none" stroke="currentColor" strokeWidth="1" />
      <line x1="6" y1="1.5" x2="6" y2="0" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <line x1="5" y1="0.8" x2="7" y2="0.8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <rect x="4.5" y="7" width="3" height="4" />
    </svg>
  ),
  hospitality: (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
      {/* Bed */}
      <rect x="1" y="6" width="10" height="4" rx="1" />
      <rect x="1" y="4" width="4.5" height="3" rx="1" />
      <line x1="1" y1="5.5" x2="1" y2="11" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <line x1="11" y1="5.5" x2="11" y2="11" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  ),
  residential: (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
      {/* House silhouette */}
      <polygon points="6,1 11,5.5 11,11 1,11 1,5.5" />
      <polygon points="6,1 11,5.5 11,11 1,11 1,5.5" fill="none" stroke="currentColor" strokeWidth="1" />
      <rect x="4.5" y="7.5" width="3" height="3.5" fill="white" fillOpacity="0.35" />
    </svg>
  ),
  government: (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
      {/* Columns / pillar */}
      <rect x="1" y="10" width="10" height="1.2" rx="0.3" />
      <rect x="1" y="1" width="10" height="1.2" rx="0.3" />
      <rect x="2" y="2.5" width="1.8" height="7" rx="0.5" />
      <rect x="5.1" y="2.5" width="1.8" height="7" rx="0.5" />
      <rect x="8.2" y="2.5" width="1.8" height="7" rx="0.5" />
    </svg>
  ),
  entertainment: (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
      {/* Star */}
      <polygon points="6,1 7.4,4.4 11,4.8 8.5,7.3 9.2,11 6,9.2 2.8,11 3.5,7.3 1,4.8 4.6,4.4" />
    </svg>
  ),
  mixed_use: (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
      {/* Layered squares */}
      <rect x="1" y="7.5" width="10" height="3.5" rx="0.6" />
      <rect x="2" y="4.5" width="8" height="3.5" rx="0.6" />
      <rect x="3" y="1.5" width="6" height="3.5" rx="0.6" />
    </svg>
  ),
  other: (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor" aria-hidden="true">
      {/* Tag / label */}
      <path d="M1.5 1.5 L6.5 1.5 L10.5 5.5 L6.5 9.5 L1.5 9.5 Z" fill="none" stroke="currentColor" strokeWidth="1" strokeLinejoin="round" />
      <circle cx="4" cy="4" r="1" />
    </svg>
  ),
}

const TYPE_CONFIG: Record<string, TypeConfig> = {
  commercial_office: { color: '#60a5fa', label: 'Commercial Office', icon: icons.commercial_office },
  healthcare:        { color: '#f87171', label: 'Healthcare',        icon: icons.healthcare },
  education:         { color: '#fbbf24', label: 'Education',         icon: icons.education },
  worship:           { color: '#a78bfa', label: 'Worship',           icon: icons.worship },
  hospitality:       { color: '#fb923c', label: 'Hospitality',       icon: icons.hospitality },
  residential:       { color: '#34d399', label: 'Residential',       icon: icons.residential },
  government:        { color: '#94a3b8', label: 'Government',        icon: icons.government },
  entertainment:     { color: '#f472b6', label: 'Entertainment',     icon: icons.entertainment },
  mixed_use:         { color: '#2dd4bf', label: 'Mixed Use',         icon: icons.mixed_use },
  other:             { color: '#6b7280', label: 'Other',             icon: icons.other },
}

const FALLBACK_ICON = icons.other

export function ProjectTypeBadge({ type, className }: ProjectTypeBadgeProps) {
  if (type == null) return null

  const normalised = type.toLowerCase().replace(/\s+/g, '_')
  const config = TYPE_CONFIG[normalised]
  const color  = config?.color ?? '#6b7280'
  const label  = config?.label ?? toTitleCase(type)
  const icon   = config?.icon  ?? FALLBACK_ICON

  const style: React.CSSProperties = {
    display:        'inline-flex',
    alignItems:     'center',
    gap:            '5px',
    padding:        '2px 8px',
    borderRadius:   '999px',
    fontSize:       '11px',
    fontWeight:     500,
    lineHeight:     '18px',
    whiteSpace:     'nowrap',
    background:     `${color}18`,
    border:         `1px solid ${color}40`,
    color,
  }

  return (
    <span style={style} className={className}>
      <span style={{ flexShrink: 0, display: 'flex' }}>{icon}</span>
      {label}
    </span>
  )
}
