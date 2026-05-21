-- CSC v3 report rollout control table.
--
-- Mirrors the csc_tier_rollout pattern in migration 020 so ops can move
-- between phases independently of tier methodology rollout:
--   phase1 — dual write v2/v3, UI still shows v2 by default (default).
--   phase2 — v3 default for new reports; per-account overrides allowed.
--   phase3 — v3 only for new reports.
--   phase4 — v2 deprecated.
--
-- Existing persisted reports are NEVER re-rendered. See
-- migrations/009_reports_durability.sql for the immutability contract
-- enforced on deal_valuation_reports.

CREATE TABLE IF NOT EXISTS csc_report_rollout (
  id            SERIAL PRIMARY KEY,
  current_phase TEXT NOT NULL CHECK (current_phase IN ('phase1', 'phase2', 'phase3', 'phase4')),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS csc_report_account_overrides (
  user_id              UUID PRIMARY KEY REFERENCES user_accounts(id) ON DELETE CASCADE,
  force_report_version TEXT NOT NULL CHECK (force_report_version IN ('v2', 'v3')),
  updated_at           TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO csc_report_rollout (current_phase)
SELECT 'phase1'
WHERE NOT EXISTS (SELECT 1 FROM csc_report_rollout);
