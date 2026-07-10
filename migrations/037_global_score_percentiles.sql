-- Global scores remain cross-sport comparable; these columns carry the
-- athlete's rank within their own sport.
ALTER TABLE athlete_gravity_scores
  ADD COLUMN IF NOT EXISTS gravity_sport_percentile NUMERIC,
  ADD COLUMN IF NOT EXISTS value_sport_percentile NUMERIC;

COMMENT ON COLUMN athlete_gravity_scores.gravity_sport_percentile IS
  'Midrank percentile (1-99) of global Gravity Score among active athletes in the same sport.';
COMMENT ON COLUMN athlete_gravity_scores.value_sport_percentile IS
  'Midrank percentile (1-99) of global Value Score among active athletes in the same sport.';

CREATE INDEX IF NOT EXISTS idx_ags_gravity_sport_percentile
  ON athlete_gravity_scores (gravity_sport_percentile DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_ags_value_sport_percentile
  ON athlete_gravity_scores (value_sport_percentile DESC NULLS LAST);
