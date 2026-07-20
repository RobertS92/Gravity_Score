-- Observed market-value labels for supervised value-model training.
-- Sourced from public datasets (nflverse/OverTheCap contracts, Basketball-Reference
-- salaries, Spotrac). These are the training targets for per-sport value models —
-- CFB already trains on scraped NIL valuations; pros need real salary/contract labels.

CREATE TABLE IF NOT EXISTS athlete_value_labels (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
  sport TEXT NOT NULL,
  label_type TEXT NOT NULL,          -- contract_apy | contract_total | salary_annual | nil_valuation
  value_usd DOUBLE PRECISION NOT NULL CHECK (value_usd >= 0),
  currency TEXT NOT NULL DEFAULT 'USD',
  source TEXT NOT NULL,              -- nflverse_otc | basketball_reference | spotrac
  as_of DATE,
  season_year INT,
  confidence DOUBLE PRECISION NOT NULL DEFAULT 0.8 CHECK (confidence >= 0 AND confidence <= 1),
  meta JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (athlete_id, label_type, source, season_year)
);

CREATE INDEX IF NOT EXISTS idx_value_labels_sport ON athlete_value_labels(sport);
CREATE INDEX IF NOT EXISTS idx_value_labels_athlete ON athlete_value_labels(athlete_id);

COMMENT ON TABLE athlete_value_labels IS 'Observed market-value training labels (contracts/salaries/NIL) from public sources';
COMMENT ON COLUMN athlete_value_labels.value_usd IS 'Market value in USD for the given label_type (APY, total contract, annual salary, or NIL valuation)';
COMMENT ON COLUMN athlete_value_labels.label_type IS 'contract_apy | contract_total | salary_annual | nil_valuation';
COMMENT ON COLUMN athlete_value_labels.source IS 'Provenance: nflverse_otc | basketball_reference | spotrac';
