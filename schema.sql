-- ═══════════════════════════════════════════════════════
-- FAMILY CRISIS PLAYBOOK — DATABASE SCHEMA
-- Run this in Supabase SQL Editor (one time setup)
-- ═══════════════════════════════════════════════════════

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT,
    first_name TEXT,
    product TEXT NOT NULL DEFAULT 'Family Crisis File',
    progress_percent INT NOT NULL DEFAULT 0,
    last_section_completed TEXT,
    answers_json JSONB NOT NULL DEFAULT '{}',
    homework_items JSONB NOT NULL DEFAULT '[]',
    homework_count INT NOT NULL DEFAULT 0,
    snapshot_results JSONB NOT NULL DEFAULT '{}',
    walkthrough_completed BOOLEAN NOT NULL DEFAULT FALSE,
    purchase_status TEXT NOT NULL DEFAULT 'not_purchased'
        CHECK (purchase_status IN ('not_purchased', 'purchased', 'refunded')),
    purchase_id TEXT,
    pdf_generated BOOLEAN NOT NULL DEFAULT FALSE,
    pdf_url TEXT,
    pdf_error BOOLEAN NOT NULL DEFAULT FALSE,
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for finding abandoned sessions
CREATE INDEX IF NOT EXISTS idx_sessions_last_activity
    ON sessions (last_activity_at)
    WHERE walkthrough_completed = FALSE;

-- Index for looking up by email
CREATE INDEX IF NOT EXISTS idx_sessions_email
    ON sessions (email)
    WHERE email IS NOT NULL;

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS sessions_updated_at ON sessions;
CREATE TRIGGER sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Storage bucket for PDFs (Phase 3)
-- INSERT INTO storage.buckets (id, name, public)
-- VALUES ('playbook-pdfs', 'playbook-pdfs', false)
-- ON CONFLICT DO NOTHING;

SELECT 'Schema created successfully' AS status;
