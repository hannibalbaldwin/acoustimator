'use client'

import { useCallback, useState } from 'react'
import { useDropzone, type FileRejection } from 'react-dropzone'
import { cn } from '@/lib/utils'

interface FileEntry {
  file: File
  id: string
}

interface PlanUploadZoneProps {
  onFilesChange?: (files: File[]) => void
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function PlanUploadZone({ onFilesChange }: PlanUploadZoneProps) {
  const [files, setFiles] = useState<FileEntry[]>([])
  const [errors, setErrors] = useState<string[]>([])

  const onDrop = useCallback(
    (accepted: File[], rejected: FileRejection[]) => {
      const newErrors: string[] = []

      rejected.forEach(({ file, errors: errs }) => {
        errs.forEach((e) => {
          if (e.code === 'file-too-large') {
            newErrors.push(`${file.name}: file exceeds 50 MB limit`)
          } else if (e.code === 'file-invalid-type') {
            newErrors.push(`${file.name}: only PDF files are accepted`)
          } else {
            newErrors.push(`${file.name}: ${e.message}`)
          }
        })
      })

      setErrors(newErrors)

      const newEntries = accepted.map((f) => ({ file: f, id: `${f.name}-${Date.now()}` }))
      const updated = [...files, ...newEntries]
      setFiles(updated)
      onFilesChange?.(updated.map((e) => e.file))
    },
    [files, onFilesChange]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxSize: 50 * 1024 * 1024,
    multiple: true,
  })

  const removeFile = (id: string) => {
    const updated = files.filter((f) => f.id !== id)
    setFiles(updated)
    onFilesChange?.(updated.map((e) => e.file))
  }

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        className={cn(
          'relative border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-all',
          isDragActive
            ? 'border-blue-500 bg-blue-50'
            : 'border-zinc-300 bg-zinc-50 hover:border-zinc-400 hover:bg-zinc-100'
        )}
      >
        <input {...getInputProps()} />

        <div className="flex flex-col items-center gap-3">
          <div
            className={cn(
              'w-12 h-12 rounded-full flex items-center justify-center transition-colors',
              isDragActive ? 'bg-blue-100' : 'bg-zinc-200'
            )}
          >
            <svg
              className={cn('w-6 h-6', isDragActive ? 'text-blue-600' : 'text-zinc-500')}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                d="M7 16a4 4 0 0 1-.88-7.903A5 5 0 1 1 15.9 6L16 6a5 5 0 0 1 1 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>

          {isDragActive ? (
            <p className="text-base font-medium text-blue-700">Drop PDF plans here...</p>
          ) : (
            <>
              <p className="text-base font-medium text-zinc-700">
                Drop PDF plans here or{' '}
                <span className="text-blue-600 underline underline-offset-2">click to browse</span>
              </p>
              <p className="text-sm text-zinc-400">
                PDF only · Up to 50 MB per file · Multiple files accepted
              </p>
            </>
          )}
        </div>
      </div>

      {errors.length > 0 && (
        <div className="rounded border border-red-200 bg-red-50 px-4 py-3">
          {errors.map((err, i) => (
            <p key={i} className="text-xs text-red-700">
              {err}
            </p>
          ))}
        </div>
      )}

      {files.length > 0 && (
        <div className="border border-zinc-200 rounded-lg overflow-hidden">
          <div className="px-4 py-2 bg-zinc-50 border-b border-zinc-200">
            <p className="text-xs font-semibold text-zinc-600">
              {files.length} file{files.length !== 1 ? 's' : ''} selected
            </p>
          </div>
          <ul className="divide-y divide-zinc-100">
            {files.map(({ file, id }) => (
              <li key={id} className="flex items-center justify-between px-4 py-2.5 hover:bg-zinc-50">
                <div className="flex items-center gap-2.5">
                  <div className="w-7 h-7 bg-red-100 rounded flex items-center justify-center flex-shrink-0">
                    <svg
                      className="w-3.5 h-3.5 text-red-600"
                      fill="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zm4 18H6V4h7v5h5v11z" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-zinc-800">{file.name}</p>
                    <p className="text-[11px] text-zinc-400 font-mono">{formatBytes(file.size)}</p>
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    removeFile(id)
                  }}
                  className="text-zinc-400 hover:text-red-500 transition-colors p-1"
                  aria-label="Remove file"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path d="M6 18L18 6M6 6l12 12" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
