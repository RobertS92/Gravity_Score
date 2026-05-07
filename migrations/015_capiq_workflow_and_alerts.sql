-- CapIQ workflow permissions, approvals, and alert surfaces.

-- Expand scenario status lifecycle.
ALTER TABLE nil_scenarios DROP CONSTRAINT IF EXISTS nil_scenarios_status_check;
ALTER TABLE nil_scenarios
  ADD CONSTRAINT nil_scenarios_status_check
  CHECK (status IN ('draft', 'approved', 'official', 'promoted'));

-- Optional workflow capability overrides layered on top of role defaults.
CREATE TABLE IF NOT EXISTS capiq_user_permissions (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id       UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id      UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
  sport        TEXT CHECK (sport IS NULL OR sport IN ('CFB', 'NCAAB', 'NCAAW')),
  can_view     BOOLEAN NOT NULL DEFAULT TRUE,
  can_edit     BOOLEAN NOT NULL DEFAULT FALSE,
  can_approve  BOOLEAN NOT NULL DEFAULT FALSE,
  created_by   UUID REFERENCES user_accounts(id),
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (org_id, user_id, sport)
);

CREATE INDEX IF NOT EXISTS idx_capiq_user_permissions_org ON capiq_user_permissions (org_id, sport);

-- Approval event history.
CREATE TABLE IF NOT EXISTS nil_scenario_approval_events (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  scenario_id    UUID NOT NULL REFERENCES nil_scenarios(id) ON DELETE CASCADE,
  org_id         UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  sport          TEXT NOT NULL CHECK (sport IN ('CFB', 'NCAAB', 'NCAAW')),
  action         TEXT NOT NULL CHECK (action IN ('submitted', 'approved', 'promoted', 'rejected', 'reverted')),
  actor_user_id  UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
  notes          TEXT,
  created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scenario_approval_events_scenario ON nil_scenario_approval_events (scenario_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scenario_approval_events_org ON nil_scenario_approval_events (org_id, sport, created_at DESC);

-- Derived cap alerts/events (materialized by API jobs or on-demand generation).
CREATE TABLE IF NOT EXISTS cap_alert_events (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  sport         TEXT NOT NULL CHECK (sport IN ('CFB', 'NCAAB', 'NCAAW')),
  fiscal_year   INT,
  alert_type    TEXT NOT NULL,
  severity      TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
  title         TEXT NOT NULL,
  description   TEXT,
  metric_value  DOUBLE PRECISION,
  threshold     DOUBLE PRECISION,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cap_alert_events_org_sport ON cap_alert_events (org_id, sport, created_at DESC);
