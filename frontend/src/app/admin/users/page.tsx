'use client'

import { useState, useEffect, useCallback } from 'react'
import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useTheme } from '@/components/ThemeProvider'
import { listAdminUsers, createAdminUser, deleteAdminUser, type AdminUser } from '@/lib/api'

// ── Role badge ────────────────────────────────────────────────────────────────

function RoleBadge({ role, isLight }: { role: string; isLight: boolean }) {
  const isAdmin = role === 'admin'
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-[4px] text-[11px] font-semibold"
      style={
        isAdmin
          ? {
              background: isLight ? 'rgba(61,112,16,0.12)' : 'rgba(161,214,124,0.12)',
              border: `1px solid ${isLight ? 'rgba(61,112,16,0.25)' : 'rgba(161,214,124,0.22)'}`,
              color: isLight ? '#3d7010' : '#a1d67c',
            }
          : {
              background: isLight ? 'rgba(74,94,122,0.10)' : 'rgba(107,130,160,0.12)',
              border: `1px solid ${isLight ? 'rgba(74,94,122,0.20)' : 'rgba(107,130,160,0.20)'}`,
              color: isLight ? '#4a5e7a' : '#6b82a0',
            }
      }
    >
      {role}
    </span>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function AdminUsersPage() {
  const { data: session, status } = useSession()
  const router = useRouter()
  const { theme } = useTheme()
  const isLight = theme === 'light'

  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)

  // Create form state
  const [formEmail, setFormEmail] = useState('')
  const [formName, setFormName] = useState('')
  const [formPassword, setFormPassword] = useState('')
  const [formRole, setFormRole] = useState<'user' | 'admin'>('user')
  const [formError, setFormError] = useState<string | null>(null)
  const [formSubmitting, setFormSubmitting] = useState(false)
  const [formSuccess, setFormSuccess] = useState(false)

  const userRole = (session?.user as { role?: string } | null | undefined)?.role

  // Redirect non-admins
  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/login')
    } else if (status === 'authenticated' && userRole !== 'admin') {
      router.push('/dashboard')
    }
  }, [status, userRole, router])

  const loadUsers = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await listAdminUsers()
      setUsers(data)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load users')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (status === 'authenticated' && userRole === 'admin') {
      loadUsers()
    }
  }, [status, userRole, loadUsers])

  async function handleDelete(userId: string) {
    setDeleting(userId)
    try {
      await deleteAdminUser(userId)
      setUsers((prev) => prev.filter((u) => u.id !== userId))
      setDeleteConfirm(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Delete failed')
    } finally {
      setDeleting(null)
    }
  }

  async function handleCreateUser(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)
    setFormSubmitting(true)
    try {
      const newUser = await createAdminUser({
        email: formEmail,
        name: formName || undefined,
        password: formPassword,
        role: formRole,
      })
      setUsers((prev) => [newUser, ...prev])
      setFormEmail('')
      setFormName('')
      setFormPassword('')
      setFormRole('user')
      setFormSuccess(true)
      setTimeout(() => setFormSuccess(false), 3000)
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Failed to create user')
    } finally {
      setFormSubmitting(false)
    }
  }

  // Colors
  const cardBg = isLight ? '#ffffff' : '#131822'
  const border = isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.07)'
  const innerBorder = isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.06)'
  const textPrimary = isLight ? '#1a2335' : '#d8e4f5'
  const textMuted = isLight ? '#7890aa' : '#3a4f6a'
  const textSecondary = isLight ? '#4a5e7a' : '#6b82a0'
  const inputBg = isLight ? '#f8fafc' : 'rgba(255,255,255,0.04)'
  const inputBorder = isLight ? 'rgba(0,0,0,0.12)' : 'rgba(255,255,255,0.10)'
  const rowHoverBg = isLight ? 'rgba(0,0,0,0.025)' : 'rgba(255,255,255,0.02)'
  const altRowBg = isLight ? 'rgba(0,0,0,0.015)' : 'rgba(255,255,255,0.015)'

  if (status === 'loading' || (status === 'authenticated' && userRole !== 'admin' && userRole !== undefined)) {
    return (
      <div className="px-4 py-6 md:px-8 md:py-8 w-full max-w-screen-2xl animate-pulse">
        <div className="h-7 w-48 rounded mb-6" style={{ background: isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.06)' }} />
        <div className="h-64 rounded-[8px]" style={{ background: isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.04)' }} />
      </div>
    )
  }

  return (
    <div className="px-4 py-6 md:px-8 md:py-8 w-full max-w-screen-xl">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 mb-5 text-[12px]" style={{ color: textMuted }}>
        <Link href="/dashboard" style={{ color: textSecondary }} className="hover:underline">Dashboard</Link>
        <span>/</span>
        <Link href="/settings" style={{ color: textSecondary }} className="hover:underline">Settings</Link>
        <span>/</span>
        <span style={{ color: textPrimary, fontWeight: 500 }}>User Management</span>
      </nav>

      {/* Header */}
      <div className="flex items-start justify-between mb-7">
        <div>
          <h1
            className="text-[22px] font-semibold tracking-tight leading-tight"
            style={{ color: textPrimary }}
          >
            User Management
          </h1>
          <p className="text-[13px] mt-1" style={{ color: textMuted }}>
            Create and manage user accounts
          </p>
        </div>
      </div>

      {error && (
        <div
          className="rounded-[6px] px-4 py-3 mb-5 text-[13px]"
          style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', color: '#ef4444' }}
        >
          {error}
        </div>
      )}

      {/* Create User form */}
      <div
        className="rounded-[8px] mb-6"
        style={{ background: cardBg, border: `1px solid ${border}` }}
      >
        <div
          className="px-5 py-3.5"
          style={{ borderBottom: `1px solid ${innerBorder}` }}
        >
          <h2 className="text-[13px] font-semibold" style={{ color: textPrimary }}>
            Create User
          </h2>
        </div>
        <form onSubmit={handleCreateUser} className="px-5 py-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
            {/* Email */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] font-semibold uppercase tracking-[0.08em]" style={{ color: textMuted }}>
                Email *
              </label>
              <input
                type="email"
                required
                value={formEmail}
                onChange={(e) => setFormEmail(e.target.value)}
                placeholder="user@example.com"
                className="rounded-[6px] px-3 py-2 text-[13px] transition-all"
                style={{
                  background: inputBg,
                  border: `1px solid ${inputBorder}`,
                  color: textPrimary,
                  outline: 'none',
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = isLight ? '#3d7010' : '#a1d67c')}
                onBlur={(e) => (e.currentTarget.style.borderColor = inputBorder)}
              />
            </div>

            {/* Name */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] font-semibold uppercase tracking-[0.08em]" style={{ color: textMuted }}>
                Name
              </label>
              <input
                type="text"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="John Smith"
                className="rounded-[6px] px-3 py-2 text-[13px] transition-all"
                style={{
                  background: inputBg,
                  border: `1px solid ${inputBorder}`,
                  color: textPrimary,
                  outline: 'none',
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = isLight ? '#3d7010' : '#a1d67c')}
                onBlur={(e) => (e.currentTarget.style.borderColor = inputBorder)}
              />
            </div>

            {/* Password */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] font-semibold uppercase tracking-[0.08em]" style={{ color: textMuted }}>
                Password *
              </label>
              <input
                type="password"
                required
                value={formPassword}
                onChange={(e) => setFormPassword(e.target.value)}
                placeholder="••••••••"
                className="rounded-[6px] px-3 py-2 text-[13px] transition-all"
                style={{
                  background: inputBg,
                  border: `1px solid ${inputBorder}`,
                  color: textPrimary,
                  outline: 'none',
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = isLight ? '#3d7010' : '#a1d67c')}
                onBlur={(e) => (e.currentTarget.style.borderColor = inputBorder)}
              />
            </div>

            {/* Role */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] font-semibold uppercase tracking-[0.08em]" style={{ color: textMuted }}>
                Role *
              </label>
              <select
                value={formRole}
                onChange={(e) => setFormRole(e.target.value as 'user' | 'admin')}
                className="rounded-[6px] px-3 py-2 text-[13px] transition-all"
                style={{
                  background: inputBg,
                  border: `1px solid ${inputBorder}`,
                  color: textPrimary,
                  outline: 'none',
                  cursor: 'pointer',
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = isLight ? '#3d7010' : '#a1d67c')}
                onBlur={(e) => (e.currentTarget.style.borderColor = inputBorder)}
              >
                <option value="user">User</option>
                <option value="admin">Admin</option>
              </select>
            </div>
          </div>

          {formError && (
            <p className="text-[12px] mb-3" style={{ color: '#ef4444' }}>
              {formError}
            </p>
          )}

          {formSuccess && (
            <p className="text-[12px] mb-3" style={{ color: isLight ? '#3d7010' : '#a1d67c' }}>
              User created successfully.
            </p>
          )}

          <button
            type="submit"
            disabled={formSubmitting}
            className="inline-flex items-center gap-2 px-4 py-2 text-[13px] font-semibold rounded-[6px] transition-all duration-100 hover:scale-[1.01] disabled:opacity-60 disabled:cursor-not-allowed"
            style={{
              background: 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
              color: '#080b10',
            }}
          >
            {formSubmitting ? (
              <>
                <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                </svg>
                Creating…
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path d="M12 5v14M5 12h14" strokeWidth="2.5" strokeLinecap="round" />
                </svg>
                Create User
              </>
            )}
          </button>
        </form>
      </div>

      {/* Users table */}
      <div
        className="rounded-[8px] overflow-hidden"
        style={{ background: cardBg, border: `1px solid ${border}` }}
      >
        <div
          className="flex items-center justify-between px-5 py-3.5"
          style={{ borderBottom: `1px solid ${innerBorder}` }}
        >
          <h2 className="text-[13px] font-semibold" style={{ color: textPrimary }}>
            Users
          </h2>
          <span className="text-[12px]" style={{ color: textMuted }}>
            {loading ? '…' : `${users.length} ${users.length === 1 ? 'user' : 'users'}`}
          </span>
        </div>

        {loading ? (
          <div className="px-5 py-8 animate-pulse space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-10 rounded" style={{ background: isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.04)' }} />
            ))}
          </div>
        ) : users.length === 0 ? (
          <div className="px-5 py-8">
            <p className="text-[13px]" style={{ color: textMuted }}>
              No users found.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr style={{ borderBottom: `1px solid ${innerBorder}` }}>
                  {['Name', 'Email', 'Role', 'Created', 'Actions'].map((col, i) => (
                    <th
                      key={i}
                      className="px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-[0.09em]"
                      style={{ color: textMuted }}
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {users.map((user, idx) => (
                  <tr
                    key={user.id}
                    style={{
                      background: idx % 2 === 1 ? altRowBg : 'transparent',
                      borderBottom: `1px solid ${innerBorder}`,
                    }}
                    onMouseEnter={(e) =>
                      ((e.currentTarget as HTMLTableRowElement).style.background = rowHoverBg)
                    }
                    onMouseLeave={(e) =>
                      ((e.currentTarget as HTMLTableRowElement).style.background =
                        idx % 2 === 1 ? altRowBg : 'transparent')
                    }
                  >
                    <td className="px-4 py-3" style={{ color: textPrimary, fontWeight: 500 }}>
                      {user.name ?? <span style={{ color: textMuted }}>—</span>}
                    </td>
                    <td className="px-4 py-3" style={{ color: textSecondary }}>
                      {user.email}
                    </td>
                    <td className="px-4 py-3">
                      <RoleBadge role={user.role} isLight={isLight} />
                    </td>
                    <td
                      className="px-4 py-3 tabular-nums text-[12px]"
                      style={{
                        color: textMuted,
                        fontFamily: 'var(--font-jetbrains-mono), monospace',
                      }}
                    >
                      {user.created_at.slice(0, 10)}
                    </td>
                    <td className="px-4 py-3">
                      {deleteConfirm === user.id ? (
                        <div className="flex items-center gap-2">
                          <span className="text-[12px]" style={{ color: textSecondary }}>
                            Confirm?
                          </span>
                          <button
                            onClick={() => handleDelete(user.id)}
                            disabled={deleting === user.id}
                            className="px-2 py-0.5 rounded-[4px] text-[11px] font-semibold transition-colors disabled:opacity-60"
                            style={{
                              background: 'rgba(239,68,68,0.15)',
                              border: '1px solid rgba(239,68,68,0.30)',
                              color: '#ef4444',
                              cursor: 'pointer',
                            }}
                          >
                            {deleting === user.id ? 'Deleting…' : 'Yes, delete'}
                          </button>
                          <button
                            onClick={() => setDeleteConfirm(null)}
                            className="px-2 py-0.5 rounded-[4px] text-[11px] font-semibold transition-colors"
                            style={{
                              background: 'transparent',
                              border: `1px solid ${inputBorder}`,
                              color: textSecondary,
                              cursor: 'pointer',
                            }}
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setDeleteConfirm(user.id)}
                          className="px-2.5 py-1 rounded-[4px] text-[11px] font-semibold transition-all"
                          style={{
                            background: 'rgba(239,68,68,0.08)',
                            border: '1px solid rgba(239,68,68,0.18)',
                            color: '#ef4444',
                            cursor: 'pointer',
                          }}
                          onMouseEnter={(e) =>
                            ((e.currentTarget as HTMLButtonElement).style.background =
                              'rgba(239,68,68,0.18)')
                          }
                          onMouseLeave={(e) =>
                            ((e.currentTarget as HTMLButtonElement).style.background =
                              'rgba(239,68,68,0.08)')
                          }
                        >
                          Delete
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
