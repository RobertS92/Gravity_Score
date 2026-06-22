-- Scraper registry and per-run observability for micro-scrapers.
-- Source of truth manifest lives in gravity_api/scraper_registry/ (Python).
-- gravity-scrapers syncs rows via POST /v1/scraper/registry/sync.

CREATE TABLE IF NOT EXISTS scraper_registry (
  scraper_key TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  sport TEXT NOT NULL,
  league_tier TEXT NOT NULL CHECK (league_tier IN ('college', 'pro')),
  dimension TEXT NOT NULL CHECK (
    dimension IN ('identity', 'brand', 'proof', 'proximity', 'velocity', 'risk', 'achievements')
  ),
  source TEXT NOT NULL,
  source_type TEXT NOT NULL CHECK (
    source_type IN ('official', 'licensed', 'public_api', 'scrape', 'manual', 'derived')
  ),
  description TEXT NOT NULL DEFAULT '',
  feature_keys JSONB NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'planned' CHECK (
    status IN ('active', 'legacy', 'stub', 'planned')
  ),
  terminal_visible BOOLEAN NOT NULL DEFAULT TRUE,
  required_for_scoring BOOLEAN NOT NULL DEFAULT FALSE,
  sla_days INTEGER NOT NULL DEFAULT 7 CHECK (sla_days > 0),
  default_confidence NUMERIC NOT NULL DEFAULT 0.75 CHECK (
    default_confidence >= 0 AND default_confidence <= 1
  ),
  circuit_breaker_source TEXT,
  priority INTEGER NOT NULL DEFAULT 3,
  metadata JSONB NOT NULL DEFAULT '{}',
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scraper_registry_sport ON scraper_registry(sport);
CREATE INDEX IF NOT EXISTS idx_scraper_registry_tier ON scraper_registry(league_tier);
CREATE INDEX IF NOT EXISTS idx_scraper_registry_dimension ON scraper_registry(dimension);
CREATE INDEX IF NOT EXISTS idx_scraper_registry_status ON scraper_registry(status);

CREATE TABLE IF NOT EXISTS scraper_run_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  scraper_key TEXT NOT NULL REFERENCES scraper_registry(scraper_key),
  athlete_id UUID REFERENCES athletes(id) ON DELETE SET NULL,
  job_id UUID,
  sport TEXT,
  status TEXT NOT NULL CHECK (status IN ('success', 'partial', 'failed', 'skipped')),
  fields_written JSONB NOT NULL DEFAULT '[]',
  fields_failed JSONB NOT NULL DEFAULT '[]',
  error_message TEXT,
  duration_ms INTEGER,
  observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_scraper_run_results_key_time
  ON scraper_run_results(scraper_key, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_scraper_run_results_athlete
  ON scraper_run_results(athlete_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_scraper_run_results_status
  ON scraper_run_results(status, observed_at DESC);

COMMENT ON TABLE scraper_registry IS 'Canonical micro-scraper manifest; synced from gravity_api/scraper_registry';
COMMENT ON TABLE scraper_run_results IS 'Per-athlete per-scraper run outcomes for observability';
