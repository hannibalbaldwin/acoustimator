'use client'

import { useState, useEffect } from 'react'
import { useSession, signOut } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { useTheme } from '@/components/ThemeProvider'
import { updateAdminUser } from '@/lib/api'

// ── Theme Toggle Pill (matches Sidebar pattern exactly) ───────────────────────

function ThemeToggle({ isLight, onToggle }: { isLight: boolean; onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
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
        overflow: 'hidden',
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
  )
}

// ── Role Badge ────────────────────────────────────────────────────────────────

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
      {isAdmin ? 'Admin' : 'User'}
    </span>
  )
}

// ── Reusable field label wrapper ──────────────────────────────────────────────

function Field({
  label,
  children,
  textMuted,
}: {
  label: string
  children: React.ReactNode
  textMuted: string
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label
        className="text-[11px] font-semibold uppercase tracking-[0.08em]"
        style={{ color: textMuted }}
      >
        {label}
      </label>
      {children}
    </div>
  )
}

// ── Text / password input ─────────────────────────────────────────────────────

function TextInput({
  value,
  onChange,
  placeholder,
  disabled,
  type = 'text',
  inputBg,
  inputBorder,
  textPrimary,
  textMuted,
  isLight,
}: {
  value: string
  onChange?: (v: string) => void
  placeholder?: string
  disabled?: boolean
  type?: string
  inputBg: string
  inputBorder: string
  textPrimary: string
  textMuted: string
  isLight: boolean
}) {
  return (
    <input
      type={type}
      value={value}
      disabled={disabled}
      onChange={onChange ? (e) => onChange(e.target.value) : undefined}
      placeholder={placeholder}
      className="rounded-[6px] px-3 py-2 text-[13px] transition-all"
      style={{
        background: disabled
          ? isLight ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.02)'
          : inputBg,
        border: `1px solid ${inputBorder}`,
        color: disabled ? textMuted : textPrimary,
        outline: 'none',
        cursor: disabled ? 'not-allowed' : 'text',
      }}
      onFocus={
        !disabled
          ? (e) => (e.currentTarget.style.borderColor = isLight ? '#3d7010' : '#a1d67c')
          : undefined
      }
      onBlur={
        !disabled
          ? (e) => (e.currentTarget.style.borderColor = inputBorder)
          : undefined
      }
    />
  )
}

// ── Card shell ────────────────────────────────────────────────────────────────

function SectionCard({
  title,
  description,
  cardBg,
  border,
  innerBorder,
  textPrimary,
  textSecondary,
  children,
}: {
  title: string
  description?: string
  cardBg: string
  border: string
  innerBorder: string
  textPrimary: string
  textSecondary: string
  children: React.ReactNode
}) {
  return (
    <div
      className="rounded-[8px] mb-5"
      style={{ background: cardBg, border: `1px solid ${border}` }}
    >
      <div
        className="px-5 py-3.5"
        style={{ borderBottom: `1px solid ${innerBorder}` }}
      >
        <h2 className="text-[13px] font-semibold" style={{ color: textPrimary }}>
          {title}
        </h2>
        {description && (
          <p className="text-[12px] mt-0.5" style={{ color: textSecondary }}>
            {description}
          </p>
        )}
      </div>
      {children}
    </div>
  )
}

// ── Gradient CTA button ───────────────────────────────────────────────────────

function SaveButton({
  submitting,
  disabled,
  label,
  loadingLabel,
  type = 'button',
  onClick,
}: {
  submitting: boolean
  disabled?: boolean
  label: string
  loadingLabel: string
  type?: 'button' | 'submit'
  onClick?: () => void
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={submitting || disabled}
      className="inline-flex items-center gap-2 px-4 py-2 text-[13px] font-semibold rounded-[6px] transition-all duration-100 hover:scale-[1.01] disabled:opacity-50 disabled:cursor-not-allowed"
      style={{
        background: 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
        color: '#080b10',
      }}
    >
      {submitting ? (
        <>
          <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
          </svg>
          {loadingLabel}
        </>
      ) : (
        <>
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path d="M5 13l4 4L19 7" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          {label}
        </>
      )}
    </button>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const { data: session, status, update: updateSession } = useSession()
  const router = useRouter()
  const { theme, toggle } = useTheme()
  const isLight = theme === 'light'

  const userId = (session?.user as { id?: string } | null | undefined)?.id
  const userRole = (session?.user as { role?: string } | null | undefined)?.role
  const userEmail = session?.user?.email ?? ''
  const sessionName = session?.user?.name ?? ''

  // ── 1. Profile ─────────────────────────────────────────────────────────────
  const [displayName, setDisplayName] = useState(sessionName)
  const [profileSaving, setProfileSaving] = useState(false)
  const [profileError, setProfileError] = useState<string | null>(null)
  const [profileSuccess, setProfileSuccess] = useState(false)
  const nameChanged = displayName.trim() !== sessionName.trim()

  // ── 2. Security ────────────────────────────────────────────────────────────
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordSaving, setPasswordSaving] = useState(false)
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [passwordSuccess, setPasswordSuccess] = useState(false)

  // ── 3. Application ─────────────────────────────────────────────────────────
  const DEFAULT_VIEW_KEY = 'acoustimator:default_view'
  const [defaultView, setDefaultView] = useState<'Table' | 'Board'>('Table')

  // ── 4. API Access ──────────────────────────────────────────────────────────
  const [copied, setCopied] = useState(false)
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? ''

  // Hydrate localStorage default view on client
  useEffect(() => {
    const stored = localStorage.getItem(DEFAULT_VIEW_KEY)
    if (stored === 'Table' || stored === 'Board') setDefaultView(stored)
  }, [])

  // Sync display name when session loads
  useEffect(() => {
    if (sessionName) setDisplayName(sessionName)
  }, [sessionName])

  useEffect(() => {
    if (status === 'unauthenticated') router.push('/login')
  }, [status, router])

  // ── Color palette ───────────────────────────────────────────────────────────
  const bg = isLight ? '#f0f4f8' : '#0e1219'
  const cardBg = isLight ? '#ffffff' : '#131822'
  const border = isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.07)'
  const innerBorder = isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.06)'
  const textPrimary = isLight ? '#1a2335' : '#d8e4f5'
  const textMuted = isLight ? '#7890aa' : '#3a4f6a'
  const textSecondary = isLight ? '#4a5e7a' : '#6b82a0'
  const inputBg = isLight ? '#f8fafc' : 'rgba(255,255,255,0.04)'
  const inputBorder = isLight ? 'rgba(0,0,0,0.12)' : 'rgba(255,255,255,0.10)'

  // Shared prop bundles
  const inputProps = { inputBg, inputBorder, textPrimary, textMuted, isLight }
  const cardProps = { cardBg, border, innerBorder, textPrimary, textSecondary }

  // ── Handlers ────────────────────────────────────────────────────────────────

  async function handleProfileSave() {
    if (!userId || !nameChanged) return
    setProfileSaving(true)
    setProfileError(null)
    try {
      await updateAdminUser(userId, { name: displayName.trim() })
      await updateSession({ name: displayName.trim() })
      setProfileSuccess(true)
      setTimeout(() => setProfileSuccess(false), 3000)
    } catch (err: unknown) {
      setProfileError(err instanceof Error ? err.message : 'Failed to save profile')
    } finally {
      setProfileSaving(false)
    }
  }

  async function handlePasswordChange(e: React.FormEvent) {
    e.preventDefault()
    setPasswordError(null)

    if (!currentPassword) {
      setPasswordError('Current password is required.')
      return
    }
    if (newPassword.length < 8) {
      setPasswordError('New password must be at least 8 characters.')
      return
    }
    if (newPassword !== confirmPassword) {
      setPasswordError('New password and confirmation do not match.')
      return
    }

    setPasswordSaving(true)
    try {
      if (!userId) throw new Error('User ID not available — please sign out and back in.')
      await updateAdminUser(userId, { password: newPassword })
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setPasswordSuccess(true)
      setTimeout(() => setPasswordSuccess(false), 4000)
    } catch (err: unknown) {
      setPasswordError(err instanceof Error ? err.message : 'Failed to update password')
    } finally {
      setPasswordSaving(false)
    }
  }

  function handleDefaultViewChange(view: 'Table' | 'Board') {
    setDefaultView(view)
    localStorage.setItem(DEFAULT_VIEW_KEY, view)
  }

  async function handleCopyApiUrl() {
    try {
      await navigator.clipboard.writeText(apiBaseUrl || window.location.origin)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard API unavailable — silent fail
    }
  }

  // ── Loading skeleton ────────────────────────────────────────────────────────

  if (status === 'loading') {
    return (
      <div
        className="px-4 py-6 md:px-8 md:py-8 w-full max-w-2xl animate-pulse"
        style={{ background: bg }}
      >
        <div
          className="h-7 w-32 rounded mb-6"
          style={{ background: isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.06)' }}
        />
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-40 rounded-[8px] mb-5"
            style={{ background: isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.04)' }}
          />
        ))}
      </div>
    )
  }

  if (!session) return null

  const avatarInitials =
    (displayName || userEmail || 'CA')
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((w: string) => w[0])
      .join('')
      .toUpperCase() || 'CA'

  return (
    <div className="px-4 py-6 md:px-8 md:py-8 w-full max-w-2xl">
      {/* Page header */}
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

      {/* ── 1. Profile ─────────────────────────────────────────────────────── */}
      <SectionCard title="Profile" description="Update your display name" {...cardProps}>
        <div className="px-5 py-5">
          {/* Avatar row */}
          <div className="flex items-center gap-4 mb-5">
            <div
              className="w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0 text-[14px] font-bold"
              style={{
                background: 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
                color: '#080b10',
              }}
            >
              {avatarInitials}
            </div>
            <div>
              <p
                className="text-[14px] font-semibold leading-tight"
                style={{ color: textPrimary }}
              >
                {displayName || userEmail || 'Commercial Acoustics'}
              </p>
              <p className="text-[12px] mt-0.5" style={{ color: textSecondary }}>
                {userEmail}
              </p>
            </div>
          </div>

          {/* Fields grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
            <Field label="Display Name" textMuted={textMuted}>
              <TextInput
                value={displayName}
                onChange={setDisplayName}
                placeholder="Your name"
                {...inputProps}
              />
            </Field>

            <Field label="Email" textMuted={textMuted}>
              <div className="relative">
                <TextInput value={userEmail} disabled placeholder="—" {...inputProps} />
                <span
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] font-semibold uppercase tracking-[0.07em]"
                  style={{ color: textMuted }}
                >
                  read-only
                </span>
              </div>
            </Field>

            <Field label="Role" textMuted={textMuted}>
              <div className="flex items-center" style={{ height: 36 }}>
                <RoleBadge role={userRole ?? 'user'} isLight={isLight} />
              </div>
            </Field>
          </div>

          {profileError && (
            <p className="text-[12px] mb-3" style={{ color: '#ef4444' }}>
              {profileError}
            </p>
          )}
          {profileSuccess && (
            <p className="text-[12px] mb-3" style={{ color: isLight ? '#3d7010' : '#a1d67c' }}>
              Profile saved successfully.
            </p>
          )}

          {nameChanged && (
            <SaveButton
              label="Save Changes"
              loadingLabel="Saving…"
              submitting={profileSaving}
              onClick={handleProfileSave}
            />
          )}
        </div>
      </SectionCard>

      {/* ── 2. Security ────────────────────────────────────────────────────── */}
      <SectionCard title="Security" description="Change your password" {...cardProps}>
        <form onSubmit={handlePasswordChange} className="px-5 py-5">
          <div className="grid grid-cols-1 gap-4 mb-4" style={{ maxWidth: 340 }}>
            <Field label="Current Password" textMuted={textMuted}>
              <TextInput
                type="password"
                value={currentPassword}
                onChange={setCurrentPassword}
                placeholder="••••••••"
                {...inputProps}
              />
            </Field>

            <Field label="New Password" textMuted={textMuted}>
              <TextInput
                type="password"
                value={newPassword}
                onChange={setNewPassword}
                placeholder="Min. 8 characters"
                {...inputProps}
              />
            </Field>

            <Field label="Confirm New Password" textMuted={textMuted}>
              <TextInput
                type="password"
                value={confirmPassword}
                onChange={setConfirmPassword}
                placeholder="••••••••"
                {...inputProps}
              />
              {confirmPassword.length > 0 && (
                <p
                  className="text-[11px] mt-1"
                  style={{
                    color:
                      newPassword === confirmPassword
                        ? isLight ? '#3d7010' : '#a1d67c'
                        : '#ef4444',
                  }}
                >
                  {newPassword === confirmPassword ? 'Passwords match' : 'Passwords do not match'}
                </p>
              )}
            </Field>
          </div>

          {passwordError && (
            <p className="text-[12px] mb-3" style={{ color: '#ef4444' }}>
              {passwordError}
            </p>
          )}
          {passwordSuccess && (
            <p className="text-[12px] mb-3" style={{ color: isLight ? '#3d7010' : '#a1d67c' }}>
              Password updated successfully.
            </p>
          )}

          <SaveButton
            type="submit"
            label="Update Password"
            loadingLabel="Updating…"
            submitting={passwordSaving}
            disabled={!currentPassword || !newPassword || !confirmPassword}
          />
        </form>
      </SectionCard>

      {/* ── 3. Application ─────────────────────────────────────────────────── */}
      <SectionCard
        title="Application"
        description="Appearance and view preferences"
        {...cardProps}
      >
        <div className="px-5 py-5 space-y-5">
          {/* Theme toggle */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[13px] font-medium" style={{ color: textPrimary }}>
                Theme
              </p>
              <p className="text-[12px] mt-0.5" style={{ color: textSecondary }}>
                {isLight ? 'Light mode is active' : 'Dark mode is active'}
              </p>
            </div>
            <ThemeToggle isLight={isLight} onToggle={toggle} />
          </div>

          <div style={{ borderTop: `1px solid ${innerBorder}` }} />

          {/* Default estimates view */}
          <div>
            <p className="text-[13px] font-medium mb-0.5" style={{ color: textPrimary }}>
              Default Estimates View
            </p>
            <p className="text-[12px] mb-3" style={{ color: textSecondary }}>
              Choose how the Estimates list opens by default.
            </p>
            <div className="flex gap-2">
              {(['Table', 'Board'] as const).map((view) => {
                const active = defaultView === view
                return (
                  <button
                    key={view}
                    onClick={() => handleDefaultViewChange(view)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[6px] text-[12px] font-semibold transition-all duration-100"
                    style={{
                      background: active
                        ? isLight ? 'rgba(61,112,16,0.12)' : 'rgba(161,214,124,0.10)'
                        : 'transparent',
                      border: `1px solid ${
                        active
                          ? isLight ? 'rgba(61,112,16,0.30)' : 'rgba(161,214,124,0.25)'
                          : inputBorder
                      }`,
                      color: active
                        ? isLight ? '#3d7010' : '#a1d67c'
                        : textSecondary,
                      cursor: 'pointer',
                    }}
                  >
                    {view === 'Table' ? (
                      <svg
                        className="w-[13px] h-[13px]"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          d="M3 10h18M3 14h18M10 3v18M3 3h18v18H3z"
                          strokeWidth="1.75"
                          strokeLinecap="round"
                        />
                      </svg>
                    ) : (
                      <svg
                        className="w-[13px] h-[13px]"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <rect x="3" y="3" width="7" height="7" rx="1" strokeWidth="1.75" />
                        <rect x="14" y="3" width="7" height="7" rx="1" strokeWidth="1.75" />
                        <rect x="3" y="14" width="7" height="7" rx="1" strokeWidth="1.75" />
                        <rect x="14" y="14" width="7" height="7" rx="1" strokeWidth="1.75" />
                      </svg>
                    )}
                    {view}
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      </SectionCard>

      {/* ── 4. API Access (admin only) ─────────────────────────────────────── */}
      {userRole === 'admin' && (
        <SectionCard
          title="API Access"
          description="Base URL for direct API calls"
          {...cardProps}
        >
          <div className="px-5 py-5">
            <p className="text-[12px] mb-3" style={{ color: textSecondary }}>
              Authenticate requests using the{' '}
              <code
                className="px-1 py-0.5 rounded-[3px] text-[11px]"
                style={{
                  background: isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.07)',
                  color: textPrimary,
                  fontFamily: 'var(--font-jetbrains-mono), monospace',
                }}
              >
                X-API-Key
              </code>{' '}
              header.
            </p>

            {/* URL + copy row */}
            <div
              className="flex items-center gap-2 rounded-[6px] px-3 py-2.5 mb-4"
              style={{
                background: isLight ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.03)',
                border: `1px solid ${inputBorder}`,
              }}
            >
              <span
                className="flex-1 text-[12px] truncate select-all"
                style={{
                  color: textPrimary,
                  fontFamily: 'var(--font-jetbrains-mono), monospace',
                }}
              >
                {apiBaseUrl || '(not configured — set NEXT_PUBLIC_API_URL)'}
              </span>
              <button
                onClick={handleCopyApiUrl}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[5px] text-[11px] font-semibold flex-shrink-0 transition-all duration-150"
                style={{
                  background: copied
                    ? isLight ? 'rgba(61,112,16,0.12)' : 'rgba(161,214,124,0.10)'
                    : isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.07)',
                  border: `1px solid ${
                    copied
                      ? isLight ? 'rgba(61,112,16,0.25)' : 'rgba(161,214,124,0.22)'
                      : inputBorder
                  }`,
                  color: copied
                    ? isLight ? '#3d7010' : '#a1d67c'
                    : textSecondary,
                  cursor: 'pointer',
                }}
              >
                {copied ? (
                  <>
                    <svg
                      className="w-[12px] h-[12px]"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        d="M5 13l4 4L19 7"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    Copied
                  </>
                ) : (
                  <>
                    <svg
                      className="w-[12px] h-[12px]"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <rect x="9" y="9" width="13" height="13" rx="2" strokeWidth="1.75" />
                      <path
                        d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"
                        strokeWidth="1.75"
                        strokeLinecap="round"
                      />
                    </svg>
                    Copy
                  </>
                )}
              </button>
            </div>

            {/* curl example */}
            <pre
              className="rounded-[6px] px-3 py-3 text-[11px] leading-relaxed overflow-x-auto"
              style={{
                background: isLight ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.03)',
                border: `1px solid ${inputBorder}`,
                color: textSecondary,
                fontFamily: 'var(--font-jetbrains-mono), monospace',
              }}
            >
              <span style={{ color: textMuted }}>{`# Example request`}</span>
              {`\ncurl ${apiBaseUrl || '<API_URL>'}/api/estimates \\\n  -H "X-API-Key: $ACOUSTIMATOR_API_KEY"`}
            </pre>
          </div>
        </SectionCard>
      )}

      {/* ── Danger Zone ────────────────────────────────────────────────────── */}
      <div
        className="rounded-[8px]"
        style={{
          background: cardBg,
          border: `1px solid ${isLight ? 'rgba(239,68,68,0.15)' : 'rgba(239,68,68,0.12)'}`,
        }}
      >
        <div
          className="px-5 py-3.5"
          style={{
            borderBottom: `1px solid ${
              isLight ? 'rgba(239,68,68,0.12)' : 'rgba(239,68,68,0.10)'
            }`,
          }}
        >
          <h2 className="text-[13px] font-semibold" style={{ color: '#ef4444' }}>
            Danger Zone
          </h2>
          <p className="text-[12px] mt-0.5" style={{ color: textSecondary }}>
            Irreversible actions — proceed with care
          </p>
        </div>
        <div className="px-5 py-5">
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
            <svg
              className="w-[14px] h-[14px]"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"
                strokeWidth="1.75"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <polyline
                points="16 17 21 12 16 7"
                strokeWidth="1.75"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <line x1="21" y1="12" x2="9" y2="12" strokeWidth="1.75" strokeLinecap="round" />
            </svg>
            Sign Out
          </button>
        </div>
      </div>
    </div>
  )
}
