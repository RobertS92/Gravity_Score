-- CSC tier rollout controls for phased migration (v1 -> v2).

CREATE TABLE IF NOT EXISTS csc_tier_rollout (
  id            SERIAL PRIMARY KEY,
  current_phase TEXT NOT NULL CHECK (current_phase IN ('phase1', 'phase2', 'phase3', 'phase4')),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS csc_tier_account_overrides (
  user_id            UUID PRIMARY KEY REFERENCES user_accounts(id) ON DELETE CASCADE,
  force_tier_version TEXT NOT NULL CHECK (force_tier_version IN ('tier_v1', 'tier_v2')),
  updated_at         TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO csc_tier_rollout (current_phase)
SELECT 'phase1'
WHERE NOT EXISTS (SELECT 1 FROM csc_tier_rollout);
