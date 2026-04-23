-- Onboarding & dashboard personalization on user_accounts

ALTER TABLE user_accounts
  ADD COLUMN IF NOT EXISTS org_type TEXT,
  ADD COLUMN IF NOT EXISTS sport_preferences TEXT[] DEFAULT ARRAY['CFB']::text[],
  ADD COLUMN IF NOT EXISTS org_name TEXT,
  ADD COLUMN IF NOT EXISTS team_or_athlete_seed TEXT,
  ADD COLUMN IF NOT EXISTS onboarding_completed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS default_dashboard_tab TEXT,
  ADD COLUMN IF NOT EXISTS athletes_default_sort TEXT,
  ADD COLUMN IF NOT EXISTS password_hash TEXT,
  ADD COLUMN IF NOT EXISTS display_name TEXT,
  ADD COLUMN IF NOT EXISTS onboarding_goal TEXT;

ALTER TABLE user_accounts DROP CONSTRAINT IF EXISTS user_accounts_org_type_check;
ALTER TABLE user_accounts ADD CONSTRAINT user_accounts_org_type_check CHECK (
  org_type IS NULL OR org_type IN (
    'school', 'nil_collective', 'brand_agency', 'law_firm_agent', 'insurance_finance', 'media_research'
  )
);

ALTER TABLE user_accounts DROP CONSTRAINT IF EXISTS user_accounts_sport_preferences_check;
ALTER TABLE user_accounts ADD CONSTRAINT user_accounts_sport_preferences_check CHECK (
  sport_preferences IS NULL
  OR (
    sport_preferences <@ ARRAY['CFB', 'NCAAB', 'NCAAW']::text[]
    AND cardinality(sport_preferences) >= 1
  )
);

ALTER TABLE user_accounts DROP CONSTRAINT IF EXISTS user_accounts_default_dashboard_tab_check;
ALTER TABLE user_accounts ADD CONSTRAINT user_accounts_default_dashboard_tab_check CHECK (
  default_dashboard_tab IS NULL
  OR default_dashboard_tab IN ('roster', 'market', 'athletes', 'deals')
);

ALTER TABLE user_accounts DROP CONSTRAINT IF EXISTS user_accounts_athletes_default_sort_check;
ALTER TABLE user_accounts ADD CONSTRAINT user_accounts_athletes_default_sort_check CHECK (
  athletes_default_sort IS NULL OR athletes_default_sort IN ('gravity_desc', 'risk_desc')
);

COMMENT ON COLUMN user_accounts.onboarding_completed_at IS 'NULL until POST /v1/auth/onboarding completes';
COMMENT ON COLUMN user_accounts.athletes_default_sort IS 'Client hint for Athletes tab: brand vs risk sort';
