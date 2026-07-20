"""Persist position-relevant stats from scraper raw fields."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import asyncpg

from gravity_api.feature_engineering.positions import derive_position_group
from gravity_api.feature_engineering.sport_specs import get_position_spec, get_sport_spec
from gravity_api.scrapers.parsers.stat_catalog import all_stat_keys_for_sport
from gravity_api.scrapers.parsers.stat_normalizer import flatten_raw_for_stats
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
    """Write numeric stat fields into athlete_season_stats (current + historical seasons)."""
    try:
        get_sport_spec(sport)
    except KeyError:
        return 0

    position_group = derive_position_group(position, sport)
    if not position_group:
        return 0

    try:
        get_position_spec(sport, position_group)
    except KeyError:
        return 0

    league = get_sport_pipeline_config(sport).league
    written = 0
    store_keys = all_stat_keys_for_sport(sport)

    async def _write_season(
        stats: dict[str, float],
        year: int,
        *,
        source_key: str,
    ) -> int:
        count = 0
        games = int(stats.get("games_played_season") or stats.get("gp") or 0) or None
        for key in store_keys:
            if key not in stats:
                continue
            val = stats[key]
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
                    year,
                    position_group,
                    key,
                    float(val),
                    games,
                    source_key,
                    datetime.now(tz=timezone.utc),
                )
                count += 1
            except asyncpg.PostgresError:
                continue
        return count

    current_year = season_year or _current_season_year()

    history = raw.get("season_stats_history")

    # First, persist every real per-season row under its actual year (used for
    # feature engineering: trajectories, peaks, recent-form). Skip current_year
    # itself — that slot is reserved for the scoring "anchor" written last so it
    # is authoritative and never overwritten by an in-progress partial season.
    history_years: dict[int, dict[str, float]] = {}
    if isinstance(history, dict):
        for season_label, season_blob in history.items():
            if not isinstance(season_blob, dict):
                continue
            year = _parse_season_year(season_label, fallback=current_year)
            normalized = flatten_raw_for_stats({"season_stats": season_blob}, sport)
            if not normalized:
                continue
            history_years[year] = normalized
            if year != current_year:
                written += await _write_season(
                    normalized,
                    year,
                    source_key=str(raw.get("stats_source") or "espn_history"),
                )

    # The scoring anchor (current_year row) must be a single clean season. Use
    # the latest COMPLETED season (year < current_year) when available — pros in
    # the offseason have no games in current_year, and the flattened top-level
    # scalars can carry career-cumulative leakage (e.g. games_played = career
    # total). Fall back to any real season, then to flattened scalars.
    anchor_stats: dict[str, float] | None = None
    completed = [y for y in history_years if y < current_year]
    if completed:
        anchor_stats = history_years[max(completed)]
    elif history_years:
        anchor_stats = history_years[max(history_years)]

    current_stats = anchor_stats or flatten_raw_for_stats(raw, sport)
    written += await _write_season(
        current_stats,
        current_year,
        source_key=str(raw.get("stats_source") or "scraper"),
    )

    return written


def _parse_season_year(label: str | int, *, fallback: int) -> int:
    if isinstance(label, int):
        return label
    text = str(label).strip()
    for token in text.replace("-", " ").split():
        if token.isdigit() and len(token) == 4:
            return int(token)
    return fallback


def _current_season_year() -> int:
    now = datetime.now(tz=timezone.utc)
    return now.year if now.month >= 7 else now.year - 1
