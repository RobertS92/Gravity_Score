-- Model registry expansion: value/quality/team models, quality columns, brand taxonomy.

CREATE TABLE IF NOT EXISTS team_gravity_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  team_id UUID NOT NULL,
  sport TEXT NOT NULL,
  gravity_score NUMERIC,
  quality_score NUMERIC,
  brand_score NUMERIC,
  proof_score NUMERIC,
  proximity_score NUMERIC,
  velocity_score NUMERIC,
  risk_score NUMERIC,
  model_key TEXT NOT NULL,
  model_version TEXT NOT NULL,
  confidence NUMERIC DEFAULT 0.5,
  fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
  scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_team_gravity_scores_team
  ON team_gravity_scores(team_id, scored_at DESC);

CREATE INDEX IF NOT EXISTS idx_team_gravity_scores_sport
  ON team_gravity_scores(sport, scored_at DESC);

ALTER TABLE athlete_gravity_scores
  ADD COLUMN IF NOT EXISTS quality_score NUMERIC,
  ADD COLUMN IF NOT EXISTS partnership_brand_score NUMERIC,
  ADD COLUMN IF NOT EXISTS partnership_top_brands JSONB;

CREATE TABLE IF NOT EXISTS brand_taxonomy_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  brand_key TEXT NOT NULL UNIQUE,
  category TEXT NOT NULL,
  display_name TEXT NOT NULL,
  prestige_score NUMERIC NOT NULL CHECK (prestige_score >= 0 AND prestige_score <= 100),
  tier TEXT NOT NULL DEFAULT 'national',
  component TEXT NOT NULL DEFAULT 'brand' CHECK (component IN ('brand', 'proof')),
  proof_boost NUMERIC NOT NULL DEFAULT 0,
  aliases JSONB NOT NULL DEFAULT '[]',
  metadata JSONB NOT NULL DEFAULT '{}',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_brand_taxonomy_category ON brand_taxonomy_entries(category);

-- Value + quality + team model registry seeds (development stage until trained)
INSERT INTO gravity_model_registry (
  model_key, model_version, entity_type, stage,
  feature_schema_version, target_schema_version, config
) VALUES
  ('gravity_athlete_cfb_value_v1', '1.0.0', 'athlete', 'development', 'gravity_features_bpxvr_v1', 'nil_valuation_usd',
   '{"sport":"cfb","objective":"value","target_key":"nil_valuation_usd"}'::jsonb),
  ('gravity_athlete_cfb_quality_v1', '1.0.0', 'athlete', 'development', 'gravity_features_bpxvr_v1', 'quality_score',
   '{"sport":"cfb","objective":"quality","target_key":"quality_score"}'::jsonb),
  ('gravity_team_cfb_value_v1', '1.0.0', 'team', 'development', 'gravity_features_program_v1', 'team_nil_proxy',
   '{"sport":"cfb","objective":"value"}'::jsonb),
  ('gravity_team_cfb_quality_v1', '1.0.0', 'team', 'development', 'gravity_features_program_v1', 'team_win_proxy',
   '{"sport":"cfb","objective":"quality"}'::jsonb),
  ('gravity_brand_sponsor_v1', '1.0.0', 'brand', 'development', 'gravity_features_brand_v1', 'brand_prestige',
   '{"objective":"brand_sponsor"}'::jsonb)
ON CONFLICT (model_key, model_version) DO UPDATE SET
  config = EXCLUDED.config,
  target_schema_version = EXCLUDED.target_schema_version;

-- Seed remaining sports (athlete value + quality + team value + quality)
INSERT INTO gravity_model_registry (model_key, model_version, entity_type, stage, feature_schema_version, target_schema_version, config)
SELECT
  format('gravity_athlete_%s_value_v1', s.sport),
  '1.0.0', 'athlete', 'development', 'gravity_features_bpxvr_v1',
  CASE WHEN s.sport IN ('nfl','nba','wnba') THEN 'contract_guaranteed_usd' ELSE 'nil_valuation_usd' END,
  jsonb_build_object('sport', s.sport, 'objective', 'value')
FROM (VALUES
  ('ncaab_mens'), ('ncaab_womens'), ('ncaa_baseball'), ('ncaa_volleyball'), ('nfl'), ('nba'), ('wnba')
) AS s(sport)
ON CONFLICT (model_key, model_version) DO NOTHING;

INSERT INTO gravity_model_registry (model_key, model_version, entity_type, stage, feature_schema_version, target_schema_version, config)
SELECT
  format('gravity_athlete_%s_quality_v1', s.sport),
  '1.0.0', 'athlete', 'development', 'gravity_features_bpxvr_v1', 'quality_score',
  jsonb_build_object('sport', s.sport, 'objective', 'quality')
FROM (VALUES
  ('cfb'), ('ncaab_mens'), ('ncaab_womens'), ('ncaa_baseball'), ('ncaa_volleyball'), ('nfl'), ('nba'), ('wnba')
) AS s(sport)
ON CONFLICT (model_key, model_version) DO NOTHING;

INSERT INTO gravity_model_registry (model_key, model_version, entity_type, stage, feature_schema_version, target_schema_version, config)
SELECT
  format('gravity_team_%s_value_v1', s.sport),
  '1.0.0', 'team', 'development', 'gravity_features_program_v1', 'team_nil_proxy',
  jsonb_build_object('sport', s.sport, 'objective', 'value')
FROM (VALUES
  ('cfb'), ('ncaab_mens'), ('ncaab_womens'), ('ncaa_baseball'), ('ncaa_volleyball'), ('nfl'), ('nba'), ('wnba')
) AS s(sport)
ON CONFLICT (model_key, model_version) DO NOTHING;

INSERT INTO gravity_model_registry (model_key, model_version, entity_type, stage, feature_schema_version, target_schema_version, config)
SELECT
  format('gravity_team_%s_quality_v1', s.sport),
  '1.0.0', 'team', 'development', 'gravity_features_program_v1', 'team_win_proxy',
  jsonb_build_object('sport', s.sport, 'objective', 'quality')
FROM (VALUES
  ('cfb'), ('ncaab_mens'), ('ncaab_womens'), ('ncaa_baseball'), ('ncaa_volleyball'), ('nfl'), ('nba'), ('wnba')
) AS s(sport)
ON CONFLICT (model_key, model_version) DO NOTHING;
