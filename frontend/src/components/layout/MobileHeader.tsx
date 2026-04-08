'use client'

import Link from 'next/link'

interface MobileHeaderProps {
  onToggle: () => void
}

export function MobileHeader({ onToggle }: MobileHeaderProps) {
  return (
    <header
      className="md:hidden fixed top-0 left-0 right-0 z-40 flex items-center h-12 px-3 gap-3"
      style={{
        background: '#0e1219',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
      }}
    >
      {/* Hamburger */}
      <button
        onClick={onToggle}
        className="w-8 h-8 flex items-center justify-center rounded-[6px] flex-shrink-0 transition-colors"
        style={{ color: '#6b82a0' }}
        onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.color = '#d8e4f5')}
        onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.color = '#6b82a0')}
        aria-label="Toggle navigation"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path d="M4 6h16M4 12h16M4 18h16" strokeWidth="1.75" strokeLinecap="round" />
        </svg>
      </button>

      {/* Wordmark */}
      <div className="flex items-center gap-2 flex-1">
        <div
          className="w-6 h-6 rounded-[5px] flex items-center justify-center flex-shrink-0"
          style={{
            background: 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
          }}
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none">
            <path
              d="M1 8h1.5M13.5 8H15M4 5v6M12 5v6M6.5 3v10M9.5 3v10"
              stroke="white"
              strokeWidth="1.6"
              strokeLinecap="round"
            />
          </svg>
        </div>
        <span className="text-[13px] font-semibold tracking-tight" style={{ color: '#d8e4f5' }}>
          Acoustimator
        </span>
      </div>

      {/* New Estimate — compact */}
      <Link
        href="/estimates/new"
        className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-semibold rounded-[6px] flex-shrink-0 transition-all"
        style={{
          background: 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
          color: '#080b10',
        }}
      >
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path d="M12 5v14M5 12h14" strokeWidth="2.5" strokeLinecap="round" />
        </svg>
        New
      </Link>
    </header>
  )
}
