-- Migration 003: roster_builds table for Roster Builder feature
-- Each row is a saved roster build (budget + athlete slots) per user.

CREATE TABLE IF NOT EXISTS roster_builds (
  id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id      UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
  name         TEXT NOT NULL DEFAULT 'My Roster',
  budget_usd   NUMERIC NOT NULL DEFAULT 1000000,
  -- slots: [{athlete_id, nil_cost_override}]
  -- nil_cost_override = null means use the athlete's dollar_p50_usd from scores
  slots        JSONB NOT NULL DEFAULT '[]',
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_roster_builds_user ON roster_builds (user_id);

ALTER TABLE roster_builds ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow_all_roster_builds" ON roster_builds;
CREATE POLICY "allow_all_roster_builds" ON roster_builds FOR ALL USING (true);
