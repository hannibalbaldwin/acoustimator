'use client'

import { useState, useEffect, useRef } from 'react'
import { useSession } from 'next-auth/react'
import {
  listEstimateNotes,
  createEstimateNote,
  updateEstimateNote,
  deleteEstimateNote,
  type EstimateNote,
} from '@/lib/api'

const CA_GREEN = '#a1d67c'
const AUTHOR_KEY = 'acoustimator_note_author'

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 7) return `${days}d ago`
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function AuthorAvatar({ name, size = 28 }: { name: string; size?: number }) {
  const initial = (name || '?').charAt(0).toUpperCase()
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        background: CA_GREEN,
        color: '#0f1923',
        fontSize: size * 0.43,
        fontWeight: 700,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        userSelect: 'none',
      }}
    >
      {initial}
    </div>
  )
}

interface NoteRowProps {
  note: EstimateNote
  isLight: boolean
  onEdit: (note: EstimateNote) => void
  onDelete: (note: EstimateNote) => void
}

function NoteRow({ note, isLight, onEdit, onDelete }: NoteRowProps) {
  const [hovered, setHovered] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const textPrimary = isLight ? '#0f1923' : '#d8e4f5'
  const textMuted = isLight ? '#7890aa' : '#3a4f6a'
  const textBold = isLight ? '#1a2335' : '#c8daef'

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => { setHovered(false); setConfirmDelete(false) }}
      style={{ display: 'flex', gap: '10px', alignItems: 'flex-start', position: 'relative' }}
    >
      <AuthorAvatar name={note.author_name} />
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Header row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '3px' }}>
          <span style={{ fontSize: '13px', fontWeight: 700, color: textBold }}>{note.author_name}</span>
          <span style={{ fontSize: '11px', color: textMuted }}>{relativeTime(note.created_at)}</span>
          {note.updated_at !== note.created_at && (
            <span style={{ fontSize: '10px', color: textMuted, fontStyle: 'italic' }}>(edited)</span>
          )}
        </div>

        {/* Content */}
        <p
          style={{
            fontSize: '13px',
            lineHeight: '1.5',
            color: textPrimary,
            margin: 0,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {note.content}
        </p>

        {/* Inline delete confirm */}
        {confirmDelete && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '6px' }}>
            <span style={{ fontSize: '12px', color: '#f05252' }}>Delete this note?</span>
            <button
              onClick={() => setConfirmDelete(false)}
              style={{
                fontSize: '12px',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: textMuted,
                padding: 0,
              }}
            >
              Cancel
            </button>
            <button
              onClick={() => onDelete(note)}
              style={{
                fontSize: '12px',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: '#f05252',
                fontWeight: 600,
                padding: 0,
              }}
            >
              Delete
            </button>
          </div>
        )}
      </div>

      {/* Hover action buttons */}
      {hovered && !confirmDelete && (
        <div style={{ display: 'flex', gap: '4px', flexShrink: 0 }}>
          {/* Edit button */}
          <button
            title="Edit note"
            onClick={() => onEdit(note)}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '3px 5px',
              borderRadius: '4px',
              color: textMuted,
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
            </svg>
          </button>
          {/* Delete button */}
          <button
            title="Delete note"
            onClick={() => setConfirmDelete(true)}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '3px 5px',
              borderRadius: '4px',
              color: textMuted,
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
              <path d="M10 11v6M14 11v6" />
              <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
            </svg>
          </button>
        </div>
      )}
    </div>
  )
}

interface NotesThreadProps {
  estimateId: string
  isLight?: boolean
}

export function NotesThread({ estimateId, isLight = false }: NotesThreadProps) {
  const { data: session } = useSession()
  const sessionName = session?.user?.name ?? session?.user?.email ?? null

  const [notes, setNotes] = useState<EstimateNote[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Compose box state
  const [composeContent, setComposeContent] = useState('')
  const [composeAuthor, setComposeAuthor] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Edit mode state
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null)
  const [editContent, setEditContent] = useState('')
  const [editSaving, setEditSaving] = useState(false)

  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Colours
  const textPrimary = isLight ? '#0f1923' : '#d8e4f5'
  const textMuted = isLight ? '#7890aa' : '#3a4f6a'
  const cardBg = isLight ? '#ffffff' : '#131822'
  const border = isLight ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.08)'
  const inputBg = isLight ? '#f5f7fa' : '#0e1219'
  const inputBorder = isLight ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.1)'
  const dividerColor = isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.06)'

  // Populate author: session name takes priority, fall back to localStorage
  useEffect(() => {
    if (sessionName) {
      setComposeAuthor(sessionName)
      return
    }
    try {
      const stored = localStorage.getItem(AUTHOR_KEY)
      if (stored) setComposeAuthor(stored)
    } catch { /* ignore */ }
  }, [sessionName])

  // Fetch notes on mount
  useEffect(() => {
    setLoading(true)
    listEstimateNotes(estimateId)
      .then((data) => { setNotes(data); setLoading(false) })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Failed to load notes')
        setLoading(false)
      })
  }, [estimateId])

  const handleAuthorChange = (val: string) => {
    setComposeAuthor(val)
    try { localStorage.setItem(AUTHOR_KEY, val) } catch { /* ignore */ }
  }

  const handleSubmit = async () => {
    if (!composeContent.trim() || !composeAuthor.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const note = await createEstimateNote(estimateId, composeContent.trim(), composeAuthor.trim())
      setNotes((prev) => [...prev, note])
      setComposeContent('')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to add note')
    } finally {
      setSubmitting(false)
    }
  }

  const handleEditStart = (note: EstimateNote) => {
    setEditingNoteId(note.id)
    setEditContent(note.content)
  }

  const handleEditSave = async (noteId: string) => {
    if (!editContent.trim()) return
    setEditSaving(true)
    try {
      const updated = await updateEstimateNote(estimateId, noteId, editContent.trim())
      setNotes((prev) => prev.map((n) => (n.id === noteId ? updated : n)))
      setEditingNoteId(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save note')
    } finally {
      setEditSaving(false)
    }
  }

  const handleDelete = async (note: EstimateNote) => {
    try {
      await deleteEstimateNote(estimateId, note.id)
      setNotes((prev) => prev.filter((n) => n.id !== note.id))
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete note')
    }
  }

  const canSubmit = composeContent.trim().length > 0 && composeAuthor.trim().length > 0

  return (
    <div
      style={{
        borderRadius: '8px',
        padding: '16px',
        background: cardBg,
        border: `1px solid ${border}`,
      }}
    >
      {/* Header */}
      <h3
        style={{
          fontSize: '10px',
          fontWeight: 600,
          letterSpacing: '0.09em',
          textTransform: 'uppercase',
          color: textMuted,
          margin: '0 0 12px 0',
        }}
      >
        Notes
      </h3>

      {/* Error */}
      {error && (
        <p style={{ fontSize: '12px', color: '#f05252', margin: '0 0 8px 0' }}>{error}</p>
      )}

      {/* Thread */}
      {loading ? (
        <p style={{ fontSize: '12px', color: textMuted }}>Loading...</p>
      ) : notes.length === 0 ? (
        <p style={{ fontSize: '12px', color: textMuted, margin: '0 0 12px 0', fontStyle: 'italic' }}>
          No notes yet — add the first one below.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginBottom: '14px' }}>
          {notes.map((note) =>
            editingNoteId === note.id ? (
              /* Edit mode */
              <div key={note.id} style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                <AuthorAvatar name={note.author_name} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <span style={{ fontSize: '13px', fontWeight: 700, color: isLight ? '#1a2335' : '#c8daef', display: 'block', marginBottom: '4px' }}>
                    {note.author_name}
                  </span>
                  <textarea
                    ref={textareaRef}
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    rows={3}
                    style={{
                      width: '100%',
                      fontSize: '13px',
                      lineHeight: '1.5',
                      resize: 'none',
                      background: inputBg,
                      border: `1px solid ${inputBorder}`,
                      borderRadius: '6px',
                      padding: '8px 10px',
                      color: textPrimary,
                      outline: 'none',
                      boxSizing: 'border-box',
                    }}
                    autoFocus
                  />
                  <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
                    <button
                      onClick={() => void handleEditSave(note.id)}
                      disabled={editSaving || !editContent.trim()}
                      style={{
                        fontSize: '12px',
                        fontWeight: 600,
                        padding: '4px 12px',
                        borderRadius: '6px',
                        border: 'none',
                        cursor: editSaving || !editContent.trim() ? 'not-allowed' : 'pointer',
                        background: editSaving || !editContent.trim()
                          ? 'rgba(161,214,124,0.3)'
                          : 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
                        color: '#080b10',
                      }}
                    >
                      {editSaving ? 'Saving...' : 'Save'}
                    </button>
                    <button
                      onClick={() => setEditingNoteId(null)}
                      style={{
                        fontSize: '12px',
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        color: textMuted,
                        padding: '4px 8px',
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <NoteRow
                key={note.id}
                note={note}
                isLight={isLight}
                onEdit={handleEditStart}
                onDelete={handleDelete}
              />
            )
          )}
        </div>
      )}

      {/* Divider */}
      <div style={{ height: '1px', background: dividerColor, margin: '12px 0' }} />

      {/* Compose box */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {/* Name field — hidden when session provides the author */}
        {!sessionName && (
          <input
            type="text"
            placeholder="Your name"
            value={composeAuthor}
            onChange={(e) => handleAuthorChange(e.target.value)}
            style={{
              width: '120px',
              fontSize: '12px',
              padding: '5px 8px',
              borderRadius: '6px',
              background: inputBg,
              border: `1px solid ${inputBorder}`,
              color: textPrimary,
              outline: 'none',
            }}
          />
        )}
        <textarea
          placeholder="Add a note..."
          rows={3}
          value={composeContent}
          onChange={(e) => setComposeContent(e.target.value)}
          onKeyDown={(e) => {
            // Ctrl/Cmd+Enter to submit
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && canSubmit) {
              e.preventDefault()
              void handleSubmit()
            }
          }}
          style={{
            width: '100%',
            fontSize: '13px',
            lineHeight: '1.5',
            resize: 'none',
            background: inputBg,
            border: `1px solid ${inputBorder}`,
            borderRadius: '6px',
            padding: '8px 10px',
            color: textPrimary,
            outline: 'none',
            boxSizing: 'border-box',
          }}
        />
        <button
          onClick={() => void handleSubmit()}
          disabled={submitting || !canSubmit}
          style={{
            alignSelf: 'flex-start',
            fontSize: '13px',
            fontWeight: 600,
            padding: '6px 16px',
            borderRadius: '6px',
            border: 'none',
            cursor: submitting || !canSubmit ? 'not-allowed' : 'pointer',
            background: submitting || !canSubmit
              ? 'rgba(161,214,124,0.3)'
              : 'linear-gradient(135deg, #5a8a1e 0%, #a1d67c 100%)',
            color: '#080b10',
            transition: 'opacity 0.15s',
          }}
        >
          {submitting ? 'Adding...' : 'Add Note'}
        </button>
      </div>
    </div>
  )
}
