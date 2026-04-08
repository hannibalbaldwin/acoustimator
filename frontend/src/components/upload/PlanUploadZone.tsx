'use client'

import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { cn } from '@/lib/utils'

interface PlanUploadZoneProps {
  onFilesChange: (files: File[]) => void
}

export function PlanUploadZone({ onFilesChange }: PlanUploadZoneProps) {
  const [files, setFiles] = useState<File[]>([])

  const onDrop = useCallback(
    (accepted: File[]) => {
      const updated = [...files, ...accepted]
      setFiles(updated)
      onFilesChange(updated)
    },
    [files, onFilesChange]
  )

  const removeFile = (idx: number) => {
    const updated = files.filter((_, i) => i !== idx)
    setFiles(updated)
    onFilesChange(updated)
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    multiple: true,
  })

  return (
    <div className="space-y-3">
      <div
        {...getRootProps()}
        className={cn(
          'relative flex flex-col items-center justify-center px-6 py-12 rounded-[8px] border-2 border-dashed cursor-pointer transition-all duration-150',
          isDragActive
            ? 'border-[#a1d67c] bg-[rgba(161,214,124,0.06)]'
            : 'border-[rgba(255,255,255,0.12)] bg-[#0e1219] hover:border-[rgba(161,214,124,0.4)] hover:bg-[rgba(161,214,124,0.03)]'
        )}
      >
        <input {...getInputProps()} />

        {/* Icon */}
        <div
          className="w-12 h-12 rounded-[8px] flex items-center justify-center mb-4"
          style={{
            background: isDragActive
              ? 'rgba(161,214,124,0.15)'
              : 'rgba(255,255,255,0.04)',
            border: `1px solid ${isDragActive ? 'rgba(161,214,124,0.3)' : 'rgba(255,255,255,0.08)'}`,
          }}
        >
          <svg
            className="w-6 h-6"
            fill="none"
            stroke={isDragActive ? '#a1d67c' : '#3a4f6a'}
            viewBox="0 0 24 24"
          >
            <path
              d="M9 13h6m-3-3v6m5 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </div>

        {isDragActive ? (
          <p className="text-[13px] font-semibold" style={{ color: '#a1d67c' }}>
            Drop PDF plans here
          </p>
        ) : (
          <>
            <p className="text-[13px] font-semibold mb-1" style={{ color: '#d8e4f5' }}>
              Drop PDF plans here, or{' '}
              <span style={{ color: '#a1d67c' }}>browse files</span>
            </p>
            <p className="text-[12px]" style={{ color: '#3a4f6a' }}>
              PDF only · multiple files supported
            </p>
          </>
        )}
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div
          className="rounded-[8px] overflow-hidden"
          style={{
            border: '1px solid rgba(255,255,255,0.08)',
            background: '#131822',
          }}
        >
          {files.map((file, idx) => (
            <div
              key={idx}
              className="flex items-center gap-3 px-4 py-2.5"
              style={{
                borderBottom:
                  idx < files.length - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none',
              }}
            >
              {/* PDF icon */}
              <div
                className="w-7 h-7 rounded-[4px] flex items-center justify-center flex-shrink-0"
                style={{ background: 'rgba(240,82,82,0.12)', border: '1px solid rgba(240,82,82,0.2)' }}
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="#f05252" viewBox="0 0 24 24">
                  <path
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z"
                    strokeWidth="1.5"
                  />
                </svg>
              </div>

              <div className="flex-1 min-w-0">
                <p
                  className="text-[12px] font-medium truncate"
                  style={{ color: '#d8e4f5' }}
                >
                  {file.name}
                </p>
                <p
                  className="text-[11px] font-mono"
                  style={{ color: '#3a4f6a' }}
                >
                  {(file.size / 1024).toFixed(0)} KB
                </p>
              </div>

              <button
                onClick={(e) => {
                  e.stopPropagation()
                  removeFile(idx)
                }}
                className="w-6 h-6 rounded flex items-center justify-center transition-colors"
                style={{ color: '#3a4f6a' }}
                onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.color = '#f05252')}
                onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.color = '#3a4f6a')}
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path d="M6 18L18 6M6 6l12 12" strokeWidth="2" strokeLinecap="round" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
