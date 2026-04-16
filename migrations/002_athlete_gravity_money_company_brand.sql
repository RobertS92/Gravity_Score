-- Dollar quantiles, confidence, program (company) gravity, and brand-market gravity on each score row.
ALTER TABLE athlete_gravity_scores
  ADD COLUMN IF NOT EXISTS dollar_p10_usd NUMERIC,
  ADD COLUMN IF NOT EXISTS dollar_p50_usd NUMERIC,
  ADD COLUMN IF NOT EXISTS dollar_p90_usd NUMERIC,
  ADD COLUMN IF NOT EXISTS dollar_confidence JSONB DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS company_gravity_score NUMERIC,
  ADD COLUMN IF NOT EXISTS brand_gravity_score NUMERIC;

COMMENT ON COLUMN athlete_gravity_scores.company_gravity_score IS 'Program/school Gravity (TeamGravityNet) at scoring time';
COMMENT ON COLUMN athlete_gravity_scores.brand_gravity_score IS 'Brand-market composite (emphasis brand + velocity + proof)';
COMMENT ON COLUMN athlete_gravity_scores.dollar_p10_usd IS 'Model NIL deal range low (10th pct)';
COMMENT ON COLUMN athlete_gravity_scores.dollar_p50_usd IS 'Model NIL deal median';
COMMENT ON COLUMN athlete_gravity_scores.dollar_p90_usd IS 'Model NIL deal range high (90th pct)';
