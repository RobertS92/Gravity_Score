-- athlete_season_stats EAV grain v2 (SCRAPER_FIX_SPEC §4.2 / WP5).
--
-- Keeps the classic EAV shape (one row per stat_key) and expands the unique
-- grain to (athlete_id, sport, season_year, season_type, team_id, stat_key).
--
-- Compatibility with a prior apply of 038_athlete_season_stats_wide.sql
-- (PR #17 / this branch's earlier draft):
--   - Wide table named athlete_season_stats (jsonb `stats`, no `stat_key`)
--   - Classic EAV renamed to athlete_season_stats_eav
-- In that case we drop the wide table and rename _eav back, then ALTER.
-- Fresh apply_all from 029: athlete_season_stats is already classic EAV;
-- this file only ALTERs + creates the career view.
--
-- Existing corrupted season rows are NOT repaired here; WP7 rebuilds them.

DO $$
BEGIN
  -- Wide-table cutover already applied: restore classic EAV as the canonical name.
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'athlete_season_stats_eav'
  ) AND EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'athlete_season_stats'
      AND column_name = 'stats'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'athlete_season_stats'
      AND column_name = 'stat_key'
  ) THEN
    DROP TABLE athlete_season_stats;
    ALTER TABLE athlete_season_stats_eav RENAME TO athlete_season_stats;
    ALTER INDEX IF EXISTS idx_athlete_season_stats_eav_cohort
      RENAME TO idx_athlete_season_stats_cohort;
    ALTER INDEX IF EXISTS idx_athlete_season_stats_eav_athlete
      RENAME TO idx_athlete_season_stats_athlete;
  END IF;

  -- Only _eav remains (wide already dropped elsewhere).
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'athlete_season_stats'
  ) AND EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'athlete_season_stats_eav'
  ) THEN
    ALTER TABLE athlete_season_stats_eav RENAME TO athlete_season_stats;
    ALTER INDEX IF EXISTS idx_athlete_season_stats_eav_cohort
      RENAME TO idx_athlete_season_stats_cohort;
    ALTER INDEX IF EXISTS idx_athlete_season_stats_eav_athlete
      RENAME TO idx_athlete_season_stats_athlete;
  END IF;
END $$;

-- Idempotent grain columns on classic EAV.
ALTER TABLE athlete_season_stats
  ADD COLUMN IF NOT EXISTS season_label TEXT,
  ADD COLUMN IF NOT EXISTS season_type TEXT NOT NULL DEFAULT 'regular',
  ADD COLUMN IF NOT EXISTS team_id TEXT NOT NULL DEFAULT 'TOT',
  ADD COLUMN IF NOT EXISTS team_name TEXT,
  ADD COLUMN IF NOT EXISTS is_total BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS is_complete BOOLEAN,
  ADD COLUMN IF NOT EXISTS stats_as_of TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS source_url TEXT,
  ADD COLUMN IF NOT EXISTS validation_status TEXT;

-- Enforce allowed values (IF NOT EXISTS for constraints is not portable; drop+add).
ALTER TABLE athlete_season_stats
  DROP CONSTRAINT IF EXISTS athlete_season_stats_season_type_check;
ALTER TABLE athlete_season_stats
  ADD CONSTRAINT athlete_season_stats_season_type_check
  CHECK (season_type IN ('regular', 'postseason'));

ALTER TABLE athlete_season_stats
  DROP CONSTRAINT IF EXISTS athlete_season_stats_validation_status_check;
ALTER TABLE athlete_season_stats
  ADD CONSTRAINT athlete_season_stats_validation_status_check
  CHECK (
    validation_status IS NULL
    OR validation_status IN (
      'unvalidated', 'matched', 'mismatch', 'no_second_source'
    )
  );

-- Replace B9 unique key with full grain.
ALTER TABLE athlete_season_stats
  DROP CONSTRAINT IF EXISTS athlete_season_stats_athlete_id_sport_season_year_stat_key_key;

DROP INDEX IF EXISTS uq_ass_grain;
CREATE UNIQUE INDEX uq_ass_grain
  ON athlete_season_stats (
    athlete_id, sport, season_year, season_type, team_id, stat_key
  );

CREATE INDEX IF NOT EXISTS idx_athlete_season_stats_tot_regular
  ON athlete_season_stats (sport, position_group, season_year, stat_key)
  WHERE team_id = 'TOT' AND season_type = 'regular';

-- Career totals = SUM of per-season TOT counting rows only.
-- Rate-like keys are excluded via the same token heuristic as
-- scrapers.parsers.stat_catalog.is_counting (derive_rates recomputes rates in Python).
CREATE OR REPLACE VIEW athlete_career_stats AS
SELECT
  athlete_id,
  sport,
  season_type,
  stat_key,
  SUM(stat_value) AS career_value,
  COUNT(DISTINCT season_year) AS seasons
FROM athlete_season_stats
WHERE team_id = 'TOT'
  AND NOT (
    stat_key ~* '(avg|pct|percent|rate|per_game|pergame|per_attempt|per_carry|per_catch|yards_per|passer_rating|^rating$|long_|_long$|^long$|per_set|usage|^bpm$|^per$|ts_pct|efg|whip|^era$|ops|obp|slg|^avg$|k9|bb9|k_bb|snap_pct|receive_rating|setting_efficiency|hitting_pct|fielding_pct|completion_pct)'
  )
GROUP BY athlete_id, sport, season_type, stat_key;
