-- Scope-specific NIL transaction labels, score snapshots, and measured calibration.
-- This migration deliberately separates an annual athlete valuation from five
-- commercially different transaction types.

DO $$ BEGIN
  CREATE TYPE nil_deal_scope AS ENUM (
    'standard_activation',
    'season_partnership',
    'collective_package',
    'group_licensing',
    'revenue_sharing'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS athlete_score_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
  observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  model_version TEXT,
  gravity_score DOUBLE PRECISION,
  brand_score DOUBLE PRECISION,
  proof_score DOUBLE PRECISION,
  proximity_score DOUBLE PRECISION,
  velocity_score DOUBLE PRECISION,
  risk_score DOUBLE PRECISION,
  annual_benchmark_usd DOUBLE PRECISION,
  score_confidence DOUBLE PRECISION,
  score_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (athlete_id, observed_at, model_version)
);
CREATE INDEX IF NOT EXISTS idx_score_snapshots_athlete_time
  ON athlete_score_snapshots (athlete_id, observed_at DESC);

CREATE OR REPLACE FUNCTION capture_athlete_score_snapshot()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO athlete_score_snapshots (
    athlete_id, observed_at, model_version, gravity_score, brand_score,
    proof_score, proximity_score, velocity_score, risk_score,
    annual_benchmark_usd, score_confidence, score_payload
  ) VALUES (
    NEW.athlete_id, COALESCE(NEW.calculated_at, NOW()), NEW.model_version,
    NEW.gravity_score, NEW.brand_score, NEW.proof_score, NEW.proximity_score,
    NEW.velocity_score, NEW.risk_score, NEW.dollar_p50_usd, NEW.confidence,
    jsonb_build_object(
      'dollar_p10_usd', NEW.dollar_p10_usd,
      'dollar_p90_usd', NEW.dollar_p90_usd,
      'dollar_confidence', NEW.dollar_confidence
    )
  ) ON CONFLICT DO NOTHING;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_capture_athlete_score_snapshot ON athlete_gravity_scores;
CREATE TRIGGER trg_capture_athlete_score_snapshot
AFTER INSERT OR UPDATE OF gravity_score, brand_score, proof_score, proximity_score,
  velocity_score, risk_score, dollar_p50_usd, confidence, calculated_at
ON athlete_gravity_scores
FOR EACH ROW EXECUTE FUNCTION capture_athlete_score_snapshot();

CREATE TABLE IF NOT EXISTS verified_deal_transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
  deal_scope nil_deal_scope NOT NULL,
  amount_usd DOUBLE PRECISION NOT NULL CHECK (amount_usd > 0),
  deal_date DATE NOT NULL,
  available_at TIMESTAMPTZ NOT NULL,
  start_date DATE,
  end_date DATE,
  brand_name TEXT,
  deliverables JSONB NOT NULL DEFAULT '[]'::jsonb,
  exclusivity JSONB NOT NULL DEFAULT '{}'::jsonb,
  usage_rights JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_url TEXT NOT NULL CHECK (source_url ~ '^https?://[^[:space:]]+$'),
  source_domain TEXT NOT NULL,
  source_tier TEXT NOT NULL CHECK (source_tier IN ('primary', 'authoritative_secondary')),
  verification_status TEXT NOT NULL CHECK (
    verification_status IN ('two_source_verified', 'primary_document_verified')
  ),
  verified_at TIMESTAMPTZ NOT NULL,
  verified_by TEXT NOT NULL,
  source_evidence JSONB NOT NULL CHECK (jsonb_typeof(source_evidence) = 'object'),
  score_snapshot_id UUID REFERENCES athlete_score_snapshots(id),
  transaction_fingerprint TEXT NOT NULL UNIQUE,
  retracted_at TIMESTAMPTZ,
  retracted_reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (available_at >= deal_date::timestamptz),
  CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
);
CREATE INDEX IF NOT EXISTS idx_verified_transactions_scope_date
  ON verified_deal_transactions (deal_scope, deal_date);
CREATE INDEX IF NOT EXISTS idx_verified_transactions_athlete_date
  ON verified_deal_transactions (athlete_id, deal_date);

CREATE TABLE IF NOT EXISTS deal_model_calibrations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  deal_scope nil_deal_scope NOT NULL,
  model_version TEXT NOT NULL,
  trained_through DATE NOT NULL,
  evaluated_from DATE NOT NULL,
  evaluated_through DATE NOT NULL,
  train_transactions INT NOT NULL CHECK (train_transactions >= 0),
  validation_transactions INT NOT NULL CHECK (validation_transactions >= 0),
  unique_validation_athletes INT NOT NULL CHECK (unique_validation_athletes >= 0),
  target_coverage DOUBLE PRECISION NOT NULL CHECK (target_coverage > 0 AND target_coverage < 1),
  empirical_coverage DOUBLE PRECISION NOT NULL CHECK (empirical_coverage >= 0 AND empirical_coverage <= 1),
  median_absolute_percentage_error DOUBLE PRECISION NOT NULL CHECK (median_absolute_percentage_error >= 0),
  median_signed_percentage_error DOUBLE PRECISION NOT NULL,
  log_residual_lower DOUBLE PRECISION NOT NULL,
  log_residual_upper DOUBLE PRECISION NOT NULL,
  split_policy TEXT NOT NULL DEFAULT 'temporal_athlete_purged_v1',
  metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (deal_scope, model_version, evaluated_through)
);

COMMENT ON TABLE verified_deal_transactions IS
  'Strict, timestamped, scope-specific transaction outcomes. Unverified legacy deals are intentionally excluded.';
COMMENT ON TABLE deal_model_calibrations IS
  'Out-of-time, athlete-purged error measurements used to construct intervals and user-facing confidence.';
