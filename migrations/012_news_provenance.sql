-- 012_news_provenance.sql
-- Production-grade accuracy stack for the live feed.
--
-- Goals:
--   1. Every news item must have a real, attributable source (URL + name +
--      tier).  No more `event_source = 'unknown'`.
--   2. Each item carries a verification level so the UI can show users how
--      much to trust it.
--   3. A claim_hash makes duplicate-claim-from-different-source detection
--      cheap, which is how we promote SINGLE_SOURCE -> MULTI_SOURCE.
--   4. Hallucinated extractions get logged, never persisted.
--   5. Legacy un-sourced events are purged (user explicitly chose this).
--
-- Idempotent and additive (except for the purge step which is intentional).

-- ---------------------------------------------------------------------------
-- 1) news_sources: the allowlist + tier table.  Tier 1 = official / wire,
--    Tier 2 = major outlet, Tier 3 = blog/aggregator, Tier 4 = blocked.
--    Only enabled sources with tier <= 3 may write events.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS news_sources (
  domain        TEXT PRIMARY KEY,
  display_name  TEXT NOT NULL,
  tier          SMALLINT NOT NULL CHECK (tier BETWEEN 1 AND 4),
  enabled       BOOLEAN NOT NULL DEFAULT TRUE,
  notes         TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed the allowlist with the publishers we trust today.  Re-running this
-- migration leaves existing tier/enabled choices intact (ON CONFLICT DO
-- NOTHING) so admins can hand-edit a row without it being clobbered.
INSERT INTO news_sources (domain, display_name, tier, notes) VALUES
  -- Tier 1: official / wire / governing body
  ('apnews.com',          'Associated Press',     1, 'Wire service'),
  ('reuters.com',          'Reuters',              1, 'Wire service'),
  ('ncaa.com',             'NCAA',                 1, 'Governing body'),
  ('ncaa.org',             'NCAA',                 1, 'Governing body'),
  -- Tier 2: major outlets with editorial standards
  ('espn.com',             'ESPN',                 2, NULL),
  ('cbssports.com',        'CBS Sports',           2, NULL),
  ('foxsports.com',        'FOX Sports',           2, NULL),
  ('si.com',               'Sports Illustrated',   2, NULL),
  ('theathletic.com',      'The Athletic',         2, NULL),
  ('yahoo.com',            'Yahoo Sports',         2, NULL),
  ('sports.yahoo.com',     'Yahoo Sports',         2, NULL),
  ('nytimes.com',          'New York Times',       2, NULL),
  ('washingtonpost.com',   'Washington Post',      2, NULL),
  ('on3.com',              'On3',                  2, 'NIL & recruiting'),
  ('247sports.com',        '247Sports',            2, 'Recruiting'),
  ('rivals.com',           'Rivals',               2, 'Recruiting'),
  ('bleacherreport.com',   'Bleacher Report',      2, NULL),
  ('opendorse.com',        'Opendorse',            2, 'NIL marketplace blog'),
  ('businessofcollegesports.com', 'Business of College Sports', 2, 'B2B trade'),
  ('frontofficesports.com','Front Office Sports',  2, 'B2B trade'),
  ('sportico.com',         'Sportico',             2, 'B2B trade'),
  ('sportsbusinessjournal.com','Sports Business Journal', 2, 'B2B trade'),
  -- Tier 3: aggregators / blogs / fan sites (still allowed but flagged)
  ('saturdaydownsouth.com','Saturday Down South',  3, NULL),
  ('on3media.com',         'On3 Network blog',     3, NULL),
  ('athlonsports.com',     'Athlon Sports',        3, NULL)
ON CONFLICT (domain) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_news_sources_tier ON news_sources (tier, enabled);


-- ---------------------------------------------------------------------------
-- 2) athlete_events: add the provenance + verification columns.
-- ---------------------------------------------------------------------------
ALTER TABLE athlete_events
  ADD COLUMN IF NOT EXISTS source_name      TEXT,
  ADD COLUMN IF NOT EXISTS source_domain    TEXT,
  ADD COLUMN IF NOT EXISTS source_url       TEXT,
  ADD COLUMN IF NOT EXISTS source_url_hash  TEXT,
  ADD COLUMN IF NOT EXISTS source_tier      SMALLINT,
  ADD COLUMN IF NOT EXISTS published_at     TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS scraper_run_id   UUID,
  ADD COLUMN IF NOT EXISTS verification     TEXT NOT NULL DEFAULT 'UNVERIFIED',
  ADD COLUMN IF NOT EXISTS confidence_score NUMERIC(4,3),
  ADD COLUMN IF NOT EXISTS claim_hash       TEXT,
  ADD COLUMN IF NOT EXISTS exact_quote      TEXT,
  ADD COLUMN IF NOT EXISTS correction_note  TEXT,
  ADD COLUMN IF NOT EXISTS retracted_at     TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS retracted_reason TEXT;

ALTER TABLE athlete_events
  DROP CONSTRAINT IF EXISTS athlete_events_verification_check;
ALTER TABLE athlete_events
  ADD CONSTRAINT athlete_events_verification_check
  CHECK (verification IN ('OFFICIAL','MULTI_SOURCE','SINGLE_SOURCE','LOW_CONFIDENCE','UNVERIFIED'));

ALTER TABLE athlete_events
  DROP CONSTRAINT IF EXISTS athlete_events_source_tier_check;
ALTER TABLE athlete_events
  ADD CONSTRAINT athlete_events_source_tier_check
  CHECK (source_tier IS NULL OR source_tier BETWEEN 1 AND 4);

CREATE INDEX IF NOT EXISTS idx_athlete_events_claim_hash
  ON athlete_events (claim_hash) WHERE claim_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_athlete_events_url_hash
  ON athlete_events (source_url_hash) WHERE source_url_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_athlete_events_verif_time
  ON athlete_events (verification, occurred_at DESC);


-- ---------------------------------------------------------------------------
-- 3) team_events: same provenance/verification columns.
-- ---------------------------------------------------------------------------
ALTER TABLE team_events
  ADD COLUMN IF NOT EXISTS source_name      TEXT,
  ADD COLUMN IF NOT EXISTS source_domain    TEXT,
  ADD COLUMN IF NOT EXISTS source_url_hash  TEXT,
  ADD COLUMN IF NOT EXISTS source_tier      SMALLINT,
  ADD COLUMN IF NOT EXISTS published_at     TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS scraper_run_id   UUID,
  ADD COLUMN IF NOT EXISTS verification     TEXT NOT NULL DEFAULT 'UNVERIFIED',
  ADD COLUMN IF NOT EXISTS confidence_score NUMERIC(4,3),
  ADD COLUMN IF NOT EXISTS claim_hash       TEXT,
  ADD COLUMN IF NOT EXISTS exact_quote      TEXT,
  ADD COLUMN IF NOT EXISTS correction_note  TEXT,
  ADD COLUMN IF NOT EXISTS retracted_at     TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS retracted_reason TEXT;

ALTER TABLE team_events
  DROP CONSTRAINT IF EXISTS team_events_verification_check;
ALTER TABLE team_events
  ADD CONSTRAINT team_events_verification_check
  CHECK (verification IN ('OFFICIAL','MULTI_SOURCE','SINGLE_SOURCE','LOW_CONFIDENCE','UNVERIFIED'));

ALTER TABLE team_events
  DROP CONSTRAINT IF EXISTS team_events_source_tier_check;
ALTER TABLE team_events
  ADD CONSTRAINT team_events_source_tier_check
  CHECK (source_tier IS NULL OR source_tier BETWEEN 1 AND 4);

CREATE INDEX IF NOT EXISTS idx_team_events_claim_hash
  ON team_events (claim_hash) WHERE claim_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_team_events_verif_time
  ON team_events (verification, occurred_at DESC);


-- ---------------------------------------------------------------------------
-- 4) athlete_nil_deals: add provenance columns matching the events tables
--    so deals get the same trust badge.
-- ---------------------------------------------------------------------------
ALTER TABLE athlete_nil_deals
  ADD COLUMN IF NOT EXISTS source_domain    TEXT,
  ADD COLUMN IF NOT EXISTS source_tier      SMALLINT,
  ADD COLUMN IF NOT EXISTS source_url_hash  TEXT,
  ADD COLUMN IF NOT EXISTS verification     TEXT NOT NULL DEFAULT 'UNVERIFIED',
  ADD COLUMN IF NOT EXISTS confidence_score NUMERIC(4,3),
  ADD COLUMN IF NOT EXISTS claim_hash       TEXT,
  ADD COLUMN IF NOT EXISTS exact_quote      TEXT,
  ADD COLUMN IF NOT EXISTS scraper_run_id   UUID,
  ADD COLUMN IF NOT EXISTS retracted_at     TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS retracted_reason TEXT;

ALTER TABLE athlete_nil_deals
  DROP CONSTRAINT IF EXISTS athlete_nil_deals_verification_check;
ALTER TABLE athlete_nil_deals
  ADD CONSTRAINT athlete_nil_deals_verification_check
  CHECK (verification IN ('OFFICIAL','MULTI_SOURCE','SINGLE_SOURCE','LOW_CONFIDENCE','UNVERIFIED'));

CREATE INDEX IF NOT EXISTS idx_nil_deals_claim_hash
  ON athlete_nil_deals (claim_hash) WHERE claim_hash IS NOT NULL;


-- ---------------------------------------------------------------------------
-- 5) extraction_rejections: every claim that fails the LLM fact-check or
--    source-allowlist gate lands here so we have an audit trail.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS extraction_rejections (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id        UUID,
  team_id           UUID,
  attempted_category TEXT,
  attempted_title   TEXT,
  attempted_claim   TEXT,
  source_domain     TEXT,
  source_url        TEXT,
  reason            TEXT NOT NULL,
  llm_response      JSONB,
  scraper_run_id    UUID,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_extraction_rejections_recent
  ON extraction_rejections (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_extraction_rejections_reason
  ON extraction_rejections (reason, created_at DESC);


-- ---------------------------------------------------------------------------
-- 6) PURGE: user explicitly chose to drop the 17.8k legacy un-sourced events
--    so the feed starts from a clean trust baseline.  Anything with a real
--    source/url/tier is kept; everything else (which today is all of them)
--    goes.  athlete_nil_deals are kept because they were manually seeded.
-- ---------------------------------------------------------------------------
DELETE FROM athlete_events
 WHERE source_url IS NULL
    OR source_url = ''
    OR source_name IS NULL
    OR source_name = ''
    OR source_tier IS NULL;

DELETE FROM team_events
 WHERE source_url IS NULL
    OR source_name IS NULL
    OR source_tier IS NULL;
