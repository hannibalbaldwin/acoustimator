-- Migration: add_estimate_notes_table
-- Phase 7.5: Threaded notes system for estimates

CREATE TABLE IF NOT EXISTS estimate_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    estimate_id UUID NOT NULL REFERENCES estimates(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    author_name TEXT NOT NULL DEFAULT 'Unknown',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_estimate_notes_estimate_id ON estimate_notes(estimate_id);
