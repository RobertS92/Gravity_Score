-- CapIQ org foundation, cap tables, school data submissions, athlete provenance.
-- FK order: organizations → organization_members → nil_scenarios → nil_roster_contracts

CREATE TABLE IF NOT EXISTS organizations (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            TEXT NOT NULL,
  slug            TEXT UNIQUE,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations (slug);

-- School-side membership: admin (sport NULL) or coach per sport
CREATE TABLE IF NOT EXISTS organization_members (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
  org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  role            TEXT NOT NULL CHECK (role IN ('school_coach', 'school_admin')),
  sport           TEXT CHECK (sport IS NULL OR sport IN ('CFB', 'NCAAB', 'NCAAW')),
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_org_members_user ON organization_members (user_id);
CREATE INDEX IF NOT EXISTS idx_org_members_org ON organization_members (org_id);
CREATE UNIQUE INDEX IF NOT EXISTS organization_members_admin_one
  ON organization_members (user_id, org_id) WHERE role = 'school_admin';
CREATE UNIQUE INDEX IF NOT EXISTS organization_members_coach_sport
  ON organization_members (user_id, org_id, sport) WHERE role = 'school_coach' AND sport IS NOT NULL;

ALTER TABLE user_accounts
  ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organizations(id);

-- Widen school-facing roles (drop old CHECK if present)
ALTER TABLE user_accounts DROP CONSTRAINT IF EXISTS user_accounts_role_check;
ALTER TABLE user_accounts ADD CONSTRAINT user_accounts_role_check CHECK (
  role IN (
    'agent', 'attorney', 'brand', 'insurer', 'admin',
    'school_coach', 'school_admin'
  )
);

-- Backfill organizations from legacy text column
INSERT INTO organizations (name, slug)
SELECT DISTINCT trim(organization) AS name,
       left(
         lower(regexp_replace(trim(organization), '[^a-zA-Z0-9]+', '-', 'g'))
         || '-' || substr(md5(trim(organization))::text, 1, 8),
         200
       ) AS slug
FROM user_accounts
WHERE organization IS NOT NULL AND trim(organization) != ''
ON CONFLICT (slug) DO NOTHING;

UPDATE user_accounts u
SET organization_id = o.id
FROM organizations o
WHERE u.organization_id IS NULL
  AND u.organization IS NOT NULL
  AND trim(u.organization) != ''
  AND lower(trim(u.organization)) = lower(trim(o.name));

-- Budget envelope per org per sport per year (total_allocation NULL = undisclosed)
CREATE TABLE IF NOT EXISTS nil_budgets (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id              UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  sport               TEXT NOT NULL CHECK (sport IN ('CFB', 'NCAAB', 'NCAAW')),
  fiscal_year         INT NOT NULL,
  total_allocation    BIGINT,
  notes               TEXT,
  set_by              UUID REFERENCES user_accounts(id),
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  updated_at          TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (org_id, sport, fiscal_year)
);

CREATE INDEX IF NOT EXISTS idx_nil_budgets_org_sport ON nil_budgets (org_id, sport);

CREATE TABLE IF NOT EXISTS nil_scenarios (
  id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                    UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  sport                     TEXT NOT NULL CHECK (sport IN ('CFB', 'NCAAB', 'NCAAW')),
  name                      TEXT NOT NULL,
  base_roster_id            UUID,
  status                    TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'promoted')),
  aggregate_gravity_score   DOUBLE PRECISION,
  total_committed           BIGINT,
  total_risk_exposure       BIGINT,
  created_by                UUID REFERENCES user_accounts(id),
  promoted_at               TIMESTAMPTZ,
  promoted_by               UUID REFERENCES user_accounts(id),
  created_at                TIMESTAMPTZ DEFAULT NOW(),
  updated_at                TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nil_scenarios_org_sport ON nil_scenarios (org_id, sport);

CREATE TABLE IF NOT EXISTS nil_roster_contracts (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                      UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  athlete_id                  UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
  sport                       TEXT NOT NULL CHECK (sport IN ('CFB', 'NCAAB', 'NCAAW')),
  base_comp                   BIGINT NOT NULL,
  incentives                  JSONB NOT NULL DEFAULT '[]',
  third_party_flag            BOOLEAN NOT NULL DEFAULT false,
  payment_schedule            JSONB NOT NULL DEFAULT '{}',
  fiscal_year_start           INT NOT NULL,
  eligibility_years_remaining INT,
  status                      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'expired', 'draft')),
  scenario_id                 UUID REFERENCES nil_scenarios(id) ON DELETE CASCADE,
  created_by                  UUID REFERENCES user_accounts(id),
  created_at                  TIMESTAMPTZ DEFAULT NOW(),
  updated_at                  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nil_contracts_org_sport ON nil_roster_contracts (org_id, sport);
CREATE INDEX IF NOT EXISTS idx_nil_contracts_official ON nil_roster_contracts (org_id, sport, fiscal_year_start)
  WHERE scenario_id IS NULL AND status = 'active';
CREATE INDEX IF NOT EXISTS idx_nil_contracts_scenario ON nil_roster_contracts (scenario_id);

CREATE TABLE IF NOT EXISTS cap_audit_log (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id     UUID NOT NULL REFERENCES user_accounts(id),
  table_name  TEXT NOT NULL,
  record_id   UUID NOT NULL,
  action      TEXT NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
  old_values  JSONB,
  new_values  JSONB,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cap_audit_org ON cap_audit_log (org_id, created_at DESC);

CREATE TABLE IF NOT EXISTS athlete_data_submissions (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id              UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
  org_id                  UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  submitted_by            UUID NOT NULL REFERENCES user_accounts(id),
  fields                  JSONB NOT NULL,
  source_notes            TEXT,
  status                  TEXT NOT NULL DEFAULT 'pending' CHECK (
    status IN ('pending', 'auto_verified', 'partial', 'flagged', 'rejected', 'promoted')
  ),
  verification_results    JSONB,
  reviewed_by             UUID REFERENCES user_accounts(id),
  review_notes            TEXT,
  reviewed_at             TIMESTAMPTZ,
  created_at              TIMESTAMPTZ DEFAULT NOW(),
  updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_athlete_submissions_org ON athlete_data_submissions (org_id, status);

CREATE TABLE IF NOT EXISTS athlete_org_overrides (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id      UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
  org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  field_name      TEXT NOT NULL,
  network_value   JSONB,
  org_value       JSONB NOT NULL,
  submission_id   UUID REFERENCES athlete_data_submissions(id),
  confidence      DOUBLE PRECISION NOT NULL DEFAULT 0.6,
  is_promoted     BOOLEAN NOT NULL DEFAULT false,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (athlete_id, org_id, field_name)
);

CREATE TABLE IF NOT EXISTS athlete_org_gravity_scores (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id        UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
  org_id            UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  gravity_score     DOUBLE PRECISION NOT NULL,
  brand_score       DOUBLE PRECISION,
  proof_score       DOUBLE PRECISION,
  proximity_score   DOUBLE PRECISION,
  velocity_score    DOUBLE PRECISION,
  risk_score        DOUBLE PRECISION,
  blend_config      JSONB,
  computed_at       TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (athlete_id, org_id)
);

ALTER TABLE athletes
  ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'scraper';
ALTER TABLE athletes
  ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT true;

COMMENT ON COLUMN athletes.source IS 'scraper | school_submitted | import';
COMMENT ON COLUMN athletes.is_verified IS 'false until scraper cross-check clears school submission';

ALTER TABLE organization_members ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow_all_organization_members" ON organization_members;
CREATE POLICY "allow_all_organization_members" ON organization_members FOR ALL USING (true);

ALTER TABLE nil_budgets ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow_all_nil_budgets" ON nil_budgets;
CREATE POLICY "allow_all_nil_budgets" ON nil_budgets FOR ALL USING (true);

ALTER TABLE nil_scenarios ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow_all_nil_scenarios" ON nil_scenarios;
CREATE POLICY "allow_all_nil_scenarios" ON nil_scenarios FOR ALL USING (true);

ALTER TABLE nil_roster_contracts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow_all_nil_roster_contracts" ON nil_roster_contracts;
CREATE POLICY "allow_all_nil_roster_contracts" ON nil_roster_contracts FOR ALL USING (true);

ALTER TABLE cap_audit_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow_all_cap_audit_log" ON cap_audit_log;
CREATE POLICY "allow_all_cap_audit_log" ON cap_audit_log FOR ALL USING (true);

ALTER TABLE athlete_data_submissions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow_all_athlete_data_submissions" ON athlete_data_submissions;
CREATE POLICY "allow_all_athlete_data_submissions" ON athlete_data_submissions FOR ALL USING (true);

ALTER TABLE athlete_org_overrides ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow_all_athlete_org_overrides" ON athlete_org_overrides;
CREATE POLICY "allow_all_athlete_org_overrides" ON athlete_org_overrides FOR ALL USING (true);

ALTER TABLE athlete_org_gravity_scores ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow_all_athlete_org_gravity_scores" ON athlete_org_gravity_scores;
CREATE POLICY "allow_all_athlete_org_gravity_scores" ON athlete_org_gravity_scores FOR ALL USING (true);

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow_all_organizations" ON organizations;
CREATE POLICY "allow_all_organizations" ON organizations FOR ALL USING (true);
