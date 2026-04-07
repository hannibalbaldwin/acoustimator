'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'

const navItems = [
  {
    href: '/dashboard',
    label: 'Dashboard',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <rect x="3" y="3" width="7" height="7" rx="1" strokeWidth="2" />
        <rect x="14" y="3" width="7" height="7" rx="1" strokeWidth="2" />
        <rect x="3" y="14" width="7" height="7" rx="1" strokeWidth="2" />
        <rect x="14" y="14" width="7" height="7" rx="1" strokeWidth="2" />
      </svg>
    ),
  },
  {
    href: '/estimates/new',
    label: 'New Estimate',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="9" strokeWidth="2" />
        <path d="M12 8v8M8 12h8" strokeWidth="2" strokeLinecap="round" />
      </svg>
    ),
    highlight: true,
  },
  {
    href: '/projects',
    label: 'Projects',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"
          strokeWidth="2"
        />
      </svg>
    ),
  },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="flex flex-col w-56 min-h-screen bg-zinc-900 text-zinc-100 flex-shrink-0">
      {/* Wordmark */}
      <div className="px-5 py-5 border-b border-zinc-800">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 bg-blue-600 rounded flex items-center justify-center flex-shrink-0">
            <svg className="w-3.5 h-3.5 text-white" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <span className="text-sm font-semibold tracking-tight text-white">Acoustimator</span>
        </div>
        <p className="text-xs text-zinc-500 mt-1 ml-8.5">Commercial Acoustics</p>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500 px-2 mb-2">
          Menu
        </p>
        {navItems.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + '/')
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-2.5 px-2.5 py-2 rounded text-sm transition-colors',
                isActive
                  ? 'bg-zinc-800 text-white'
                  : 'text-zinc-400 hover:text-white hover:bg-zinc-800/60',
                item.highlight && !isActive && 'text-blue-400 hover:text-blue-300'
              )}
            >
              <span className={cn(isActive ? 'text-white' : '', item.highlight && !isActive ? 'text-blue-400' : '')}>
                {item.icon}
              </span>
              {item.label}
              {item.highlight && (
                <span className="ml-auto text-[10px] bg-blue-600 text-white px-1.5 py-0.5 rounded font-medium">
                  NEW
                </span>
              )}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-zinc-800">
        <p className="text-[11px] text-zinc-600 font-mono">v0.6.2-alpha</p>
        <p className="text-[11px] text-zinc-600 mt-0.5">Phase 6.2 — Frontend</p>
      </div>
    </aside>
  )
}
