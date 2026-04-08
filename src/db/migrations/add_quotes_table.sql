-- Migration: add_quotes_table
-- Phase 6.5: Quote generation with sequential numbering

CREATE TABLE IF NOT EXISTS quotes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    estimate_id UUID NOT NULL REFERENCES estimates(id) ON DELETE CASCADE,
    quote_number TEXT NOT NULL UNIQUE,
    template TEXT NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_quotes_estimate_id ON quotes(estimate_id);
