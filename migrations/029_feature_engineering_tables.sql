-- Feature engineering: cohort baselines, season stats, metric history for
-- percentile / trajectory / profile-card extraction (BPXVR v2).

CREATE TABLE IF NOT EXISTS gravity_cohort_baselines (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  league TEXT NOT NULL,
  sport TEXT NOT NULL,
  position_group TEXT NOT NULL,
  season_year INT,
  window_key TEXT NOT NULL DEFAULT 'season',
  metric_key TEXT NOT NULL,
  cohort_level TEXT NOT NULL DEFAULT 'primary' CHECK (
    cohort_level IN ('primary', 'fallback_season', 'fallback_multi_year', 'fallback_sport')
  ),
  n INT NOT NULL DEFAULT 0,
  mean_value NUMERIC,
  std_value NUMERIC,
  p50 NUMERIC,
  p75 NUMERIC,
  p80 NUMERIC,
  p90 NUMERIC,
  p95 NUMERIC,
  p99 NUMERIC,
  min_value NUMERIC,
  max_value NUMERIC,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  metadata JSONB NOT NULL DEFAULT '{}',
  UNIQUE (league, sport, position_group, season_year, window_key, metric_key, cohort_level)
);

CREATE INDEX IF NOT EXISTS idx_gravity_cohort_baselines_lookup
  ON gravity_cohort_baselines (league, sport, position_group, season_year, metric_key);

CREATE TABLE IF NOT EXISTS athlete_season_stats (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
  sport TEXT NOT NULL,
  league TEXT NOT NULL,
  season_year INT NOT NULL,
  position_group TEXT,
  stat_key TEXT NOT NULL,
  stat_value NUMERIC NOT NULL,
  games_played INT,
  source_key TEXT,
  observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  metadata JSONB NOT NULL DEFAULT '{}',
  UNIQUE (athlete_id, sport, season_year, stat_key)
);

CREATE INDEX IF NOT EXISTS idx_athlete_season_stats_cohort
  ON athlete_season_stats (sport, position_group, season_year, stat_key);

CREATE INDEX IF NOT EXISTS idx_athlete_season_stats_athlete
  ON athlete_season_stats (athlete_id, season_year DESC);

CREATE TABLE IF NOT EXISTS athlete_metric_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
  metric_key TEXT NOT NULL,
  period_start TIMESTAMPTZ NOT NULL,
  period_end TIMESTAMPTZ,
  window_key TEXT NOT NULL CHECK (
    window_key IN ('7d', '30d', '90d', 'season', 'yoy', 'career')
  ),
  numeric_value NUMERIC NOT NULL,
  source_key TEXT,
  confidence NUMERIC NOT NULL DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
  observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  metadata JSONB NOT NULL DEFAULT '{}',
  UNIQUE (athlete_id, metric_key, period_start, window_key)
);

CREATE INDEX IF NOT EXISTS idx_athlete_metric_history_lookup
  ON athlete_metric_history (athlete_id, metric_key, period_start DESC);
