'use client'

import { useSession, signOut } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import Link from 'next/link'
import { useTheme } from '@/components/ThemeProvider'

export default function SettingsPage() {
  const { data: session, status } = useSession()
  const router = useRouter()
  const { theme, toggle } = useTheme()
  const isLight = theme === 'light'

  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/login')
    }
  }, [status, router])

  // Colors
  const bg = isLight ? '#f0f4f8' : '#0e1219'
  const cardBg = isLight ? '#ffffff' : '#131822'
  const border = isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.07)'
  const innerBorder = isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.06)'
  const textPrimary = isLight ? '#1a2335' : '#d8e4f5'
  const textMuted = isLight ? '#7890aa' : '#3a4f6a'
  const textSecondary = isLight ? '#4a5e7a' : '#6b82a0'
  const userRole = (session?.user as { role?: string } | null | undefined)?.role

  if (status === 'loading') {
    return (
      <div
        className="px-4 py-6 md:px-8 md:py-8 w-full max-w-screen-2xl animate-pulse"
        style={{ background: bg }}
      >
        <div className="h-7 w-32 rounded mb-6" style={{ background: isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.06)' }} />
        <div className="h-40 rounded-[8px]" style={{ background: isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.04)' }} />
      </div>
    )
  }

  if (!session) return null

  const userName = session.user?.name ?? session.user?.email ?? 'Commercial Acoustics'
  const userEmail = session.user?.email ?? ''

  return (
    <div className="px-4 py-6 md:px-8 md:py-8 w-full max-w-2xl">
      {/* Header */}
      <div className="mb-7">
        <h1
          className="text-[22px] font-semibold tracking-tight leading-tight"
          style={{ color: textPrimary }}
        >
          Settings
        </h1>
        <p className="text-[13px] mt-1" style={{ color: textMuted }}>
          Manage your account and preferences
        </p>
      </div>

      {/* Account section */}
      <div
        className="rounded-[8px] mb-5"
        style={{ background: cardBg, border: `1px solid ${border}` }}
      >
        <div
          className="px-5 py-3.5"
          style={{ borderBottom: `1px solid ${innerBorder}` }}
        >
          <h2 className="text-[13px] font-semibold" style={{ color: textPrimary }}>
            Account
          </h2>
        </div>
        <div className="px-5 py-5 space-y-4">
          {/* Avatar + name row */}
          <div className="flex items-center gap-4">
            <div
              className="w-11 h-11 rounded-full flex items-center justify-center flex-shrink-0 text-[14px] font-bold"
              style={{
                background: 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
                color: '#080b10',
              }}
            >
              {userName
                .trim()
                .split(/\s+/)
                .filter(Boolean)
                .slice(0, 2)
                .map((w: string) => w[0])
                .join('')
                .toUpperCase() || 'CA'}
            </div>
            <div>
              <p className="text-[14px] font-semibold" style={{ color: textPrimary }}>
                {userName}
              </p>
              {userEmail && (
                <p className="text-[12px] mt-0.5" style={{ color: textSecondary }}>
                  {userEmail}
                </p>
              )}
            </div>
          </div>

          {/* Fields */}
          <div
            className="grid grid-cols-[120px_1fr] gap-x-4 gap-y-3 pt-2"
            style={{ borderTop: `1px solid ${innerBorder}` }}
          >
            <span className="text-[12px] font-medium pt-0.5" style={{ color: textMuted }}>Name</span>
            <span className="text-[13px]" style={{ color: textPrimary }}>{userName}</span>

            <span className="text-[12px] font-medium pt-0.5" style={{ color: textMuted }}>Email</span>
            <span className="text-[13px]" style={{ color: textPrimary }}>{userEmail || '—'}</span>

            <span className="text-[12px] font-medium pt-0.5" style={{ color: textMuted }}>Role</span>
            <span>
              {userRole === 'admin' ? (
                <span
                  className="inline-flex items-center px-2 py-0.5 rounded-[4px] text-[11px] font-semibold"
                  style={{
                    background: isLight ? 'rgba(61,112,16,0.12)' : 'rgba(161,214,124,0.12)',
                    border: `1px solid ${isLight ? 'rgba(61,112,16,0.25)' : 'rgba(161,214,124,0.22)'}`,
                    color: isLight ? '#3d7010' : '#a1d67c',
                  }}
                >
                  Admin
                </span>
              ) : (
                <span
                  className="inline-flex items-center px-2 py-0.5 rounded-[4px] text-[11px] font-semibold"
                  style={{
                    background: isLight ? 'rgba(74,94,122,0.10)' : 'rgba(107,130,160,0.12)',
                    border: `1px solid ${isLight ? 'rgba(74,94,122,0.20)' : 'rgba(107,130,160,0.20)'}`,
                    color: isLight ? '#4a5e7a' : '#6b82a0',
                  }}
                >
                  User
                </span>
              )}
            </span>
          </div>
        </div>
      </div>

      {/* Appearance section */}
      <div
        className="rounded-[8px] mb-5"
        style={{ background: cardBg, border: `1px solid ${border}` }}
      >
        <div
          className="px-5 py-3.5"
          style={{ borderBottom: `1px solid ${innerBorder}` }}
        >
          <h2 className="text-[13px] font-semibold" style={{ color: textPrimary }}>
            Appearance
          </h2>
        </div>
        <div className="px-5 py-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[13px] font-medium" style={{ color: textPrimary }}>
                Theme
              </p>
              <p className="text-[12px] mt-0.5" style={{ color: textSecondary }}>
                {isLight ? 'Light mode is active' : 'Dark mode is active'}
              </p>
            </div>
            <button
              onClick={toggle}
              aria-label="Toggle theme"
              style={{
                position: 'relative',
                flexShrink: 0,
                width: 44,
                height: 24,
                borderRadius: 9999,
                background: isLight ? '#a1d67c' : 'rgba(255,255,255,0.12)',
                border: 'none',
                cursor: 'pointer',
                padding: 0,
                transition: 'background 200ms',
              }}
            >
              <span
                style={{
                  position: 'absolute',
                  top: 3,
                  left: 3,
                  width: 18,
                  height: 18,
                  borderRadius: '50%',
                  background: isLight ? '#080b10' : '#d8e4f5',
                  transition: 'transform 200ms',
                  transform: isLight ? 'translateX(20px)' : 'translateX(0)',
                  display: 'block',
                }}
              />
            </button>
          </div>
        </div>
      </div>

      {/* Admin panel link — only for admins */}
      {userRole === 'admin' && (
        <div
          className="rounded-[8px] mb-5"
          style={{ background: cardBg, border: `1px solid ${border}` }}
        >
          <div
            className="px-5 py-3.5"
            style={{ borderBottom: `1px solid ${innerBorder}` }}
          >
            <h2 className="text-[13px] font-semibold" style={{ color: textPrimary }}>
              Administration
            </h2>
          </div>
          <div className="px-5 py-5">
            <p className="text-[13px] mb-4" style={{ color: textSecondary }}>
              You have admin access. Manage users and system settings from the admin panel.
            </p>
            <Link
              href="/admin/users"
              className="inline-flex items-center gap-2 px-4 py-2 text-[13px] font-semibold rounded-[6px] transition-all duration-100 hover:scale-[1.01]"
              style={{
                background: 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
                color: '#080b10',
              }}
            >
              <svg className="w-[14px] h-[14px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"
                  strokeWidth="1.75"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              Open Admin Panel
            </Link>
          </div>
        </div>
      )}

      {/* Danger zone */}
      <div
        className="rounded-[8px]"
        style={{
          background: cardBg,
          border: `1px solid ${isLight ? 'rgba(239,68,68,0.15)' : 'rgba(239,68,68,0.12)'}`,
        }}
      >
        <div
          className="px-5 py-3.5"
          style={{ borderBottom: `1px solid ${isLight ? 'rgba(239,68,68,0.12)' : 'rgba(239,68,68,0.10)'}` }}
        >
          <h2 className="text-[13px] font-semibold" style={{ color: '#ef4444' }}>
            Danger Zone
          </h2>
        </div>
        <div className="px-5 py-5 space-y-4">
          <p className="text-[13px]" style={{ color: textSecondary }}>
            To change your email or password, contact your administrator.
          </p>
          <button
            onClick={() => signOut({ callbackUrl: '/login' })}
            className="inline-flex items-center gap-2 px-4 py-2 text-[13px] font-semibold rounded-[6px] transition-all duration-100"
            style={{
              background: 'rgba(239,68,68,0.1)',
              border: '1px solid rgba(239,68,68,0.25)',
              color: '#ef4444',
              cursor: 'pointer',
            }}
            onMouseEnter={(e) =>
              ((e.currentTarget as HTMLButtonElement).style.background = 'rgba(239,68,68,0.2)')
            }
            onMouseLeave={(e) =>
              ((e.currentTarget as HTMLButtonElement).style.background = 'rgba(239,68,68,0.1)')
            }
          >
            <svg className="w-[14px] h-[14px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
              <polyline points="16 17 21 12 16 7" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
              <line x1="21" y1="12" x2="9" y2="12" strokeWidth="1.75" strokeLinecap="round" />
            </svg>
            Sign Out
          </button>
        </div>
      </div>
    </div>
  )
}
