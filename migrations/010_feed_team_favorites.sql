-- 010_feed_team_favorites.sql
-- Live feed v2: team favorites + a categorized cross-source feed.
--
-- Design choice: rather than introduce a new "feed_items" table, we keep
-- athlete-level events in the existing `athlete_events` table (already
-- 17k+ rows) and add a normalized `category` column. Team-level news
-- gets its own `team_events` table. The /v1/feed endpoint UNIONs the two.
--
-- This migration is idempotent and additive only; existing rows are
-- preserved and backfilled.

-- ---------------------------------------------------------------------------
-- 1) team_favorites: each row is "user U follows team T".
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS team_favorites (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
  team_id     UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, team_id)
);

CREATE INDEX IF NOT EXISTS idx_team_favorites_user ON team_favorites (user_id);
CREATE INDEX IF NOT EXISTS idx_team_favorites_team ON team_favorites (team_id);


-- ---------------------------------------------------------------------------
-- 2) athlete_events: add a normalized `category` column so the feed can
--    filter without depending on raw scraper event_type strings.
-- ---------------------------------------------------------------------------
ALTER TABLE athlete_events
  ADD COLUMN IF NOT EXISTS category TEXT;

-- Backfill from existing event_type values. Mapping is intentionally
-- coarse — this is the *display* category, not the raw type.
UPDATE athlete_events
   SET category = CASE
     WHEN UPPER(event_type) LIKE '%NIL%DEAL%'   THEN 'NIL_DEAL'
     WHEN UPPER(event_type) LIKE '%DEAL%'       THEN 'NIL_DEAL'
     WHEN UPPER(event_type) LIKE '%SCORE%'      THEN 'SCORE_UPDATE'
     WHEN UPPER(event_type) LIKE '%RISK%'       THEN 'RISK'
     WHEN UPPER(event_type) LIKE '%INJURY%'     THEN 'INJURY'
     WHEN UPPER(event_type) LIKE '%TRANSFER%'   THEN 'TRANSFER'
     WHEN UPPER(event_type) LIKE '%ROSTER%'     THEN 'ROSTER'
     WHEN UPPER(event_type) LIKE '%NEWS%'       THEN 'NEWS'
     WHEN UPPER(event_type) LIKE '%FOLLOWER%'   THEN 'SOCIAL'
     WHEN UPPER(event_type) LIKE '%SOCIAL%'     THEN 'SOCIAL'
     WHEN UPPER(event_type) LIKE '%RANK%'       THEN 'RANKING'
     ELSE 'OTHER'
   END
 WHERE category IS NULL;

-- Add the CHECK only if it doesn't already exist (idempotent).
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'athlete_events_category_check'
  ) THEN
    ALTER TABLE athlete_events
      ADD CONSTRAINT athlete_events_category_check
      CHECK (category IN (
        'NIL_DEAL','SCORE_UPDATE','RISK','INJURY','TRANSFER',
        'ROSTER','NEWS','SOCIAL','RANKING','OTHER'
      ));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_athlete_events_category_time
  ON athlete_events (category, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_athlete_events_athlete_time
  ON athlete_events (athlete_id, occurred_at DESC);


-- ---------------------------------------------------------------------------
-- 3) team_events: news / rankings / recruiting items at the team level.
--    Note: a small `team_events` table predates this migration (id, team_id,
--    event_type, title, metadata, occurred_at, detected_at). We extend it
--    additively with the columns the feed needs.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS team_events (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  team_id       UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  event_type    TEXT NOT NULL DEFAULT 'OTHER',
  title         TEXT NOT NULL,
  metadata      JSONB DEFAULT '{}'::jsonb,
  occurred_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  detected_at   TIMESTAMPTZ
);

ALTER TABLE team_events
  ADD COLUMN IF NOT EXISTS category    TEXT,
  ADD COLUMN IF NOT EXISTS body        TEXT,
  ADD COLUMN IF NOT EXISTS source      TEXT,
  ADD COLUMN IF NOT EXISTS source_url  TEXT,
  ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS dedupe_hash TEXT;

UPDATE team_events
   SET category = CASE
     WHEN UPPER(event_type) LIKE '%NEWS%'        THEN 'NEWS'
     WHEN UPPER(event_type) LIKE '%RANK%'        THEN 'RANKING'
     WHEN UPPER(event_type) LIKE '%RECRUIT%'     THEN 'RECRUITING'
     WHEN UPPER(event_type) LIKE '%ROSTER%'      THEN 'ROSTER'
     WHEN UPPER(event_type) LIKE '%DEAL%'        THEN 'NIL_DEAL'
     ELSE 'OTHER'
   END
 WHERE category IS NULL;

ALTER TABLE team_events
  ALTER COLUMN category SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'team_events_category_check'
  ) THEN
    ALTER TABLE team_events
      ADD CONSTRAINT team_events_category_check
      CHECK (category IN (
        'NEWS','RANKING','RECRUITING','ROSTER','NIL_DEAL','OTHER'
      ));
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'team_events_dedupe_hash_key'
  ) THEN
    ALTER TABLE team_events
      ADD CONSTRAINT team_events_dedupe_hash_key UNIQUE (dedupe_hash);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_team_events_team_time
  ON team_events (team_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_team_events_category_time
  ON team_events (category, occurred_at DESC);
