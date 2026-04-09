'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import { useTheme } from '@/components/ThemeProvider'
import { useSession, signOut } from 'next-auth/react'

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
    href: '/estimates',
    label: 'Estimates',
    icon: (
      <svg className="w-[15px] h-[15px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path d="M9 12h6M9 16h6M9 8h6M5 4h14a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z" strokeWidth="1.75" strokeLinecap="round" />
      </svg>
    ),
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

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) {
    // Could be an email — take first two chars
    return parts[0].slice(0, 2).toUpperCase()
  }
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

interface SidebarProps {
  isOpen?: boolean
  onClose?: () => void
}

export function Sidebar({ isOpen = false, onClose }: SidebarProps) {
  const pathname = usePathname()
  const { theme, toggle } = useTheme()
  const isLight = theme === 'light'
  const { data: session, status } = useSession()

  const userName =
    status === 'loading'
      ? 'Loading…'
      : session?.user?.name ?? session?.user?.email ?? 'Commercial Acoustics'
  const userRole = (session?.user as { role?: string } | null | undefined)?.role
  const avatarInitials =
    status === 'loading' ? '…' : getInitials(session?.user?.name ?? session?.user?.email ?? 'Commercial Acoustics')

  const bg = isLight ? '#f0f4f8' : '#0e1219'
  const border = isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.07)'
  const textPrimary = isLight ? '#1a2335' : '#d8e4f5'
  const textMuted = isLight ? '#7890aa' : '#3a4f6a'
  const textSecondary = isLight ? '#4a5e7a' : '#6b82a0'
  const activeNavBg = isLight ? 'rgba(82,155,30,0.12)' : 'rgba(161,214,124,0.10)'
  const activeNavText = isLight ? '#3d7010' : '#a1d67c'
  const activeNavIcon = isLight ? '#3d7010' : '#a1d67c'
  const hoverNavBg = isLight ? 'rgba(0,0,0,0.04)' : undefined

  return (
    <>
      {/* Mobile overlay backdrop */}
      {onClose && (
        <div
          className={cn(
            'fixed inset-0 z-40 bg-black/50 md:hidden transition-opacity duration-200',
            isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
          )}
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar panel */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex flex-col w-[220px] min-h-screen flex-shrink-0 transition-transform duration-200',
          'md:static md:translate-x-0 md:z-auto md:transition-none',
          isOpen ? 'translate-x-0' : '-translate-x-full'
        )}
        style={{ background: bg, borderRight: `1px solid ${border}` }}
      >
        {/* ── Logo / Wordmark ── */}
        <div className="px-5 py-[18px]" style={{ borderBottom: `1px solid ${border}` }}>
          <div className="flex items-center gap-2.5">
            <div
              className="w-7 h-7 rounded-[6px] flex items-center justify-center flex-shrink-0"
              style={{ background: 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)' }}
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
              <p className="text-[13px] font-semibold tracking-tight leading-none" style={{ color: textPrimary }}>
                Acoustimator
              </p>
              <p className="text-[10px] mt-0.5 leading-none" style={{ color: textMuted }}>
                Commercial Acoustics
              </p>
            </div>
          </div>
        </div>

        {/* ── Navigation ── */}
        <nav className="flex-1 px-3 py-4">
          <p
            className="text-[10px] font-semibold uppercase tracking-[0.1em] px-2.5 mb-2.5"
            style={{ color: textMuted }}
          >
            Navigation
          </p>

          <div className="space-y-0.5">
            {navItems.map((item) => {
              const isActive = pathname === item.href || pathname.startsWith(item.href + '/')

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onClose}
                  className={cn(
                    'flex items-center gap-2.5 px-2.5 py-2 rounded-[6px] text-[13px] font-medium transition-all duration-100',
                  )}
                  style={
                    isActive
                      ? {
                          background: activeNavBg,
                          borderLeft: '2px solid #a1d67c',
                          paddingLeft: '10px',
                          color: activeNavText,
                        }
                      : {
                          borderLeft: '2px solid transparent',
                          color: textSecondary,
                          ...(hoverNavBg ? {} : {}),
                        }
                  }
                  onMouseEnter={(e) => {
                    if (!isActive && hoverNavBg) {
                      (e.currentTarget as HTMLAnchorElement).style.background = hoverNavBg
                      ;(e.currentTarget as HTMLAnchorElement).style.color = textPrimary
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) {
                      (e.currentTarget as HTMLAnchorElement).style.background = ''
                      ;(e.currentTarget as HTMLAnchorElement).style.color = textSecondary
                    }
                  }}
                >
                  <span style={{ color: isActive ? activeNavIcon : textSecondary }}>{item.icon}</span>
                  {item.label}
                </Link>
              )
            })}

            {/* Admin link — only shown for admin users */}
            {userRole === 'admin' && (
              <Link
                href="/admin/users"
                onClick={onClose}
                className="flex items-center gap-2.5 px-2.5 py-2 rounded-[6px] text-[13px] font-medium transition-all duration-100"
                style={
                  pathname === '/admin/users' || pathname.startsWith('/admin/')
                    ? {
                        background: activeNavBg,
                        borderLeft: '2px solid #a1d67c',
                        paddingLeft: '10px',
                        color: activeNavText,
                      }
                    : {
                        borderLeft: '2px solid transparent',
                        color: textSecondary,
                      }
                }
                onMouseEnter={(e) => {
                  const isActive = pathname === '/admin/users' || pathname.startsWith('/admin/')
                  if (!isActive && hoverNavBg) {
                    (e.currentTarget as HTMLAnchorElement).style.background = hoverNavBg
                    ;(e.currentTarget as HTMLAnchorElement).style.color = textPrimary
                  }
                }}
                onMouseLeave={(e) => {
                  const isActive = pathname === '/admin/users' || pathname.startsWith('/admin/')
                  if (!isActive) {
                    (e.currentTarget as HTMLAnchorElement).style.background = ''
                    ;(e.currentTarget as HTMLAnchorElement).style.color = textSecondary
                  }
                }}
              >
                <span
                  style={{
                    color: pathname === '/admin/users' || pathname.startsWith('/admin/')
                      ? activeNavIcon
                      : textSecondary,
                  }}
                >
                  <svg className="w-[15px] h-[15px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"
                      strokeWidth="1.75"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </span>
                Admin
              </Link>
            )}
          </div>
        </nav>

        {/* ── Account Settings ── */}
        <div style={{ borderTop: `1px solid ${border}` }}>
          {/* Theme toggle row */}
          <div className="px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <svg className="w-[14px] h-[14px]" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: textSecondary }}>
                {isLight ? (
                  /* sun icon */
                  <path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.36-6.36-.71.71M6.34 17.66l-.7.7M17.66 17.66l-.71-.7M6.34 6.34l-.7-.71M12 5a7 7 0 1 0 0 14A7 7 0 0 0 12 5z" strokeWidth="1.75" strokeLinecap="round" />
                ) : (
                  /* moon icon */
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
                )}
              </svg>
              <span className="text-[12px] font-medium" style={{ color: textSecondary }}>
                {isLight ? 'Light mode' : 'Dark mode'}
              </span>
            </div>

            {/* Toggle pill */}
            <button
              onClick={toggle}
              aria-label="Toggle theme"
              style={{
                position: 'relative',
                flexShrink: 0,
                width: 36,
                height: 20,
                borderRadius: 9999,
                background: isLight ? '#a1d67c' : 'rgba(255,255,255,0.12)',
                border: 'none',
                cursor: 'pointer',
                padding: 0,
                transition: 'background 200ms',
                overflow: 'hidden',
              }}
            >
              <span
                style={{
                  position: 'absolute',
                  top: 2,
                  left: 2,
                  width: 16,
                  height: 16,
                  borderRadius: '50%',
                  background: isLight ? '#080b10' : '#d8e4f5',
                  transition: 'transform 200ms',
                  transform: isLight ? 'translateX(16px)' : 'translateX(0)',
                  display: 'block',
                }}
              />
            </button>
          </div>

          {/* Account row */}
          <div
            className="px-4 py-3 flex items-center gap-2.5"
            style={{ borderTop: `1px solid ${border}` }}
          >
            {/* Avatar */}
            <div
              className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 text-[11px] font-bold"
              style={{
                background: 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
                color: '#080b10',
              }}
            >
              {avatarInitials}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[12px] font-medium leading-none truncate" style={{ color: textPrimary }}>
                {userName}
              </p>
              <p className="text-[10px] mt-0.5 leading-none" style={{ color: textMuted }}>
                {userRole === 'admin' ? 'Admin · v0.6.2-alpha' : 'v0.6.2-alpha · Phase 6'}
              </p>
            </div>
            {/* Settings gear — links to /settings */}
            <Link
              href="/settings"
              aria-label="Account settings"
              className="flex-shrink-0 p-1 rounded-[4px] transition-colors"
              style={{ color: textMuted }}
              onMouseEnter={(e) => ((e.currentTarget as HTMLAnchorElement).style.color = textPrimary)}
              onMouseLeave={(e) => ((e.currentTarget as HTMLAnchorElement).style.color = textMuted)}
            >
              <svg className="w-[14px] h-[14px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z" strokeWidth="1.75" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" strokeWidth="1.75" />
              </svg>
            </Link>
            {/* Logout button */}
            <button
              onClick={() => signOut({ callbackUrl: '/login' })}
              aria-label="Sign out"
              className="flex-shrink-0 p-1 rounded-[4px] transition-colors"
              style={{ color: textMuted, background: 'transparent', border: 'none', cursor: 'pointer' }}
              onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.color = '#ef4444')}
              onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.color = textMuted)}
            >
              {/* Door/logout icon */}
              <svg className="w-[14px] h-[14px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
                <polyline points="16 17 21 12 16 7" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
                <line x1="21" y1="12" x2="9" y2="12" strokeWidth="1.75" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        </div>
      </aside>
    </>
  )
}
