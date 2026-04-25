-- 011_feed_categories_v2.sql
-- Expand the live feed taxonomy: add ANNOUNCEMENT / BUSINESS / INCIDENT /
-- AWARD / RECRUITING / PERFORMANCE / SCORE / BRAND_DEAL so the "general"
-- feed surfaces things college sports business actually cares about
-- (NIL/brand deals, league announcements, suspensions, big news, etc).
--
-- The migration is idempotent and additive: it widens both CHECK
-- constraints and refines the backfill mapping.  Existing rows keep
-- their current category; only NULL or now-misclassified rows get
-- recomputed.

-- ---------------------------------------------------------------------------
-- 1) athlete_events: widen the CHECK + refine the event_type → category map.
-- ---------------------------------------------------------------------------
ALTER TABLE athlete_events
  DROP CONSTRAINT IF EXISTS athlete_events_category_check;

UPDATE athlete_events
   SET category = CASE
     WHEN UPPER(event_type) LIKE '%NIL%DEAL%'     THEN 'NIL_DEAL'
     WHEN UPPER(event_type) LIKE '%BRAND%DEAL%'   THEN 'NIL_DEAL'
     WHEN UPPER(event_type) LIKE '%ENDORSE%'      THEN 'NIL_DEAL'
     WHEN UPPER(event_type) LIKE '%SPONSOR%'      THEN 'NIL_DEAL'
     WHEN UPPER(event_type) LIKE '%DEAL%'         THEN 'NIL_DEAL'
     WHEN UPPER(event_type) LIKE '%SUSPEN%'       THEN 'INCIDENT'
     WHEN UPPER(event_type) LIKE '%ARREST%'       THEN 'INCIDENT'
     WHEN UPPER(event_type) LIKE '%LEGAL%'        THEN 'INCIDENT'
     WHEN UPPER(event_type) LIKE '%CONTROVERS%'   THEN 'INCIDENT'
     WHEN UPPER(event_type) LIKE '%VIOLATION%'    THEN 'INCIDENT'
     WHEN UPPER(event_type) LIKE '%DECLAR%'       THEN 'ANNOUNCEMENT'
     WHEN UPPER(event_type) LIKE '%ANNOUNC%'      THEN 'ANNOUNCEMENT'
     WHEN UPPER(event_type) LIKE '%COMMIT%'       THEN 'RECRUITING'
     WHEN UPPER(event_type) LIKE '%RECRUIT%'      THEN 'RECRUITING'
     WHEN UPPER(event_type) LIKE '%DRAFT%'        THEN 'ANNOUNCEMENT'
     WHEN UPPER(event_type) LIKE '%AWARD%'        THEN 'AWARD'
     WHEN UPPER(event_type) LIKE '%HONOR%'        THEN 'AWARD'
     WHEN UPPER(event_type) LIKE '%ALL%CONF%'     THEN 'AWARD'
     WHEN UPPER(event_type) LIKE '%GAME%STAT%'    THEN 'PERFORMANCE'
     WHEN UPPER(event_type) LIKE '%PERF%'         THEN 'PERFORMANCE'
     WHEN UPPER(event_type) LIKE '%STAT%'         THEN 'PERFORMANCE'
     WHEN UPPER(event_type) LIKE '%COLLECTIVE%'   THEN 'BUSINESS'
     WHEN UPPER(event_type) LIKE '%CONFERENCE%MOVE%' THEN 'BUSINESS'
     WHEN UPPER(event_type) LIKE '%REVENUE%'      THEN 'BUSINESS'
     WHEN UPPER(event_type) LIKE '%SCORE%'        THEN 'SCORE'
     WHEN UPPER(event_type) LIKE '%RISK%'         THEN 'RISK'
     WHEN UPPER(event_type) LIKE '%INJURY%'       THEN 'INJURY'
     WHEN UPPER(event_type) LIKE '%TRANSFER%'     THEN 'TRANSFER'
     WHEN UPPER(event_type) LIKE '%PORTAL%'       THEN 'TRANSFER'
     WHEN UPPER(event_type) LIKE '%ROSTER%'       THEN 'ROSTER'
     WHEN UPPER(event_type) LIKE '%NEWS%'         THEN 'NEWS'
     WHEN UPPER(event_type) LIKE '%MENTION%'      THEN 'NEWS'
     WHEN UPPER(event_type) LIKE '%FOLLOWER%'     THEN 'SOCIAL'
     WHEN UPPER(event_type) LIKE '%SOCIAL%'       THEN 'SOCIAL'
     WHEN UPPER(event_type) LIKE '%RANK%'         THEN 'RANKING'
     ELSE COALESCE(category, 'OTHER')
   END;

-- Consolidate legacy SCORE_UPDATE -> SCORE so the catalog stays narrow.
UPDATE athlete_events SET category = 'SCORE' WHERE category = 'SCORE_UPDATE';

ALTER TABLE athlete_events
  ADD CONSTRAINT athlete_events_category_check
  CHECK (category IN (
    'NIL_DEAL','TRANSFER','INJURY','NEWS','AWARD','RECRUITING',
    'PERFORMANCE','ANNOUNCEMENT','BUSINESS','INCIDENT',
    'SCORE','ROSTER','SOCIAL','RANKING','RISK','OTHER'
  ));

-- ---------------------------------------------------------------------------
-- 2) team_events: widen the CHECK + refine the event_type → category map.
-- ---------------------------------------------------------------------------
ALTER TABLE team_events
  DROP CONSTRAINT IF EXISTS team_events_category_check;

UPDATE team_events
   SET category = CASE
     WHEN UPPER(event_type) LIKE '%NIL%DEAL%'     THEN 'NIL_DEAL'
     WHEN UPPER(event_type) LIKE '%COLLECTIVE%'   THEN 'BUSINESS'
     WHEN UPPER(event_type) LIKE '%CONFERENCE%'   THEN 'BUSINESS'
     WHEN UPPER(event_type) LIKE '%REVENUE%'      THEN 'BUSINESS'
     WHEN UPPER(event_type) LIKE '%SUSPEN%'       THEN 'INCIDENT'
     WHEN UPPER(event_type) LIKE '%VIOLATION%'    THEN 'INCIDENT'
     WHEN UPPER(event_type) LIKE '%ANNOUNC%'      THEN 'ANNOUNCEMENT'
     WHEN UPPER(event_type) LIKE '%HIRE%'         THEN 'ANNOUNCEMENT'
     WHEN UPPER(event_type) LIKE '%FIRE%'         THEN 'ANNOUNCEMENT'
     WHEN UPPER(event_type) LIKE '%COACH%'        THEN 'ANNOUNCEMENT'
     WHEN UPPER(event_type) LIKE '%RECRUIT%'      THEN 'RECRUITING'
     WHEN UPPER(event_type) LIKE '%COMMIT%'       THEN 'RECRUITING'
     WHEN UPPER(event_type) LIKE '%RANK%'         THEN 'RANKING'
     WHEN UPPER(event_type) LIKE '%NEWS%'         THEN 'NEWS'
     WHEN UPPER(event_type) LIKE '%ROSTER%'       THEN 'ROSTER'
     ELSE COALESCE(category, 'OTHER')
   END;

ALTER TABLE team_events
  ADD CONSTRAINT team_events_category_check
  CHECK (category IN (
    'NIL_DEAL','TRANSFER','INJURY','NEWS','AWARD','RECRUITING',
    'PERFORMANCE','ANNOUNCEMENT','BUSINESS','INCIDENT',
    'SCORE','ROSTER','SOCIAL','RANKING','RISK','OTHER'
  ));
