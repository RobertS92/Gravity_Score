"""Bidirectional sync between athlete_season_stats and raw_athlete_data."""

from __future__ import annotations

from typing import Any

import asyncpg

from gravity_api.scrapers.parsers.stat_normalizer import finalize_stat_fields
from gravity_api.services.sport_pipeline.season_stats import _current_season_year


def _is_empty(val: Any) -> bool:
    if val is None or val == "":
        return True
    if isinstance(val, (int, float)) and val <= 0:
        return True
    if isinstance(val, (list, dict)) and len(val) == 0:
        return True
    return False


def apply_ass_enrichment_to_raw(raw: dict[str, Any], enrichment: dict[str, Any]) -> dict[str, Any]:
    """Fill gaps in raw from athlete_season_stats without clobbering richer scraper data."""
    if not enrichment:
        return raw

    out = dict(raw)
    enrich_season = enrichment.get("season_stats")
    raw_season = out.get("season_stats")
    if not isinstance(raw_season, dict):
        raw_season = {}

    if isinstance(enrich_season, dict) and enrich_season:
        merged_season = dict(raw_season)
        for key, val in enrich_season.items():
            if _is_empty(merged_season.get(key)) and not _is_empty(val):
                merged_season[key] = val
        if merged_season:
            out["season_stats"] = merged_season
            for key, val in merged_season.items():
                if _is_empty(out.get(key)) and not _is_empty(val):
                    out[key] = val

    for key, val in enrichment.items():
        if key == "season_stats":
            continue
        if _is_empty(out.get(key)) and not _is_empty(val):
            out[key] = val

    return out


async def enrich_raw_from_athlete_season_stats(
    conn: asyncpg.Connection,
    athlete_id: str,
    sport: str,
) -> dict[str, Any]:
    """Load current-season athlete_season_stats rows into a raw enrichment blob."""
    current_year = _current_season_year()
    rows = await conn.fetch(
        """SELECT stat_key, stat_value, games_played
           FROM athlete_season_stats
           WHERE athlete_id = $1::uuid AND sport = $2 AND season_year = $3""",
        athlete_id,
        sport,
        current_year,
    )
    if not rows:
        return {}

    season_stats: dict[str, float] = {}
    games_played: int | None = None
    for row in rows:
        season_stats[str(row["stat_key"])] = float(row["stat_value"])
        if row["games_played"]:
            games_played = int(row["games_played"])

    enrichment: dict[str, Any] = {"season_stats": season_stats}
    gp = games_played or season_stats.get("games_played_season") or season_stats.get("gp")
    if gp is not None:
        enrichment["games_played_season"] = int(gp)

    return finalize_stat_fields(sport, enrichment)


__all__ = ["apply_ass_enrichment_to_raw", "enrich_raw_from_athlete_season_stats"]
