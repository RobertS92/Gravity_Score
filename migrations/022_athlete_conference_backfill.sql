-- Backfill athletes.conference from team_conferences and create
-- data_quality_issues table for ops review of unmapped athletes.
--
-- This migration is idempotent: re-running it only updates rows whose
-- stored conference disagrees with the current authoritative mapping
-- (or whose conference is the placeholder string "Conference").

-- =========================================================================
-- 1) data_quality_issues — append-only log of operational gaps.
-- =========================================================================

CREATE TABLE IF NOT EXISTS data_quality_issues (
  id         BIGSERIAL PRIMARY KEY,
  kind       TEXT NOT NULL,
  athlete_id UUID,
  payload    JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_data_quality_issues_kind_created
  ON data_quality_issues (kind, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_data_quality_issues_athlete
  ON data_quality_issues (athlete_id);

-- =========================================================================
-- 2) Backfill athletes.conference from team_conferences via school name.
--    Match is case/whitespace insensitive; only rewrite when the table has
--    an authoritative current row.
-- =========================================================================

WITH current_mapping AS (
  SELECT DISTINCT ON (UPPER(TRIM(tc.team_id)), tc.sport)
    UPPER(TRIM(tc.team_id)) AS canonical_team,
    tc.sport                AS sport,
    tc.conference           AS conference
  FROM team_conferences tc
  WHERE tc.effective_from <= CURRENT_DATE
    AND (tc.effective_to IS NULL OR tc.effective_to >= CURRENT_DATE)
  ORDER BY UPPER(TRIM(tc.team_id)), tc.sport, tc.effective_from DESC
)
UPDATE athletes a
   SET conference = cm.conference
  FROM current_mapping cm
 WHERE cm.canonical_team = UPPER(TRIM(a.school))
   AND cm.sport          = a.sport
   AND (
        a.conference IS NULL
     OR TRIM(a.conference) = ''
     OR LOWER(TRIM(a.conference)) = 'conference'
     OR a.conference <> cm.conference
   );

-- =========================================================================
-- 3) Record athletes whose team has no current conference mapping.
-- =========================================================================

INSERT INTO data_quality_issues (kind, athlete_id, payload)
SELECT
  'conference_not_mapped',
  a.id,
  jsonb_build_object(
    'school',     a.school,
    'sport',      a.sport,
    'conference', a.conference,
    'as_of',      CURRENT_DATE
  )
FROM athletes a
WHERE NOT EXISTS (
        SELECT 1
        FROM team_conferences tc
        WHERE UPPER(TRIM(tc.team_id)) = UPPER(TRIM(a.school))
          AND tc.sport = a.sport
          AND tc.effective_from <= CURRENT_DATE
          AND (tc.effective_to IS NULL OR tc.effective_to >= CURRENT_DATE)
      )
  AND NOT EXISTS (
        SELECT 1
        FROM data_quality_issues d
        WHERE d.athlete_id = a.id
          AND d.kind = 'conference_not_mapped'
          AND d.created_at > NOW() - INTERVAL '7 days'
      );
