"""Resolve `teams.id` for school + sport (favorites / school index).

School Index rows come from `programs`, while favorites require a real
`teams.id` UUID. Program gravity scores may be keyed by `programs.id` and
fail the `team_gravity_scores` → `teams` join even when a catalog team
exists for the same school/sport. This module is the shared lookup used
to recover that mapping.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Iterable, Mapping

if TYPE_CHECKING:
    import asyncpg

# programs/athletes often use mcbb/wcbb; teams.sport uses ncaab_mens/ncaab_womens.
_TEAM_SPORT_ALIASES: dict[str, str] = {
    "cfb": "cfb",
    "football": "cfb",
    "fbs": "cfb",
    "ncaaf": "cfb",
    "mcbb": "ncaab_mens",
    "ncaab": "ncaab_mens",
    "ncaab_mens": "ncaab_mens",
    "mens": "ncaab_mens",
    "mens_basketball": "ncaab_mens",
    "mbb": "ncaab_mens",
    "wcbb": "ncaab_womens",
    "ncaaw": "ncaab_womens",
    "ncaab_womens": "ncaab_womens",
    "womens": "ncaab_womens",
    "womens_basketball": "ncaab_womens",
    "wbb": "ncaab_womens",
}


def canonical_team_sport(sport: object) -> str:
    s = str(sport or "").strip().lower()
    return _TEAM_SPORT_ALIASES.get(s, s)


def school_key(name: object) -> str:
    """Normalize punctuation/spacing drift across programs/teams/athletes."""
    return re.sub(r"[^a-z0-9]", "", str(name or "").strip().lower())


def team_sport_slugs_for(sport: object) -> list[str]:
    """Return teams.sport slug(s) that match an athlete/program sport code."""
    canonical = canonical_team_sport(sport)
    if not canonical:
        return []
    return [canonical]


def index_teams_by_school_sport(
    rows: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str], str]:
    """Map (school_key, canonical_sport) → teams.id string."""
    out: dict[tuple[str, str], str] = {}
    for row in rows:
        school_name = row.get("school_name")
        sport = row.get("sport")
        team_id = row.get("id")
        if not school_name or not sport or team_id is None:
            continue
        key = (school_key(school_name), canonical_team_sport(sport))
        out.setdefault(key, str(team_id))
    return out


def lookup_team_id(
    teams_by_key: Mapping[tuple[str, str], str],
    school: object,
    sport: object,
) -> str | None:
    if not school or not sport:
        return None
    return teams_by_key.get((school_key(school), canonical_team_sport(sport)))


async def fetch_teams_index(db: asyncpg.Connection) -> dict[tuple[str, str], str]:
    rows = await db.fetch("SELECT id, school_name, sport FROM teams")
    return index_teams_by_school_sport(rows)


async def resolve_team_id_for_school_sport(
    db: asyncpg.Connection,
    school: object,
    sport: object,
) -> str | None:
    """Look up a single teams.id for school + sport (with sport aliases)."""
    if not school or not sport:
        return None
    slugs = team_sport_slugs_for(sport)
    if not slugs:
        return None
    row = await db.fetchrow(
        """
        SELECT id
        FROM teams
        WHERE sport = ANY($1::text[])
          AND regexp_replace(lower(trim(school_name)), '[^a-z0-9]', '', 'g')
              = regexp_replace(lower(trim($2::text)), '[^a-z0-9]', '', 'g')
        LIMIT 1
        """,
        slugs,
        str(school),
    )
    return str(row["id"]) if row else None
