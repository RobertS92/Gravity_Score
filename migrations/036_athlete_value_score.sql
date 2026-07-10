-- Value Score = winning impact (public). Distinct from Gravity Score (commercial).
-- Heuristic source is win_impact_v0; ML impact_v1 overrides when champion exists.

ALTER TABLE athlete_gravity_scores
  ADD COLUMN IF NOT EXISTS value_score NUMERIC,
  ADD COLUMN IF NOT EXISTS value_score_source TEXT,
  ADD COLUMN IF NOT EXISTS impact_confidence NUMERIC;

COMMENT ON COLUMN athlete_gravity_scores.value_score IS
  'Winning impact 0-100 (Value Score). Heuristic win_impact_v0 now; ML impact_v1 when champion.';
COMMENT ON COLUMN athlete_gravity_scores.value_score_source IS
  'Provenance: win_impact_v0 | gravity_athlete_{sport}_impact_v1';
COMMENT ON COLUMN athlete_gravity_scores.impact_confidence IS
  'Confidence in value_score / win-impact features (0-1)';

CREATE INDEX IF NOT EXISTS idx_ags_value_score
  ON athlete_gravity_scores (value_score DESC NULLS LAST);

-- Backfill from dollar_confidence JSONB when present.
UPDATE athlete_gravity_scores
SET
  value_score = (dollar_confidence ->> 'win_impact_score')::numeric,
  value_score_source = COALESCE(value_score_source, 'win_impact_v0')
WHERE value_score IS NULL
  AND jsonb_typeof(dollar_confidence -> 'win_impact_score') = 'number';

-- Backfill remaining from latest raw_athlete_data.
UPDATE athlete_gravity_scores s
SET
  value_score = (r.raw_data ->> 'win_impact_score')::numeric,
  value_score_source = COALESCE(s.value_score_source, 'win_impact_v0'),
  impact_confidence = COALESCE(
    s.impact_confidence,
    CASE
      WHEN jsonb_typeof(r.raw_data -> 'impact_confidence') = 'number'
      THEN (r.raw_data ->> 'impact_confidence')::numeric
      ELSE NULL
    END
  )
FROM (
  SELECT DISTINCT ON (athlete_id) athlete_id, raw_data
  FROM raw_athlete_data
  ORDER BY athlete_id, scraped_at DESC NULLS LAST
) r
WHERE s.athlete_id = r.athlete_id
  AND s.value_score IS NULL
  AND jsonb_typeof(r.raw_data -> 'win_impact_score') = 'number';
