'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { PlanUploadZone } from '@/components/upload/PlanUploadZone'
import { cn } from '@/lib/utils'
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

function StepIndicator({ current, step }: { current: Step; step: Step }) {
  const done = current > step
  const active = current === step

  return (
    <div className="flex items-center gap-3">
      <div
        className={cn(
          'w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold border-2 transition-all',
          done
            ? 'bg-green-600 border-green-600 text-white'
            : active
            ? 'bg-blue-600 border-blue-600 text-white'
            : 'bg-white border-zinc-300 text-zinc-400'
        )}
      >
        {done ? (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path d="M5 13l4 4L19 7" strokeWidth="2.5" strokeLinecap="round" />
          </svg>
        ) : (
          step
        )}
      </div>
      <span
        className={cn(
          'text-sm font-medium',
          done ? 'text-green-700' : active ? 'text-zinc-900' : 'text-zinc-400'
        )}
      >
        {step === 1 ? 'Upload Plans' : step === 2 ? 'Project Details' : 'Processing'}
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
    <div className="flex items-center gap-3 py-2.5">
      <div className="w-5 h-5 flex items-center justify-center flex-shrink-0">
        {status === 'done' && (
          <div className="w-5 h-5 rounded-full bg-green-100 flex items-center justify-center">
            <svg className="w-3 h-3 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M5 13l4 4L19 7" strokeWidth="2.5" strokeLinecap="round" />
            </svg>
          </div>
        )}
        {status === 'running' && (
          <div className="w-4 h-4 rounded-full border-2 border-blue-600 border-t-transparent animate-spin" />
        )}
        {status === 'pending' && (
          <div className="w-3.5 h-3.5 rounded-full border-2 border-zinc-300" />
        )}
      </div>
      <span
        className={cn(
          'text-sm',
          status === 'done' ? 'text-green-700 font-medium' : status === 'running' ? 'text-blue-700 font-medium' : 'text-zinc-400'
        )}
      >
        {label}
        {status === 'done' && ' ✓'}
      </span>
    </div>
  )
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

  // Simulate processing progression
  useEffect(() => {
    if (step !== 3) return
    if (complete) return

    const interval = setInterval(() => {
      setProcessingStep((prev) => {
        if (prev >= PROCESSING_STEPS.length) {
          clearInterval(interval)
          setComplete(true)
          return prev
        }
        return prev + 1
      })
    }, 1800)

    return () => clearInterval(interval)
  }, [step, complete])

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

  return (
    <div className="px-8 py-8 max-w-3xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-zinc-900">New Estimate</h1>
        <p className="text-sm text-zinc-500 mt-0.5">Upload architectural plans to generate a cost estimate</p>
      </div>

      {/* Step indicators */}
      <div className="flex items-center gap-6 mb-8">
        <StepIndicator current={step} step={1} />
        <div className="flex-1 h-px bg-zinc-200" />
        <StepIndicator current={step} step={2} />
        <div className="flex-1 h-px bg-zinc-200" />
        <StepIndicator current={step} step={3} />
      </div>

      {/* Step 1: Upload */}
      {step === 1 && (
        <div className="space-y-6">
          <div>
            <h2 className="text-base font-semibold text-zinc-800 mb-1">Upload PDF Plans</h2>
            <p className="text-sm text-zinc-500">
              Upload the architectural plans. The AI will extract scope areas and room tags.
            </p>
          </div>
          <PlanUploadZone onFilesChange={setFiles} />
          <div className="flex justify-end pt-2">
            <button
              onClick={() => setStep(2)}
              disabled={files.length === 0}
              className={cn(
                'px-5 py-2 rounded-lg text-sm font-medium transition-colors',
                files.length > 0
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-zinc-100 text-zinc-400 cursor-not-allowed'
              )}
            >
              Continue →
            </button>
          </div>
        </div>
      )}

      {/* Step 2: Project Details */}
      {step === 2 && (
        <div className="space-y-6">
          <div>
            <h2 className="text-base font-semibold text-zinc-800 mb-1">Project Details</h2>
            <p className="text-sm text-zinc-500">
              Fill in project metadata to improve estimate accuracy.
            </p>
          </div>

          <div className="bg-white border border-zinc-200 rounded-lg p-6 space-y-5">
            <div>
              <label className="block text-xs font-semibold text-zinc-700 mb-1.5 uppercase tracking-wide">
                Project Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="e.g. Seven Pines Jax — AWP/ACT Renovation"
                className="w-full border border-zinc-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1.5 uppercase tracking-wide">
                  General Contractor
                </label>
                <input
                  type="text"
                  value={gcName}
                  onChange={(e) => setGcName(e.target.value)}
                  placeholder="e.g. DPR Construction"
                  className="w-full border border-zinc-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1.5 uppercase tracking-wide">
                  Estimated SF
                </label>
                <input
                  type="number"
                  value={estSF}
                  onChange={(e) => setEstSF(e.target.value)}
                  placeholder="e.g. 5000"
                  className="w-full border border-zinc-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-700 mb-1.5 uppercase tracking-wide">
                Address
              </label>
              <input
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder="e.g. 4000 Seven Pines Dr, Jacksonville, FL 32256"
                className="w-full border border-zinc-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-700 mb-2 uppercase tracking-wide">
                Scope Type Hints
              </label>
              <div className="flex flex-wrap gap-2">
                {SCOPE_TYPES.map((t) => (
                  <button
                    key={t}
                    onClick={() => toggleScopeHint(t)}
                    className={cn(
                      'px-3 py-1.5 rounded text-xs font-semibold border transition-all font-mono',
                      scopeHints.includes(t)
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-white text-zinc-600 border-zinc-300 hover:border-zinc-400'
                    )}
                  >
                    {t}
                  </button>
                ))}
              </div>
              <p className="text-xs text-zinc-400 mt-1.5">
                Optional — helps the AI focus on specific scope types
              </p>
            </div>
          </div>

          <div className="flex items-center justify-between pt-2">
            <button
              onClick={() => setStep(1)}
              className="px-4 py-2 text-sm font-medium text-zinc-600 hover:text-zinc-900 transition-colors"
            >
              ← Back
            </button>
            <button
              onClick={() => setStep(3)}
              disabled={!projectName.trim()}
              className={cn(
                'px-5 py-2 rounded-lg text-sm font-medium transition-colors',
                projectName.trim()
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-zinc-100 text-zinc-400 cursor-not-allowed'
              )}
            >
              Start Estimation →
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Processing */}
      {step === 3 && (
        <div className="space-y-6">
          <div>
            <h2 className="text-base font-semibold text-zinc-800 mb-1">Running Estimation</h2>
            <p className="text-sm text-zinc-500">
              AI is reading plans and running cost models. This takes 30–60 seconds.
            </p>
          </div>

          <div className="bg-white border border-zinc-200 rounded-lg p-6">
            <div className="space-y-0 divide-y divide-zinc-100">
              {PROCESSING_STEPS.map((s, idx) => (
                <ProcessingStepRow
                  key={s.id}
                  label={s.label}
                  status={getProcessingStatus(idx + 1)}
                />
              ))}
            </div>

            {complete && (
              <div className="mt-6 pt-5 border-t border-zinc-200">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
                    <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path d="M5 13l4 4L19 7" strokeWidth="2.5" strokeLinecap="round" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-zinc-800">Estimate complete</p>
                    <p className="text-xs text-zinc-500">3 scopes detected · High confidence</p>
                  </div>
                </div>
                <Link
                  href="/estimates/est-001"
                  className="flex items-center justify-center gap-2 w-full px-4 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
                >
                  View Estimate →
                </Link>
              </div>
            )}
          </div>

          {!complete && (
            <p className="text-xs text-zinc-400 text-center">
              Do not close this tab. Estimation in progress...
            </p>
          )}
        </div>
      )}
    </div>
  )
}
