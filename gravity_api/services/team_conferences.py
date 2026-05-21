"""Team -> conference + conference-tier lookup with effective dates.

The `team_conferences` table is the source of truth for conference attribution
in CSC report cohorts and elsewhere. Conference realignment is frequent enough
that hardcoding `athletes.conference` rots; this service guarantees a valid
mapping (or surfaces a hard error so the caller can return HTTP 422).

`team_id` is stored as canonical TEXT; lookups are case/whitespace insensitive.
For athletes joining via school name (the in-repo convention), pass the school
name (e.g. "Texas") as `team_id`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Literal, Optional

import asyncpg

logger = logging.getLogger(__name__)


ConferenceTier = Literal["power_5", "group_of_5", "fcs", "mid_major", "other"]


class ConferenceNotMappedError(ValueError):
    """Raised when no conference mapping exists for (team_id, sport, as_of)."""

    def __init__(self, team_id: str, sport: str, as_of: date) -> None:
        self.team_id = team_id
        self.sport = sport
        self.as_of = as_of
        super().__init__(
            f"No conference mapping for team_id={team_id!r} sport={sport!r} as_of={as_of.isoformat()}"
        )


@dataclass(frozen=True)
class ConferenceLookup:
    conference: str
    conference_tier: ConferenceTier


_SPORT_ALIASES: dict[str, str] = {
    "cfb": "cfb",
    "ncaaf": "cfb",
    "fbs": "cfb",
    "football": "cfb",
    "ncaab": "ncaab",
    "mcbb": "ncaab",
    "ncaab_mens": "ncaab",
    "basketball": "ncaab",
}


def _canonical_sport(sport: str) -> str:
    key = (sport or "").strip().lower()
    return _SPORT_ALIASES.get(key, key)


async def get_conference(
    db: asyncpg.Connection,
    team_id: str,
    sport: str,
    *,
    as_of: Optional[date] = None,
) -> ConferenceLookup:
    """Return canonical (conference, conference_tier) for a team at a point in time.

    Raises ConferenceNotMappedError when no row covers `as_of`.
    """
    if not team_id or not str(team_id).strip():
        raise ConferenceNotMappedError(str(team_id), sport, as_of or date.today())
    canonical = _canonical_sport(sport)
    if canonical not in ("cfb", "ncaab"):
        raise ConferenceNotMappedError(team_id, sport, as_of or date.today())
    effective = as_of or date.today()
    row = await db.fetchrow(
        """SELECT conference, conference_tier
           FROM team_conferences
           WHERE UPPER(TRIM(team_id)) = UPPER(TRIM($1))
             AND sport = $2
             AND effective_from <= $3
             AND (effective_to IS NULL OR effective_to >= $3)
           ORDER BY effective_from DESC
           LIMIT 1""",
        team_id,
        canonical,
        effective,
    )
    if not row:
        raise ConferenceNotMappedError(team_id, canonical, effective)
    return ConferenceLookup(
        conference=str(row["conference"]),
        conference_tier=str(row["conference_tier"]),  # type: ignore[arg-type]
    )


async def try_get_conference(
    db: asyncpg.Connection,
    team_id: str,
    sport: str,
    *,
    as_of: Optional[date] = None,
) -> Optional[ConferenceLookup]:
    """Non-throwing variant for surfaces where a missing mapping is non-fatal
    (search, backfill jobs). Returns None on miss or on any DB-level error
    (e.g. the migration has not yet been applied in this environment)."""
    try:
        return await get_conference(db, team_id, sport, as_of=as_of)
    except ConferenceNotMappedError:
        return None
    except asyncpg.PostgresError as exc:
        # team_conferences table may not exist yet in a given env (migration
        # 021 not yet applied). Surface as a soft miss; callers will fall
        # back to the athlete row's stored conference where present.
        logger.warning(
            "team_conferences lookup failed (team_id=%s sport=%s): %s",
            team_id,
            sport,
            exc,
        )
        return None
    except Exception as exc:  # noqa: BLE001 — never crash a report on lookup
        logger.exception(
            "Unexpected error in team_conferences lookup (team_id=%s sport=%s): %s",
            team_id,
            sport,
            exc,
        )
        return None


async def refresh_athlete_conference_backfill(
    db: asyncpg.Connection,
) -> dict:
    """Re-apply the conference backfill that migration 022 performs.

    Returns a dict with counts so the caller (jobs/CLI) can log them.
    Safe to run nightly; only rewrites rows that disagree with the
    current authoritative mapping or hold the placeholder "Conference".
    """
    updated = await db.fetchval(
        """WITH current_mapping AS (
              SELECT DISTINCT ON (UPPER(TRIM(tc.team_id)), tc.sport)
                UPPER(TRIM(tc.team_id)) AS canonical_team,
                tc.sport                AS sport,
                tc.conference           AS conference
              FROM team_conferences tc
              WHERE tc.effective_from <= CURRENT_DATE
                AND (tc.effective_to IS NULL OR tc.effective_to >= CURRENT_DATE)
              ORDER BY UPPER(TRIM(tc.team_id)), tc.sport, tc.effective_from DESC
            ),
            updated AS (
              UPDATE athletes a
                 SET conference = cm.conference
                FROM current_mapping cm
               WHERE cm.canonical_team = UPPER(TRIM(a.school))
                 AND cm.sport = a.sport
                 AND (
                       a.conference IS NULL
                    OR TRIM(a.conference) = ''
                    OR LOWER(TRIM(a.conference)) = 'conference'
                    OR a.conference <> cm.conference
                 )
              RETURNING a.id
            )
            SELECT COUNT(*)::int FROM updated"""
    )
    issued = await db.fetchval(
        """INSERT INTO data_quality_issues (kind, athlete_id, payload)
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
                   SELECT 1 FROM team_conferences tc
                   WHERE UPPER(TRIM(tc.team_id)) = UPPER(TRIM(a.school))
                     AND tc.sport = a.sport
                     AND tc.effective_from <= CURRENT_DATE
                     AND (tc.effective_to IS NULL OR tc.effective_to >= CURRENT_DATE)
                 )
             AND NOT EXISTS (
                   SELECT 1 FROM data_quality_issues d
                   WHERE d.athlete_id = a.id
                     AND d.kind = 'conference_not_mapped'
                     AND d.created_at > NOW() - INTERVAL '7 days'
                 )
           RETURNING (SELECT COUNT(*)::int FROM data_quality_issues)"""
    )
    return {
        "athletes_updated": int(updated or 0),
        "issues_logged": int(issued or 0),
    }


async def list_unmapped_athletes(
    db: asyncpg.Connection, sport: Optional[str] = None
) -> list[dict]:
    """Return athletes whose school has no team_conferences mapping.

    Used by CI invariants and by the data-quality nightly hook.
    """
    if sport:
        canonical = _canonical_sport(sport)
        rows = await db.fetch(
            """SELECT a.id, a.name, a.school, a.sport
               FROM athletes a
               WHERE a.sport = $1
                 AND NOT EXISTS (
                   SELECT 1 FROM team_conferences tc
                   WHERE UPPER(TRIM(tc.team_id)) = UPPER(TRIM(a.school))
                     AND tc.sport = $1
                 )""",
            canonical,
        )
    else:
        rows = await db.fetch(
            """SELECT a.id, a.name, a.school, a.sport
               FROM athletes a
               WHERE NOT EXISTS (
                   SELECT 1 FROM team_conferences tc
                   WHERE UPPER(TRIM(tc.team_id)) = UPPER(TRIM(a.school))
                     AND tc.sport = a.sport
                 )"""
        )
    return [dict(r) for r in rows]
