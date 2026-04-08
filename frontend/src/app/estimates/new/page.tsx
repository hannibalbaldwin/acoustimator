'use client'

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { PlanUploadZone } from '@/components/upload/PlanUploadZone'
import { cn } from '@/lib/utils'
import { createEstimate } from '@/lib/api'
import type { ScopeType } from '@/lib/types'

type Step = 1 | 2 | 3

const SCOPE_TYPES: ScopeType[] = ['ACT', 'AWP', 'FW', 'SM', 'WW', 'Baffles', 'RPG', 'Other']

const PROCESSING_STEPS = [
  { id: 1, label: 'Files uploaded' },
  { id: 2, label: 'Extracting plan text' },
  { id: 3, label: 'Detecting scopes' },
  { id: 4, label: 'Running cost models' },
  { id: 5, label: 'Building estimate' },
]

// Scope badge colors matching ScopeTypeBadge
const SCOPE_COLORS: Record<ScopeType, { color: string; bg: string; border: string }> = {
  ACT:     { color: '#60a5fa', bg: 'rgba(96,165,250,0.10)',   border: 'rgba(96,165,250,0.20)'   },
  AWP:     { color: '#a1d67c', bg: 'rgba(161,214,124,0.10)', border: 'rgba(161,214,124,0.20)'   },
  AP:      { color: '#a1d67c', bg: 'rgba(161,214,124,0.10)', border: 'rgba(161,214,124,0.20)'   },
  FW:      { color: '#2dd4bf', bg: 'rgba(45,212,191,0.10)',   border: 'rgba(45,212,191,0.20)'   },
  SM:      { color: '#c084fc', bg: 'rgba(192,132,252,0.10)', border: 'rgba(192,132,252,0.20)'   },
  WW:      { color: '#fb923c', bg: 'rgba(251,146,60,0.10)',   border: 'rgba(251,146,60,0.20)'   },
  Baffles: { color: '#f472b6', bg: 'rgba(244,114,182,0.10)', border: 'rgba(244,114,182,0.20)'   },
  RPG:     { color: '#818cf8', bg: 'rgba(129,140,248,0.10)', border: 'rgba(129,140,248,0.20)'   },
  Other:   { color: '#6b7280', bg: 'rgba(107,114,128,0.10)', border: 'rgba(107,114,128,0.20)'   },
}

function StepIndicator({ current, step }: { current: Step; step: Step }) {
  const done = current > step
  const active = current === step
  const label = step === 1 ? 'Upload Plans' : step === 2 ? 'Project Details' : 'Processing'

  return (
    <div className="flex items-center gap-2.5">
      <div
        className="w-7 h-7 rounded-full flex items-center justify-center text-[12px] font-semibold flex-shrink-0 transition-all"
        style={
          done
            ? { background: 'rgba(161,214,124,0.15)', border: '2px solid #a1d67c', color: '#a1d67c' }
            : active
            ? { background: 'rgba(161,214,124,0.15)', border: '2px solid #a1d67c', color: '#a1d67c' }
            : { background: 'transparent', border: '2px solid rgba(255,255,255,0.12)', color: '#3a4f6a' }
        }
      >
        {done ? (
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path d="M5 13l4 4L19 7" strokeWidth="2.5" strokeLinecap="round" />
          </svg>
        ) : (
          step
        )}
      </div>
      <span
        className="text-[13px] font-medium"
        style={{ color: active || done ? '#d8e4f5' : '#3a4f6a' }}
      >
        {label}
      </span>
    </div>
  )
}

interface ProcessingStepRowProps {
  label: string
  status: 'done' | 'running' | 'pending'
}

function ProcessingStepRow({ label, status }: ProcessingStepRowProps) {
  return (
    <div
      className="flex items-center gap-3 py-3"
      style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}
    >
      <div className="w-5 h-5 flex items-center justify-center flex-shrink-0">
        {status === 'done' && (
          <div
            className="w-5 h-5 rounded-full flex items-center justify-center"
            style={{ background: 'rgba(161,214,124,0.12)', border: '1px solid rgba(161,214,124,0.25)' }}
          >
            <svg className="w-2.5 h-2.5" fill="none" stroke="#a1d67c" viewBox="0 0 24 24">
              <path d="M5 13l4 4L19 7" strokeWidth="2.5" strokeLinecap="round" />
            </svg>
          </div>
        )}
        {status === 'running' && (
          <div
            className="w-4 h-4 rounded-full border-2 animate-spin"
            style={{ borderColor: 'rgba(161,214,124,0.2)', borderTopColor: '#a1d67c' }}
          />
        )}
        {status === 'pending' && (
          <div
            className="w-3.5 h-3.5 rounded-full"
            style={{ border: '2px solid rgba(255,255,255,0.1)' }}
          />
        )}
      </div>
      <span
        className="text-[13px] font-medium"
        style={{
          color:
            status === 'done' ? '#a1d67c' : status === 'running' ? '#d8e4f5' : '#3a4f6a',
        }}
      >
        {label}
        {status === 'done' && (
          <span className="ml-1.5 text-[11px] opacity-60">✓</span>
        )}
      </span>
    </div>
  )
}

const inputClass =
  'w-full px-3 py-2 text-[13px] rounded-[6px] transition-all focus:outline-none'
const inputStyle: React.CSSProperties = {
  background: '#0e1219',
  border: '1px solid rgba(255,255,255,0.12)',
  color: '#d8e4f5',
}

export default function NewEstimatePage() {
  const [step, setStep] = useState<Step>(1)
  const [files, setFiles] = useState<File[]>([])
  const [projectName, setProjectName] = useState('')
  const [gcName, setGcName] = useState('')
  const [address, setAddress] = useState('')
  const [estSF, setEstSF] = useState('')
  const [scopeHints, setScopeHints] = useState<ScopeType[]>([])
  const [processingStep, setProcessingStep] = useState(0)
  const [complete, setComplete] = useState(false)
  const [estimateId, setEstimateId] = useState<string | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)
  const apiCalledRef = useRef(false)

  // Animate the first 4 steps while the API call is in-flight,
  // then hold at step 5 "Building estimate" until it resolves.
  useEffect(() => {
    if (step !== 3) return
    if (complete) return
    if (apiCalledRef.current) return

    apiCalledRef.current = true
    setProcessingStep(1)

    // Simulate the first 4 steps
    const interval = setInterval(() => {
      setProcessingStep((prev) => {
        if (prev >= 4) {
          clearInterval(interval)
          return 5 // Hold at "Building estimate" (running)
        }
        return prev + 1
      })
    }, 1800)

    // Fire the real API call
    const formData = new FormData()
    files.forEach((f) => formData.append('plans', f))
    formData.append('project_name', projectName)
    if (gcName.trim()) formData.append('gc_name', gcName)
    if (address.trim()) formData.append('address', address)
    scopeHints.forEach((h) => formData.append('scope_type_hints', h))

    createEstimate(formData)
      .then((estimate) => {
        clearInterval(interval)
        setProcessingStep(PROCESSING_STEPS.length + 1) // all done
        setEstimateId(estimate.id)
        setComplete(true)
      })
      .catch((err: unknown) => {
        clearInterval(interval)
        setApiError(err instanceof Error ? err.message : 'Estimation failed. Please try again.')
      })

    return () => clearInterval(interval)
  }, [step, complete, files, projectName, gcName, address, scopeHints])

  const toggleScopeHint = (t: ScopeType) => {
    setScopeHints((prev) =>
      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]
    )
  }

  const getProcessingStatus = (stepIndex: number): 'done' | 'running' | 'pending' => {
    if (processingStep > stepIndex) return 'done'
    if (processingStep === stepIndex) return 'running'
    return 'pending'
  }

  const handleTryAgain = () => {
    setStep(1)
    setProcessingStep(0)
    setComplete(false)
    setEstimateId(null)
    setApiError(null)
    apiCalledRef.current = false
  }

  const primaryBtn: React.CSSProperties = {
    background: 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
    color: '#080b10',
    boxShadow: '0 0 20px rgba(161,214,124,0.15)',
  }

  const disabledBtn: React.CSSProperties = {
    background: 'rgba(255,255,255,0.05)',
    color: '#3a4f6a',
    cursor: 'not-allowed',
  }

  return (
    <div className="px-8 py-8 max-w-3xl">
      {/* Header */}
      <div className="mb-7">
        <h1 className="text-[22px] font-semibold tracking-tight" style={{ color: '#d8e4f5' }}>
          New Estimate
        </h1>
        <p className="text-[13px] mt-1" style={{ color: '#3a4f6a' }}>
          Upload architectural plans to generate a cost estimate
        </p>
      </div>

      {/* Step indicators */}
      <div className="flex items-center gap-4 mb-8">
        <StepIndicator current={step} step={1} />
        <div className="flex-1 h-px" style={{ background: 'rgba(255,255,255,0.08)' }} />
        <StepIndicator current={step} step={2} />
        <div className="flex-1 h-px" style={{ background: 'rgba(255,255,255,0.08)' }} />
        <StepIndicator current={step} step={3} />
      </div>

      {/* ── Step 1: Upload ── */}
      {step === 1 && (
        <div className="space-y-5">
          <div>
            <h2 className="text-[14px] font-semibold mb-0.5" style={{ color: '#d8e4f5' }}>
              Upload PDF Plans
            </h2>
            <p className="text-[12px]" style={{ color: '#3a4f6a' }}>
              The AI will extract scope areas and room tags from the architectural plans.
            </p>
          </div>
          <PlanUploadZone onFilesChange={setFiles} />
          <div className="flex justify-end pt-1">
            <button
              onClick={() => setStep(2)}
              disabled={files.length === 0}
              className="px-5 py-2 rounded-[6px] text-[13px] font-semibold transition-all duration-100"
              style={files.length > 0 ? primaryBtn : disabledBtn}
            >
              Continue →
            </button>
          </div>
        </div>
      )}

      {/* ── Step 2: Project Details ── */}
      {step === 2 && (
        <div className="space-y-5">
          <div>
            <h2 className="text-[14px] font-semibold mb-0.5" style={{ color: '#d8e4f5' }}>
              Project Details
            </h2>
            <p className="text-[12px]" style={{ color: '#3a4f6a' }}>
              Fill in project metadata to improve estimate accuracy.
            </p>
          </div>

          <div
            className="rounded-[8px] p-5 space-y-5"
            style={{ background: '#131822', border: '1px solid rgba(255,255,255,0.08)' }}
          >
            {/* Project Name */}
            <div>
              <label
                className="block text-[10px] font-semibold uppercase tracking-[0.09em] mb-1.5"
                style={{ color: '#3a4f6a' }}
              >
                Project Name <span style={{ color: '#f05252' }}>*</span>
              </label>
              <input
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="e.g. Seven Pines Jax — AWP/ACT Renovation"
                className={inputClass}
                style={inputStyle}
              />
            </div>

            {/* GC + SF row */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label
                  className="block text-[10px] font-semibold uppercase tracking-[0.09em] mb-1.5"
                  style={{ color: '#3a4f6a' }}
                >
                  General Contractor
                </label>
                <input
                  type="text"
                  value={gcName}
                  onChange={(e) => setGcName(e.target.value)}
                  placeholder="e.g. DPR Construction"
                  className={inputClass}
                  style={inputStyle}
                />
              </div>
              <div>
                <label
                  className="block text-[10px] font-semibold uppercase tracking-[0.09em] mb-1.5"
                  style={{ color: '#3a4f6a' }}
                >
                  Estimated SF
                </label>
                <input
                  type="number"
                  value={estSF}
                  onChange={(e) => setEstSF(e.target.value)}
                  placeholder="e.g. 5000"
                  className={inputClass}
                  style={{
                    ...inputStyle,
                    fontFamily: 'var(--font-jetbrains-mono), monospace',
                  }}
                />
              </div>
            </div>

            {/* Address */}
            <div>
              <label
                className="block text-[10px] font-semibold uppercase tracking-[0.09em] mb-1.5"
                style={{ color: '#3a4f6a' }}
              >
                Address
              </label>
              <input
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder="e.g. 4000 Seven Pines Dr, Jacksonville, FL 32256"
                className={inputClass}
                style={inputStyle}
              />
            </div>

            {/* Scope hints */}
            <div>
              <label
                className="block text-[10px] font-semibold uppercase tracking-[0.09em] mb-2"
                style={{ color: '#3a4f6a' }}
              >
                Scope Type Hints
              </label>
              <div className="flex flex-wrap gap-2">
                {SCOPE_TYPES.map((t) => {
                  const c = SCOPE_COLORS[t] ?? SCOPE_COLORS.Other
                  const active = scopeHints.includes(t)
                  return (
                    <button
                      key={t}
                      onClick={() => toggleScopeHint(t)}
                      className="px-2.5 py-1 rounded-[4px] text-[11px] font-semibold font-mono tracking-wide transition-all"
                      style={
                        active
                          ? { color: c.color, background: c.bg, border: `1px solid ${c.border}` }
                          : {
                              color: '#3a4f6a',
                              background: 'transparent',
                              border: '1px solid rgba(255,255,255,0.1)',
                            }
                      }
                    >
                      {t}
                    </button>
                  )
                })}
              </div>
              <p className="text-[11px] mt-1.5" style={{ color: '#3a4f6a' }}>
                Optional — helps the AI focus on specific scope types
              </p>
            </div>
          </div>

          <div className="flex items-center justify-between pt-1">
            <button
              onClick={() => setStep(1)}
              className="text-[13px] font-medium transition-colors"
              style={{ color: '#3a4f6a' }}
              onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.color = '#6b82a0')}
              onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.color = '#3a4f6a')}
            >
              ← Back
            </button>
            <button
              onClick={() => setStep(3)}
              disabled={!projectName.trim()}
              className="px-5 py-2 rounded-[6px] text-[13px] font-semibold transition-all duration-100"
              style={projectName.trim() ? primaryBtn : disabledBtn}
            >
              Start Estimation →
            </button>
          </div>
        </div>
      )}

      {/* ── Step 3: Processing ── */}
      {step === 3 && (
        <div className="space-y-5">
          <div>
            <h2 className="text-[14px] font-semibold mb-0.5" style={{ color: '#d8e4f5' }}>
              Running Estimation
            </h2>
            <p className="text-[12px]" style={{ color: '#3a4f6a' }}>
              AI is reading plans and running cost models. This takes 30–60 seconds.
            </p>
          </div>

          <div
            className="rounded-[8px] p-5"
            style={{ background: '#131822', border: '1px solid rgba(255,255,255,0.08)' }}
          >
            <div>
              {PROCESSING_STEPS.map((s, idx) => (
                <ProcessingStepRow
                  key={s.id}
                  label={s.label}
                  status={getProcessingStatus(idx + 1)}
                />
              ))}
            </div>

            {apiError && (
              <div
                className="mt-5 pt-5"
                style={{ borderTop: '1px solid rgba(255,255,255,0.08)' }}
              >
                <p className="text-[13px] mb-3" style={{ color: '#f05252' }}>
                  {apiError}
                </p>
                <button
                  onClick={handleTryAgain}
                  className="px-4 py-2 rounded-[6px] text-[13px] font-semibold transition-all"
                  style={{
                    background: 'rgba(255,255,255,0.07)',
                    border: '1px solid rgba(255,255,255,0.12)',
                    color: '#d8e4f5',
                  }}
                >
                  ← Try again
                </button>
              </div>
            )}

            {complete && estimateId && (
              <div
                className="mt-5 pt-5"
                style={{ borderTop: '1px solid rgba(255,255,255,0.08)' }}
              >
                <div className="flex items-center gap-3 mb-4">
                  <div
                    className="w-8 h-8 rounded-full flex items-center justify-center"
                    style={{
                      background: 'rgba(161,214,124,0.12)',
                      border: '1px solid rgba(161,214,124,0.25)',
                    }}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="#a1d67c" viewBox="0 0 24 24">
                      <path d="M5 13l4 4L19 7" strokeWidth="2.5" strokeLinecap="round" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-[13px] font-semibold" style={{ color: '#d8e4f5' }}>
                      Estimate complete
                    </p>
                    <p className="text-[11px]" style={{ color: '#3a4f6a' }}>
                      Review your scopes and adjust as needed
                    </p>
                  </div>
                </div>
                <Link
                  href={`/estimates/${estimateId}`}
                  className="flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-[6px] text-[13px] font-semibold transition-all"
                  style={{
                    background: 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
                    color: '#080b10',
                    boxShadow: '0 0 20px rgba(161,214,124,0.2)',
                  }}
                >
                  View Estimate →
                </Link>
              </div>
            )}
          </div>

          {!complete && !apiError && (
            <p className="text-[11px] text-center" style={{ color: '#3a4f6a' }}>
              Do not close this tab. Estimation in progress...
            </p>
          )}
        </div>
      )}
    </div>
  )
}
