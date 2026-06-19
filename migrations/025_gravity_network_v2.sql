-- Gravity Network v2
-- Provenance, temporal observations, supervised outcomes, model registry,
-- calibrated predictions, and athlete/team/brand relationship intelligence.

ALTER TABLE athletes
  ADD COLUMN IF NOT EXISTS nil_valuation_raw NUMERIC;

CREATE TABLE IF NOT EXISTS gravity_data_sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_key TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  source_type TEXT NOT NULL CHECK (
    source_type IN ('official', 'licensed', 'public_api', 'scrape', 'manual', 'derived')
  ),
  default_confidence NUMERIC NOT NULL DEFAULT 0.5 CHECK (
    default_confidence >= 0 AND default_confidence <= 1
  ),
  active BOOLEAN NOT NULL DEFAULT TRUE,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS gravity_observations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type TEXT NOT NULL CHECK (entity_type IN ('athlete', 'team', 'brand', 'campaign')),
  entity_id UUID NOT NULL,
  feature_key TEXT NOT NULL,
  numeric_value NUMERIC,
  text_value TEXT,
  json_value JSONB,
  observed_at TIMESTAMPTZ NOT NULL,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  source_id UUID REFERENCES gravity_data_sources(id),
  source_record_id TEXT,
  confidence NUMERIC NOT NULL DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
  verification_status TEXT NOT NULL DEFAULT 'unverified' CHECK (
    verification_status IN ('verified', 'corroborated', 'single_source', 'unverified', 'rejected')
  ),
  freshness_seconds BIGINT,
  collection_run_id TEXT,
  metadata JSONB NOT NULL DEFAULT '{}',
  CHECK (
    numeric_value IS NOT NULL OR text_value IS NOT NULL OR json_value IS NOT NULL
  )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_gravity_observation_source_record
  ON gravity_observations(entity_type, entity_id, feature_key, source_id, source_record_id)
  WHERE source_record_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_gravity_observations_entity_time
  ON gravity_observations(entity_type, entity_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_gravity_observations_feature_time
  ON gravity_observations(feature_key, observed_at DESC);

CREATE TABLE IF NOT EXISTS gravity_feature_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type TEXT NOT NULL CHECK (entity_type IN ('athlete', 'team', 'brand')),
  entity_id UUID NOT NULL,
  as_of TIMESTAMPTZ NOT NULL,
  feature_schema_version TEXT NOT NULL,
  features JSONB NOT NULL,
  missingness JSONB NOT NULL DEFAULT '{}',
  provenance_summary JSONB NOT NULL DEFAULT '{}',
  freshness_summary JSONB NOT NULL DEFAULT '{}',
  data_quality_score NUMERIC NOT NULL DEFAULT 0 CHECK (
    data_quality_score >= 0 AND data_quality_score <= 1
  ),
  out_of_distribution_score NUMERIC,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(entity_type, entity_id, as_of, feature_schema_version)
);

CREATE INDEX IF NOT EXISTS idx_gravity_feature_snapshots_latest
  ON gravity_feature_snapshots(entity_type, entity_id, as_of DESC);

CREATE TABLE IF NOT EXISTS gravity_training_labels (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type TEXT NOT NULL CHECK (entity_type IN ('athlete', 'team', 'brand', 'relationship')),
  entity_id UUID NOT NULL,
  related_entity_type TEXT,
  related_entity_id UUID,
  target_key TEXT NOT NULL,
  target_value NUMERIC,
  target_class TEXT,
  label_start_at TIMESTAMPTZ NOT NULL,
  label_end_at TIMESTAMPTZ,
  available_at TIMESTAMPTZ NOT NULL,
  source_id UUID REFERENCES gravity_data_sources(id),
  confidence NUMERIC NOT NULL DEFAULT 1 CHECK (confidence >= 0 AND confidence <= 1),
  verified BOOLEAN NOT NULL DEFAULT FALSE,
  leakage_guard JSONB NOT NULL DEFAULT '{}',
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gravity_training_labels_target_time
  ON gravity_training_labels(entity_type, target_key, available_at DESC);

CREATE TABLE IF NOT EXISTS gravity_model_registry (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_key TEXT NOT NULL,
  model_version TEXT NOT NULL,
  entity_type TEXT NOT NULL CHECK (
    entity_type IN ('athlete', 'team', 'brand', 'relationship', 'global')
  ),
  stage TEXT NOT NULL DEFAULT 'candidate' CHECK (
    stage IN ('development', 'candidate', 'shadow', 'champion', 'retired', 'failed')
  ),
  artifact_uri TEXT,
  feature_schema_version TEXT NOT NULL,
  target_schema_version TEXT NOT NULL,
  trained_at TIMESTAMPTZ,
  training_window_start TIMESTAMPTZ,
  training_window_end TIMESTAMPTZ,
  metrics JSONB NOT NULL DEFAULT '{}',
  calibration JSONB NOT NULL DEFAULT '{}',
  cohort_metrics JSONB NOT NULL DEFAULT '{}',
  training_data_hash TEXT,
  git_sha TEXT,
  config JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(model_key, model_version)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_gravity_model_champion
  ON gravity_model_registry(model_key)
  WHERE stage = 'champion';

CREATE TABLE IF NOT EXISTS gravity_predictions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type TEXT NOT NULL CHECK (entity_type IN ('athlete', 'team', 'brand', 'relationship')),
  entity_id UUID NOT NULL,
  related_entity_type TEXT,
  related_entity_id UUID,
  model_id UUID REFERENCES gravity_model_registry(id),
  model_key TEXT NOT NULL,
  model_version TEXT NOT NULL,
  scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  as_of TIMESTAMPTZ NOT NULL,
  gravity_score NUMERIC,
  component_scores JSONB NOT NULL DEFAULT '{}',
  predictions JSONB NOT NULL DEFAULT '{}',
  intervals JSONB NOT NULL DEFAULT '{}',
  confidence NUMERIC NOT NULL DEFAULT 0 CHECK (confidence >= 0 AND confidence <= 1),
  data_quality_score NUMERIC NOT NULL DEFAULT 0 CHECK (
    data_quality_score >= 0 AND data_quality_score <= 1
  ),
  out_of_distribution_score NUMERIC,
  fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
  top_drivers JSONB NOT NULL DEFAULT '[]',
  feature_snapshot_id UUID REFERENCES gravity_feature_snapshots(id),
  metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_gravity_predictions_latest
  ON gravity_predictions(entity_type, entity_id, scored_at DESC);
CREATE INDEX IF NOT EXISTS idx_gravity_predictions_model
  ON gravity_predictions(model_key, model_version, scored_at DESC);

CREATE TABLE IF NOT EXISTS gravity_teams (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  external_key TEXT UNIQUE,
  school TEXT NOT NULL,
  team_name TEXT,
  sport TEXT NOT NULL,
  conference TEXT,
  market TEXT,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(school, sport)
);

CREATE TABLE IF NOT EXISTS gravity_brands (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  category TEXT,
  market_scope TEXT,
  audience_profile JSONB NOT NULL DEFAULT '{}',
  campaign_constraints JSONB NOT NULL DEFAULT '{}',
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(name, category)
);

CREATE TABLE IF NOT EXISTS gravity_campaign_outcomes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  brand_id UUID NOT NULL REFERENCES gravity_brands(id) ON DELETE CASCADE,
  athlete_id UUID REFERENCES athletes(id) ON DELETE SET NULL,
  team_id UUID REFERENCES gravity_teams(id) ON DELETE SET NULL,
  campaign_key TEXT,
  started_at TIMESTAMPTZ NOT NULL,
  ended_at TIMESTAMPTZ,
  contracted_value_usd NUMERIC,
  impressions NUMERIC,
  engagements NUMERIC,
  conversions NUMERIC,
  revenue_usd NUMERIC,
  renewed BOOLEAN,
  completed BOOLEAN,
  compliance_incidents INT NOT NULL DEFAULT 0,
  verified BOOLEAN NOT NULL DEFAULT FALSE,
  source_id UUID REFERENCES gravity_data_sources(id),
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gravity_campaign_outcomes_brand_time
  ON gravity_campaign_outcomes(brand_id, started_at DESC);

CREATE TABLE IF NOT EXISTS gravity_entity_edges (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_type TEXT NOT NULL CHECK (source_type IN ('athlete', 'team', 'brand')),
  source_id UUID NOT NULL,
  target_type TEXT NOT NULL CHECK (target_type IN ('athlete', 'team', 'brand')),
  target_id UUID NOT NULL,
  edge_type TEXT NOT NULL,
  weight NUMERIC NOT NULL DEFAULT 1,
  confidence NUMERIC NOT NULL DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
  valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  valid_to TIMESTAMPTZ,
  features JSONB NOT NULL DEFAULT '{}',
  metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_gravity_entity_edges_source
  ON gravity_entity_edges(source_type, source_id, edge_type, valid_from DESC);
CREATE INDEX IF NOT EXISTS idx_gravity_entity_edges_target
  ON gravity_entity_edges(target_type, target_id, edge_type, valid_from DESC);

INSERT INTO gravity_data_sources (
  source_key, display_name, source_type, default_confidence
) VALUES
  ('espn', 'ESPN', 'public_api', 0.85),
  ('verified_nil_deal', 'Verified NIL Deal', 'licensed', 1.0),
  ('official_roster', 'Official Team Roster', 'official', 0.98),
  ('manual_review', 'Gravity Manual Review', 'manual', 0.9),
  ('model_derived', 'Gravity Derived Feature', 'derived', 0.6)
ON CONFLICT (source_key) DO NOTHING;

