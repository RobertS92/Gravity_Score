-- Record which score inputs were imputed (manual or heuristic) and the
-- effective data-quality used at scoring time, so reports and ops can
-- distinguish real scraped signals from fabricated fallbacks.
ALTER TABLE athlete_gravity_scores
  ADD COLUMN IF NOT EXISTS imputed_fields JSONB DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS effective_data_quality NUMERIC DEFAULT NULL;

COMMENT ON COLUMN athlete_gravity_scores.imputed_fields IS
  'Inputs filled at scoring time: {"manual": [...], "heuristic": [...]}. Empty/NULL means all inputs were real scraped values.';
COMMENT ON COLUMN athlete_gravity_scores.effective_data_quality IS
  'Data-quality score (0-1) used for this scoring run after imputation gating; lower when follower/social inputs were fabricated.';
