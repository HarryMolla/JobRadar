-- ============================================================
-- JobRadar — Supabase Database Schema
-- Run this in the Supabase SQL Editor to initialize the database.
-- ============================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Main jobs table
CREATE TABLE IF NOT EXISTS jobs (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    fingerprint TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,
    source_id TEXT,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL DEFAULT '',
    location TEXT DEFAULT '',
    description TEXT DEFAULT '',
    posted_at TIMESTAMPTZ,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    remote_type TEXT DEFAULT 'unknown',
    remote_countries JSONB DEFAULT '[]',
    sponsorship TEXT DEFAULT 'unknown',
    relocation_offered BOOLEAN DEFAULT FALSE,
    employment_type TEXT DEFAULT '',
    seniority TEXT DEFAULT '',
    salary_min INTEGER,
    salary_max INTEGER,
    salary_currency TEXT DEFAULT '',
    match_score INTEGER DEFAULT 0,
    match_reasons JSONB DEFAULT '[]',
    match_category TEXT DEFAULT 'irrelevant',
    notified BOOLEAN DEFAULT FALSE,
    application_status TEXT DEFAULT 'new',
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_jobs_match_score ON jobs(match_score DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_detected_at ON jobs(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_jobs_notified ON jobs(notified);
CREATE INDEX IF NOT EXISTS idx_jobs_application_status ON jobs(application_status);
CREATE INDEX IF NOT EXISTS idx_jobs_remote_type ON jobs(remote_type);

-- Source run logs (for health dashboard)
CREATE TABLE IF NOT EXISTS source_runs (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    source TEXT NOT NULL,
    success BOOLEAN NOT NULL,
    jobs_found INTEGER DEFAULT 0,
    error TEXT DEFAULT '',
    checked_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_source_runs_source ON source_runs(source);
CREATE INDEX IF NOT EXISTS idx_source_runs_checked_at ON source_runs(checked_at DESC);

-- Auto-update last_updated on jobs
CREATE OR REPLACE FUNCTION update_last_updated()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER IF NOT EXISTS trigger_jobs_last_updated
    BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION update_last_updated();

-- Row Level Security (RLS)
-- Enable RLS but allow service role full access
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE source_runs ENABLE ROW LEVEL SECURITY;

-- Policy: service role (used by backend) has full access
CREATE POLICY IF NOT EXISTS "service_role_all_jobs"
    ON jobs FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY IF NOT EXISTS "service_role_all_source_runs"
    ON source_runs FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Policy: anon can read jobs (for Chrome extension via public API)
-- Remove this if you want to restrict to service_role only
CREATE POLICY IF NOT EXISTS "anon_read_jobs"
    ON jobs FOR SELECT
    TO anon
    USING (true);

CREATE POLICY IF NOT EXISTS "anon_read_source_runs"
    ON source_runs FOR SELECT
    TO anon
    USING (true);

-- Cleanup old source_runs (keep last 1000 per source)
-- Run this periodically if needed:
-- DELETE FROM source_runs WHERE id NOT IN (
--     SELECT id FROM source_runs ORDER BY checked_at DESC LIMIT 1000
-- );

SELECT 'Schema created successfully' AS status;
