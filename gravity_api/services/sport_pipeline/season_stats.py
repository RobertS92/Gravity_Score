"""Persist position-relevant stats from scraper raw fields."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import asyncpg

from gravity_api.feature_engineering.positions import derive_position_group
from gravity_api.feature_engineering.sport_specs import get_position_spec, get_sport_spec
from gravity_api.services.sport_pipeline.config import get_sport_pipeline_config


async def upsert_season_stats_from_raw(
    conn: asyncpg.Connection,
    *,
    athlete_id: str,
    sport: str,
    position: str | None,
    raw: dict[str, Any],
    season_year: int | None = None,
) -> int:
    """Write numeric stat fields for the athlete's position into athlete_season_stats."""
    try:
        get_sport_spec(sport)
    except KeyError:
        return 0

    season_year = season_year or _current_season_year()
    position_group = derive_position_group(position, sport)
    if not position_group:
        return 0

    try:
        pos_spec = get_position_spec(sport, position_group)
    except KeyError:
        return 0

    league = get_sport_pipeline_config(sport).league
    written = 0
    stat_keys = {sw.stat_key for sw in pos_spec.performance_stats}
    stat_keys.add("games_played_season")

    for key in stat_keys:
        val = raw.get(key)
        if val is None:
            continue
        try:
            num = float(val)
        except (TypeError, ValueError):
            continue
        try:
            await conn.execute(
                """INSERT INTO athlete_season_stats (
                     athlete_id, sport, league, season_year, position_group,
                     stat_key, stat_value, games_played, source_key, observed_at
                   ) VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                   ON CONFLICT (athlete_id, sport, season_year, stat_key)
                   DO UPDATE SET
                     stat_value = EXCLUDED.stat_value,
                     position_group = EXCLUDED.position_group,
                     games_played = EXCLUDED.games_played,
                     observed_at = EXCLUDED.observed_at""",
                athlete_id,
                sport,
                league,
                season_year,
                position_group,
                key,
                num,
                int(raw.get("games_played_season") or 0) or None,
                raw.get("stats_source") or "scraper",
                datetime.now(tz=timezone.utc),
            )
            written += 1
        except asyncpg.PostgresError:
            continue
    return written


def _current_season_year() -> int:
    now = datetime.now(tz=timezone.utc)
    # Academic/sports season: use calendar year; callers can override.
    return now.year if now.month >= 7 else now.year - 1
