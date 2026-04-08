'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'

const navItems = [
  {
    href: '/dashboard',
    label: 'Dashboard',
    icon: (
      <svg className="w-[15px] h-[15px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <rect x="3" y="3" width="7" height="7" rx="1.5" strokeWidth="1.75" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" strokeWidth="1.75" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" strokeWidth="1.75" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" strokeWidth="1.75" />
      </svg>
    ),
  },
  {
    href: '/estimates/new',
    label: 'New Estimate',
    icon: (
      <svg className="w-[15px] h-[15px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path d="M12 5v14M5 12h14" strokeWidth="2" strokeLinecap="round" />
      </svg>
    ),
    primary: true,
  },
  {
    href: '/projects',
    label: 'Projects',
    icon: (
      <svg className="w-[15px] h-[15px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"
          strokeWidth="1.75"
        />
      </svg>
    ),
  },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside
      className="flex flex-col w-[220px] min-h-screen flex-shrink-0"
      style={{
        background: '#0e1219',
        borderRight: '1px solid rgba(255,255,255,0.07)',
      }}
    >
      {/* ── Logo / Wordmark ── */}
      <div
        className="px-5 py-[18px]"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.07)' }}
      >
        <div className="flex items-center gap-2.5">
          {/* Sound-wave logo mark */}
          <div
            className="w-7 h-7 rounded-[6px] flex items-center justify-center flex-shrink-0"
            style={{
              background: 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
            }}
          >
            <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none">
              <path
                d="M1 8h1.5M13.5 8H15M4 5v6M12 5v6M6.5 3v10M9.5 3v10"
                stroke="white"
                strokeWidth="1.6"
                strokeLinecap="round"
              />
            </svg>
          </div>
          <div>
            <p className="text-[13px] font-semibold tracking-tight leading-none text-[#d8e4f5]">
              Acoustimator
            </p>
            <p className="text-[10px] mt-0.5 leading-none" style={{ color: '#3a4f6a' }}>
              Commercial Acoustics
            </p>
          </div>
        </div>
      </div>

      {/* ── Navigation ── */}
      <nav className="flex-1 px-3 py-4">
        <p
          className="text-[10px] font-semibold uppercase tracking-[0.1em] px-2.5 mb-2.5"
          style={{ color: '#3a4f6a' }}
        >
          Navigation
        </p>

        <div className="space-y-0.5">
          {navItems.map((item) => {
            const isActive =
              pathname === item.href || pathname.startsWith(item.href + '/')

            if (item.primary) {
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-2.5 px-2.5 py-2 rounded-[6px] text-[13px] font-medium transition-all duration-100',
                    isActive
                      ? 'text-[#080b10]'
                      : 'text-[#d8e4f5] hover:text-[#080b10]'
                  )}
                  style={
                    isActive
                      ? {
                          background: 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
                          boxShadow: '0 0 16px rgba(161,214,124,0.2)',
                        }
                      : {
                          background: 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
                          boxShadow: '0 0 16px rgba(161,214,124,0.2)',
                        }
                  }
                >
                  <span>{item.icon}</span>
                  {item.label}
                </Link>
              )
            }

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'flex items-center gap-2.5 px-2.5 py-2 rounded-[6px] text-[13px] font-medium transition-all duration-100',
                  isActive
                    ? 'text-[#a1d67c]'
                    : 'text-[#6b82a0] hover:text-[#d8e4f5]'
                )}
                style={
                  isActive
                    ? {
                        background: 'rgba(161, 214, 124, 0.10)',
                        borderLeft: '2px solid #a1d67c',
                        paddingLeft: '10px',
                      }
                    : {
                        borderLeft: '2px solid transparent',
                      }
                }
              >
                <span className={isActive ? 'text-[#a1d67c]' : ''}>{item.icon}</span>
                {item.label}
              </Link>
            )
          })}
        </div>
      </nav>

      {/* ── Footer ── */}
      <div
        className="px-5 py-4"
        style={{ borderTop: '1px solid rgba(255,255,255,0.07)' }}
      >
        <div className="flex items-center gap-1.5 mb-1">
          <div
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: '#a1d67c' }}
          />
          <p className="text-[11px] font-mono" style={{ color: '#3a4f6a' }}>
            v0.6.2-alpha
          </p>
        </div>
        <p className="text-[11px]" style={{ color: '#3a4f6a' }}>
          Phase 6 — Web App
        </p>
      </div>
    </aside>
  )
}
