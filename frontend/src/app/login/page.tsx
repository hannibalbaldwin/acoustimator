'use client'

import { Suspense, useState } from 'react'
import { signIn } from 'next-auth/react'
import { useSearchParams } from 'next/navigation'
import { useTheme } from '@/components/ThemeProvider'

const ERROR_MESSAGES: Record<string, string> = {
  CredentialsSignin: 'Invalid email or password.',
  Default: 'Something went wrong. Please try again.',
}

// Inner component that reads searchParams — must be inside Suspense
function LoginForm() {
  const { theme } = useTheme()
  const isLight = theme === 'light'
  const searchParams = useSearchParams()
  const errorCode = searchParams.get('error') ?? undefined
  const serverError = errorCode ? (ERROR_MESSAGES[errorCode] ?? ERROR_MESSAGES.Default) : null

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [clientError, setClientError] = useState<string | null>(null)

  const error = clientError ?? serverError

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!email || !password) {
      setClientError('Email and password are required.')
      return
    }
    setClientError(null)
    setLoading(true)
    try {
      const result = await signIn('credentials', {
        email,
        password,
        redirect: false,
      })
      if (result?.error) {
        setClientError('Invalid email or password.')
      } else if (result?.ok) {
        window.location.href = '/dashboard'
      }
    } catch {
      setClientError('Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4"
      style={{ background: isLight ? '#f0f4f8' : '#0e1219' }}
    >
      <div
        className="w-full max-w-[380px] rounded-[12px] px-8 py-10"
        style={{
          background: isLight ? '#ffffff' : '#131822',
          border: `1px solid ${isLight ? 'rgba(0,0,0,0.09)' : 'rgba(255,255,255,0.08)'}`,
          boxShadow: isLight
            ? '0 4px 24px rgba(0,0,0,0.07)'
            : '0 4px 32px rgba(0,0,0,0.4)',
        }}
      >
        {/* Logo / Brand */}
        <div className="flex flex-col items-center mb-8">
          <div
            className="w-10 h-10 rounded-[10px] flex items-center justify-center mb-3"
            style={{
              background: 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
              boxShadow: '0 0 20px rgba(161,214,124,0.25)',
            }}
          >
            {/* Waveform icon */}
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path
                d="M2 10 Q4 4 6 10 Q8 16 10 10 Q12 4 14 10 Q16 16 18 10"
                stroke="#080b10"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                fill="none"
              />
            </svg>
          </div>
          <h1
            className="text-[20px] font-semibold tracking-tight"
            style={{ color: isLight ? '#1a2335' : '#d8e4f5' }}
          >
            Acoustimator
          </h1>
          <p
            className="text-[13px] mt-1"
            style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}
          >
            Sign in to your account
          </p>
        </div>

        {/* Error message */}
        {error && (
          <div
            className="rounded-[6px] px-4 py-3 mb-5 text-[13px]"
            style={{
              background: 'rgba(239,68,68,0.10)',
              border: '1px solid rgba(239,68,68,0.28)',
              color: '#ef4444',
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* Email */}
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="email"
              className="text-[12px] font-medium uppercase tracking-[0.07em]"
              style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}
            >
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              disabled={loading}
              className="rounded-[6px] px-3 py-2.5 text-[14px] outline-none transition-all"
              style={{
                background: isLight ? '#f5f7fa' : 'rgba(255,255,255,0.05)',
                border: `1px solid ${isLight ? 'rgba(0,0,0,0.12)' : 'rgba(255,255,255,0.10)'}`,
                color: isLight ? '#1a2335' : '#d8e4f5',
              }}
              onFocus={(e) => {
                e.currentTarget.style.border = `1px solid ${isLight ? 'rgba(61,112,16,0.6)' : 'rgba(161,214,124,0.5)'}`
                e.currentTarget.style.boxShadow = `0 0 0 3px ${isLight ? 'rgba(61,112,16,0.10)' : 'rgba(161,214,124,0.08)'}`
              }}
              onBlur={(e) => {
                e.currentTarget.style.border = `1px solid ${isLight ? 'rgba(0,0,0,0.12)' : 'rgba(255,255,255,0.10)'}`
                e.currentTarget.style.boxShadow = 'none'
              }}
            />
          </div>

          {/* Password */}
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="password"
              className="text-[12px] font-medium uppercase tracking-[0.07em]"
              style={{ color: isLight ? '#7890aa' : '#3a4f6a' }}
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              disabled={loading}
              className="rounded-[6px] px-3 py-2.5 text-[14px] outline-none transition-all"
              style={{
                background: isLight ? '#f5f7fa' : 'rgba(255,255,255,0.05)',
                border: `1px solid ${isLight ? 'rgba(0,0,0,0.12)' : 'rgba(255,255,255,0.10)'}`,
                color: isLight ? '#1a2335' : '#d8e4f5',
              }}
              onFocus={(e) => {
                e.currentTarget.style.border = `1px solid ${isLight ? 'rgba(61,112,16,0.6)' : 'rgba(161,214,124,0.5)'}`
                e.currentTarget.style.boxShadow = `0 0 0 3px ${isLight ? 'rgba(61,112,16,0.10)' : 'rgba(161,214,124,0.08)'}`
              }}
              onBlur={(e) => {
                e.currentTarget.style.border = `1px solid ${isLight ? 'rgba(0,0,0,0.12)' : 'rgba(255,255,255,0.10)'}`
                e.currentTarget.style.boxShadow = 'none'
              }}
            />
          </div>

          {/* Submit button */}
          <button
            type="submit"
            disabled={loading}
            className="mt-2 rounded-[6px] py-2.5 text-[14px] font-semibold transition-all duration-100"
            style={{
              background: loading
                ? isLight ? 'rgba(61,112,16,0.5)' : 'rgba(161,214,124,0.4)'
                : 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
              color: '#080b10',
              boxShadow: loading ? 'none' : '0 0 20px rgba(161,214,124,0.2)',
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Signing in\u2026' : 'Sign In'}
          </button>
        </form>

        <p
          className="text-center text-[12px] mt-6"
          style={{ color: isLight ? '#b0c4d8' : '#2a3a4e' }}
        >
          Commercial Acoustics &middot; Tampa, FL
        </p>
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  )
}
