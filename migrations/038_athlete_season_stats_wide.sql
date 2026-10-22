-- Canonical per-season athlete stats (wide rows).
-- Spec: docs/SCRAPER_SEASON_BACKFILL_SPEC.md
-- Unique key: (athlete_id, league, espn_season_year, season_type, team_id)
--
-- Previous EAV shape (stat_key / stat_value) is preserved as athlete_season_stats_eav
-- for cohort baselines during cutover; writers dual-write both.

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'athlete_season_stats'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'athlete_season_stats_eav'
  ) AND EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'athlete_season_stats'
      AND column_name = 'stat_key'
  ) THEN
    ALTER TABLE athlete_season_stats RENAME TO athlete_season_stats_eav;
    ALTER INDEX IF EXISTS idx_athlete_season_stats_cohort
      RENAME TO idx_athlete_season_stats_eav_cohort;
    ALTER INDEX IF EXISTS idx_athlete_season_stats_athlete
      RENAME TO idx_athlete_season_stats_eav_athlete;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS athlete_season_stats (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
  espn_id TEXT,
  sport TEXT NOT NULL,
  league TEXT NOT NULL,
  season_label TEXT NOT NULL,
  espn_season_year INT NOT NULL,
  -- Alias used by legacy cohort / feature code that still says season_year.
  season_year INT GENERATED ALWAYS AS (espn_season_year) STORED,
  season_type TEXT NOT NULL DEFAULT 'regular'
    CHECK (season_type IN ('regular', 'postseason')),
  team_id TEXT NOT NULL DEFAULT 'UNK',
  team_abbr TEXT,
  games_played INT,
  stats JSONB NOT NULL DEFAULT '{}'::jsonb,
  is_complete BOOLEAN NOT NULL DEFAULT TRUE,
  is_total BOOLEAN NOT NULL DEFAULT FALSE,
  stats_as_of TIMESTAMPTZ NOT NULL,
  source TEXT NOT NULL,
  source_url TEXT NOT NULL,
  collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  collection_errors JSONB NOT NULL DEFAULT '[]'::jsonb,
  position_group TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (athlete_id, league, espn_season_year, season_type, team_id)
);

CREATE INDEX IF NOT EXISTS idx_athlete_season_stats_athlete_year
  ON athlete_season_stats (athlete_id, espn_season_year DESC);

CREATE INDEX IF NOT EXISTS idx_athlete_season_stats_cohort
  ON athlete_season_stats (sport, position_group, espn_season_year);

CREATE INDEX IF NOT EXISTS idx_athlete_season_stats_league_year
  ON athlete_season_stats (league, espn_season_year);

-- EAV projection for cohort code that still expects stat_key / stat_value.
CREATE TABLE IF NOT EXISTS athlete_season_stats_eav (
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
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (athlete_id, sport, season_year, stat_key)
);

CREATE INDEX IF NOT EXISTS idx_athlete_season_stats_eav_cohort
  ON athlete_season_stats_eav (sport, position_group, season_year, stat_key);

CREATE INDEX IF NOT EXISTS idx_athlete_season_stats_eav_athlete
  ON athlete_season_stats_eav (athlete_id, season_year DESC);
