-- Gravity NIL Terminal schema (Supabase / PostgreSQL)
-- Run in SQL editor. Adds social_snapshots + roster upsert unique constraint not in original spec.
-- NOTE: If you already have an `athletes` table from legacy SQLAlchemy models, resolve naming
-- conflicts (table rename or fresh project) before applying.

-- Core athletes table (college specific)
CREATE TABLE IF NOT EXISTS athletes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  sport VARCHAR(10) NOT NULL CHECK (sport IN ('cfb', 'mcbb')),
  school TEXT NOT NULL,
  conference TEXT NOT NULL,
  position TEXT,
  position_group TEXT,
  eligibility_year INT,
  recruiting_stars INT,
  height_inches INT,
  weight_lbs INT,
  hometown TEXT,
  home_state TEXT,
  dma_rank INT,
  jersey_number TEXT,
  photo_url TEXT,
  espn_id TEXT,
  on3_id TEXT,
  sports_ref_id TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (name, school, sport)
);

-- Social snapshots (referenced by scoring / weekly job)
CREATE TABLE IF NOT EXISTS social_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
  instagram_followers BIGINT,
  tiktok_followers BIGINT,
  twitter_followers BIGINT,
  youtube_subscribers BIGINT,
  instagram_engagement_rate NUMERIC,
  tiktok_engagement_rate NUMERIC,
  instagram_verified BOOLEAN,
  twitter_verified BOOLEAN,
  news_mentions_30d INT,
  ig_follower_delta_30d INT,
  news_velocity_30d NUMERIC,
  scraped_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_social_snapshots_athlete ON social_snapshots(athlete_id, scraped_at DESC);

-- Performance snapshots (college stats)
CREATE TABLE IF NOT EXISTS athlete_performance_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE,
  season INT NOT NULL,
  week INT,
  sport VARCHAR(10) NOT NULL,
  position TEXT,
  stats JSONB NOT NULL DEFAULT '{}',
  pff_grade NUMERIC,
  snap_count_pct NUMERIC,
  recruiting_rank INT,
  conference_strength_adj NUMERIC DEFAULT 1.0,
  scraped_at TIMESTAMPTZ DEFAULT NOW()
);

-- Gravity scores (all phases)
CREATE TABLE IF NOT EXISTS athlete_gravity_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE,
  gravity_score NUMERIC NOT NULL,
  brand_score NUMERIC NOT NULL,
  proof_score NUMERIC NOT NULL,
  proximity_score NUMERIC NOT NULL,
  velocity_score NUMERIC NOT NULL,
  risk_score NUMERIC NOT NULL,
  confidence NUMERIC NOT NULL DEFAULT 0.5,
  shap_values JSONB DEFAULT '{}',
  top_factors_up JSONB DEFAULT '[]',
  top_factors_down JSONB DEFAULT '[]',
  model_version TEXT DEFAULT 'v1.0',
  calculated_at TIMESTAMPTZ DEFAULT NOW()
);

-- NIL deals (verified and estimated)
CREATE TABLE IF NOT EXISTS athlete_nil_deals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE,
  source TEXT NOT NULL,
  deal_value NUMERIC,
  deal_type VARCHAR(30) CHECK (deal_type IN (
    'endorsement','appearance','social_post',
    'content','collective','revenue_share','merchandise','other'
  )),
  brand_name TEXT,
  brand_category TEXT,
  deal_date DATE,
  verified BOOLEAN DEFAULT FALSE,
  source_url TEXT,
  csc_status VARCHAR(20) DEFAULT 'unknown' CHECK (csc_status IN (
    'cleared','not_cleared','pending','flagged','unknown'
  )),
  ingested_at TIMESTAMPTZ DEFAULT NOW()
);

-- Deal valuation reports (Phase 1 revenue)
CREATE TABLE IF NOT EXISTS deal_valuation_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  report_uuid TEXT UNIQUE DEFAULT gen_random_uuid()::text,
  athlete_id UUID REFERENCES athletes(id),
  requested_by UUID,
  proposed_deal_value NUMERIC NOT NULL,
  deal_type TEXT NOT NULL,
  deal_description TEXT,
  performance_obligations TEXT,
  brand_name TEXT,
  brand_category TEXT,
  deal_duration_days INT,
  gravity_score_at_report NUMERIC,
  comparable_athletes JSONB DEFAULT '[]',
  compensation_range_low NUMERIC,
  compensation_range_high NUMERIC,
  csc_assessment TEXT,
  csc_likelihood VARCHAR(20),
  pdf_url TEXT,
  status VARCHAR(20) DEFAULT 'pending',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Comparables cache
CREATE TABLE IF NOT EXISTS comparable_sets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE,
  comparable_athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE,
  similarity_score NUMERIC NOT NULL,
  matching_dimensions JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(subject_athlete_id, comparable_athlete_id)
);

-- Programs (schools)
CREATE TABLE IF NOT EXISTS programs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school TEXT NOT NULL,
  conference TEXT NOT NULL,
  sport VARCHAR(10) NOT NULL,
  dma_rank INT,
  dma_size BIGINT,
  annual_tv_appearances INT DEFAULT 0,
  collective_budget_usd BIGINT DEFAULT 0,
  revenue_share_cap_usd BIGINT DEFAULT 20500000,
  nil_environment_score NUMERIC,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(school, sport)
);

-- User accounts
CREATE TABLE IF NOT EXISTS user_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  role VARCHAR(20) NOT NULL CHECK (role IN ('agent','attorney','brand','insurer','admin')),
  organization TEXT,
  stripe_customer_id TEXT,
  subscription_tier VARCHAR(20) DEFAULT 'free',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Watchlists
CREATE TABLE IF NOT EXISTS watchlists (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES user_accounts(id) ON DELETE CASCADE,
  athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE,
  alert_threshold NUMERIC DEFAULT 5.0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, athlete_id)
);

-- Score alerts
CREATE TABLE IF NOT EXISTS score_alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES user_accounts(id) ON DELETE CASCADE,
  athlete_id UUID REFERENCES athletes(id) ON DELETE CASCADE,
  previous_score NUMERIC,
  new_score NUMERIC,
  delta NUMERIC,
  trigger_reason TEXT,
  read BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Query history (for agentic terminal)
CREATE TABLE IF NOT EXISTS query_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES user_accounts(id) ON DELETE CASCADE,
  query_text TEXT NOT NULL,
  query_type VARCHAR(30),
  result_summary TEXT,
  athlete_ids_returned JSONB DEFAULT '[]',
  execution_time_ms INT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_athletes_sport_conference ON athletes(sport, conference);
CREATE INDEX IF NOT EXISTS idx_athletes_school ON athletes(school);
CREATE INDEX IF NOT EXISTS idx_gravity_scores_athlete ON athlete_gravity_scores(athlete_id);
CREATE INDEX IF NOT EXISTS idx_gravity_scores_calculated ON athlete_gravity_scores(calculated_at DESC);
CREATE INDEX IF NOT EXISTS idx_nil_deals_athlete ON athlete_nil_deals(athlete_id);
CREATE INDEX IF NOT EXISTS idx_comparables_subject ON comparable_sets(subject_athlete_id);
CREATE INDEX IF NOT EXISTS idx_watchlists_user ON watchlists(user_id);
CREATE INDEX IF NOT EXISTS idx_score_alerts_user ON score_alerts(user_id, read);
