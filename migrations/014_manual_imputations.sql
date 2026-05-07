-- Manual and heuristic imputations used by scoring fallback.
CREATE TABLE IF NOT EXISTS athlete_manual_imputations (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id    UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
  scope         TEXT NOT NULL CHECK (scope IN ('global', 'org')),
  org_id        UUID REFERENCES organizations(id) ON DELETE CASCADE,
  field_name    TEXT NOT NULL,
  field_value   JSONB NOT NULL,
  confidence    DOUBLE PRECISION NOT NULL DEFAULT 0.6,
  source_type   TEXT NOT NULL CHECK (source_type IN ('admin_manual', 'school_manual', 'heuristic')),
  reason        TEXT,
  created_by    UUID REFERENCES user_accounts(id) ON DELETE SET NULL,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_manual_impute_global_unique
  ON athlete_manual_imputations (athlete_id, field_name)
  WHERE scope = 'global' AND org_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_manual_impute_org_unique
  ON athlete_manual_imputations (athlete_id, org_id, field_name)
  WHERE scope = 'org' AND org_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_manual_impute_athlete ON athlete_manual_imputations (athlete_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_manual_impute_org ON athlete_manual_imputations (org_id, updated_at DESC);
