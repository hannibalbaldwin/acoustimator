'use client'

import { useState, useRef, useEffect } from 'react'
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
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
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
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  const userName = status === 'loading' ? '…' : (session?.user?.name ?? 'Commercial Acoustics')
  const userEmail = status === 'loading' ? '' : (session?.user?.email ?? '')
  const userRole = (session?.user as { role?: string } | null | undefined)?.role
  const avatarInitials = status === 'loading' ? '…' : getInitials(session?.user?.name ?? session?.user?.email ?? 'CA')

  // Close popup on outside click
  useEffect(() => {
    function handle(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    if (menuOpen) document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [menuOpen])

  const bg = isLight ? '#f0f4f8' : '#0e1219'
  const border = isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.07)'
  const textPrimary = isLight ? '#1a2335' : '#d8e4f5'
  const textMuted = isLight ? '#7890aa' : '#3a4f6a'
  const textSecondary = isLight ? '#4a5e7a' : '#6b82a0'
  const activeNavBg = isLight ? 'rgba(82,155,30,0.12)' : 'rgba(161,214,124,0.10)'
  const activeNavText = isLight ? '#3d7010' : '#a1d67c'
  const activeNavIcon = isLight ? '#3d7010' : '#a1d67c'
  const hoverNavBg = isLight ? 'rgba(0,0,0,0.04)' : undefined
  const popupBg = isLight ? '#ffffff' : '#1e2638'
  const popupBorder = isLight ? 'rgba(0,0,0,0.10)' : 'rgba(255,255,255,0.10)'

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
                  className="flex items-center gap-2.5 px-2.5 py-2 rounded-[6px] text-[13px] font-medium transition-all duration-100"
                  style={
                    isActive
                      ? { background: activeNavBg, borderLeft: '2px solid #a1d67c', paddingLeft: '10px', color: activeNavText }
                      : { borderLeft: '2px solid transparent', color: textSecondary }
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
          </div>
        </nav>

        {/* ── Account row (bottom) ── */}
        <div ref={menuRef} style={{ borderTop: `1px solid ${border}`, position: 'relative' }}>

          {/* Popup menu — renders above the account row */}
          {menuOpen && (
            <div
              style={{
                position: 'absolute',
                bottom: 'calc(100% + 6px)',
                left: 12,
                right: 12,
                background: popupBg,
                border: `1px solid ${popupBorder}`,
                borderRadius: 10,
                boxShadow: isLight
                  ? '0 8px 24px rgba(0,0,0,0.12), 0 1px 4px rgba(0,0,0,0.06)'
                  : '0 8px 32px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.07)',
                overflow: 'hidden',
                zIndex: 60,
              }}
            >
              {/* Theme toggle row */}
              <div
                className="flex items-center justify-between px-3 py-2.5"
                style={{ borderBottom: `1px solid ${popupBorder}` }}
              >
                <div className="flex items-center gap-2">
                  <svg className="w-[13px] h-[13px]" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: textSecondary }}>
                    {isLight ? (
                      <path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.36-6.36-.71.71M6.34 17.66l-.7.7M17.66 17.66l-.71-.7M6.34 6.34l-.7-.71M12 5a7 7 0 1 0 0 14A7 7 0 0 0 12 5z" strokeWidth="1.75" strokeLinecap="round" />
                    ) : (
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
                    width: 34,
                    height: 19,
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
                      width: 15,
                      height: 15,
                      borderRadius: '50%',
                      background: isLight ? '#080b10' : '#d8e4f5',
                      transition: 'transform 200ms',
                      transform: isLight ? 'translateX(15px)' : 'translateX(0)',
                      display: 'block',
                    }}
                  />
                </button>
              </div>

              {/* Admin page — only for admins */}
              {userRole === 'admin' && (
                <Link
                  href="/admin/users"
                  onClick={() => setMenuOpen(false)}
                  className="flex items-center gap-2.5 px-3 py-2.5 text-[13px] font-medium w-full transition-colors"
                  style={{
                    color: textSecondary,
                    borderBottom: `1px solid ${popupBorder}`,
                  }}
                  onMouseEnter={(e) => ((e.currentTarget as HTMLAnchorElement).style.color = textPrimary)}
                  onMouseLeave={(e) => ((e.currentTarget as HTMLAnchorElement).style.color = textSecondary)}
                >
                  <svg className="w-[14px] h-[14px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  Admin Panel
                </Link>
              )}

              {/* Sign out */}
              <button
                onClick={() => signOut({ callbackUrl: '/login' })}
                className="flex items-center gap-2.5 px-3 py-2.5 text-[13px] font-medium w-full transition-colors"
                style={{ color: textSecondary, background: 'transparent', border: 'none', cursor: 'pointer', textAlign: 'left' }}
                onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.color = '#ef4444')}
                onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.color = textSecondary)}
              >
                <svg className="w-[14px] h-[14px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
                  <polyline points="16 17 21 12 16 7" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
                  <line x1="21" y1="12" x2="9" y2="12" strokeWidth="1.75" strokeLinecap="round" />
                </svg>
                Sign Out
              </button>
            </div>
          )}

          {/* Account button */}
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            className="w-full flex items-center gap-2.5 px-4 py-3 transition-colors text-left"
            style={{
              background: menuOpen
                ? isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.04)'
                : 'transparent',
              border: 'none',
              cursor: 'pointer',
            }}
            onMouseEnter={(e) => {
              if (!menuOpen) (e.currentTarget as HTMLButtonElement).style.background = isLight ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.03)'
            }}
            onMouseLeave={(e) => {
              if (!menuOpen) (e.currentTarget as HTMLButtonElement).style.background = 'transparent'
            }}
          >
            {/* Avatar */}
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-[11px] font-bold"
              style={{
                background: 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
                color: '#080b10',
              }}
            >
              {avatarInitials}
            </div>
            {/* Name + email */}
            <div className="flex-1 min-w-0 text-left">
              <p className="text-[12px] font-semibold leading-tight truncate" style={{ color: textPrimary }}>
                {userName}
              </p>
              {userEmail && (
                <p className="text-[10px] leading-tight truncate mt-0.5" style={{ color: textMuted }}>
                  {userEmail}
                </p>
              )}
            </div>
            {/* Chevron */}
            <svg
              className="w-[12px] h-[12px] flex-shrink-0 transition-transform"
              style={{ color: textMuted, transform: menuOpen ? 'rotate(180deg)' : 'rotate(0deg)' }}
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path d="M19 9l-7 7-7-7" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </aside>
    </>
  )
}
