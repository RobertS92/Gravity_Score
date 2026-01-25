-- ============================================================================
-- Crawler Execution Tracking and Score Recalculation Tables
-- ============================================================================
-- Migration: Add tables for crawler execution tracking and score recalculation
-- Date: 2024
-- ============================================================================

-- Crawler execution tracking
CREATE TABLE IF NOT EXISTS crawler_executions (
    execution_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    crawler_name VARCHAR(100) NOT NULL,
    athlete_id UUID REFERENCES athletes(athlete_id),
    sport VARCHAR(50),
    status VARCHAR(50) NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    events_created INTEGER DEFAULT 0,
    errors JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_crawler_executions_athlete 
    ON crawler_executions(athlete_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_crawler_executions_status 
    ON crawler_executions(status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_crawler_executions_crawler 
    ON crawler_executions(crawler_name, started_at DESC);

-- Crawler configuration
CREATE TABLE IF NOT EXISTS crawler_configs (
    config_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    crawler_name VARCHAR(100) UNIQUE NOT NULL,
    is_enabled BOOLEAN DEFAULT true,
    schedule_interval VARCHAR(50), -- '1h', 'daily', 'weekly'
    schedule_time VARCHAR(10), -- '02:00' for daily
    last_run_at TIMESTAMP,
    next_run_at TIMESTAMP,
    config JSONB DEFAULT '{}'::jsonb,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_crawler_configs_enabled 
    ON crawler_configs(is_enabled, next_run_at);

-- Score recalculation tracking
CREATE TABLE IF NOT EXISTS score_recalculations (
    recalculation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id UUID NOT NULL REFERENCES athletes(athlete_id),
    trigger_event_id UUID REFERENCES athlete_events(event_id),
    trigger_event_type VARCHAR(100),
    components_recalculated TEXT[], -- ['brand', 'proof', etc.]
    old_gravity_score FLOAT,
    new_gravity_score FLOAT,
    score_delta FLOAT,
    recalculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_recalculations_athlete 
    ON score_recalculations(athlete_id, recalculated_at DESC);
CREATE INDEX IF NOT EXISTS idx_recalculations_event 
    ON score_recalculations(trigger_event_id);
CREATE INDEX IF NOT EXISTS idx_recalculations_type 
    ON score_recalculations(trigger_event_type, recalculated_at DESC);

-- Enhanced athlete_events table (add crawler_name column if not exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'athlete_events' 
        AND column_name = 'crawler_name'
    ) THEN
        ALTER TABLE athlete_events ADD COLUMN crawler_name VARCHAR(100);
        CREATE INDEX IF NOT EXISTS idx_events_crawler 
            ON athlete_events(crawler_name, event_timestamp DESC);
    END IF;
END $$;

-- Comments
COMMENT ON TABLE crawler_executions IS 'Tracks execution history of all crawlers';
COMMENT ON TABLE crawler_configs IS 'Configuration and scheduling for crawlers';
COMMENT ON TABLE score_recalculations IS 'Tracks score recalculations triggered by events';
COMMENT ON COLUMN athlete_events.crawler_name IS 'Name of crawler that created this event';
