-- Migration 004: athlete_events — central event ledger for the living model system
-- Never delete rows from this table; append-only.
-- processed_at = NULL means the event processor has not yet handled this event.

-- Create the table if it does not exist (fresh install)
CREATE TABLE IF NOT EXISTS athlete_events (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id      UUID REFERENCES athletes(id) NOT NULL,
  event_type      TEXT NOT NULL,
  event_source    TEXT NOT NULL DEFAULT 'unknown',
  event_data      JSONB NOT NULL DEFAULT '{}',
  signal_strength DECIMAL DEFAULT 1.0,
  occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  processed_at    TIMESTAMPTZ,
  score_impact    JSONB,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- If the table already existed with the old schema (event_severity / title / metadata / source),
-- add the new columns safely. All are nullable so old rows are unaffected.
ALTER TABLE athlete_events ADD COLUMN IF NOT EXISTS event_source    TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE athlete_events ADD COLUMN IF NOT EXISTS event_data      JSONB NOT NULL DEFAULT '{}';
ALTER TABLE athlete_events ADD COLUMN IF NOT EXISTS signal_strength DECIMAL DEFAULT 1.0;
ALTER TABLE athlete_events ADD COLUMN IF NOT EXISTS processed_at    TIMESTAMPTZ;
ALTER TABLE athlete_events ADD COLUMN IF NOT EXISTS score_impact    JSONB;
ALTER TABLE athlete_events ADD COLUMN IF NOT EXISTS created_at      TIMESTAMPTZ DEFAULT NOW();

-- Primary index: event processor polls WHERE processed_at IS NULL
CREATE INDEX IF NOT EXISTS idx_events_unprocessed
  ON athlete_events(processed_at, occurred_at)
  WHERE processed_at IS NULL;

-- Per-athlete history index
CREATE INDEX IF NOT EXISTS idx_events_athlete
  ON athlete_events(athlete_id, occurred_at DESC);

-- Event-type index for dedup checks
CREATE INDEX IF NOT EXISTS idx_events_type
  ON athlete_events(athlete_id, event_type);

ALTER TABLE athlete_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow_all_athlete_events" ON athlete_events;
CREATE POLICY "allow_all_athlete_events" ON athlete_events FOR ALL USING (true);
