-- Migration: Add scraper_jobs and test_executions tables
-- Date: 2026-01-23
-- Description: Tables for tracking scraper job execution and test results

-- Job execution tracking table
CREATE TABLE IF NOT EXISTS scraper_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_type TEXT NOT NULL, -- 'daily_vip', 'weekly_full', 'on_demand'
    league TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    athletes_total INTEGER DEFAULT 0,
    athletes_processed INTEGER DEFAULT 0,
    athletes_failed INTEGER DEFAULT 0,
    events_created INTEGER DEFAULT 0,
    errors JSONB,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for scraper_jobs
CREATE INDEX IF NOT EXISTS idx_scraper_jobs_status ON scraper_jobs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scraper_jobs_type ON scraper_jobs(job_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scraper_jobs_created ON scraper_jobs(created_at DESC);

-- Test execution tracking table
CREATE TABLE IF NOT EXISTS test_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    test_name TEXT NOT NULL,
    test_type TEXT NOT NULL, -- 'unit', 'integration', 'e2e'
    status TEXT NOT NULL CHECK (status IN ('passed', 'failed', 'skipped')),
    duration_ms INTEGER,
    error_message TEXT,
    test_output JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for test_executions
CREATE INDEX IF NOT EXISTS idx_test_executions_name ON test_executions(test_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_test_executions_status ON test_executions(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_test_executions_created ON test_executions(created_at DESC);

-- Add comments for documentation
COMMENT ON TABLE scraper_jobs IS 'Tracks execution of scraper and crawler jobs';
COMMENT ON TABLE test_executions IS 'Tracks execution of automated tests';

COMMENT ON COLUMN scraper_jobs.job_type IS 'Type of job: daily_vip (top 100), weekly_full (all athletes), or on_demand';
COMMENT ON COLUMN scraper_jobs.status IS 'Current status: pending, running, completed, or failed';
COMMENT ON COLUMN test_executions.test_type IS 'Type of test: unit, integration, or e2e';
COMMENT ON COLUMN test_executions.status IS 'Result: passed, failed, or skipped';
