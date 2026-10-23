"""Persist position-relevant stats from scraper raw fields.

Canonical storage is the EAV ``athlete_season_stats`` table with grain
``(athlete_id, sport, season_year, season_type, team_id, stat_key)``
(see migration ``038_athlete_season_stats_v2.sql`` and ``season_stats_store``).

Prefer ``upsert_season_stat_lines`` when callers already have ``SeasonStatLine``
rows. This module keeps the legacy ``upsert_season_stats_from_raw`` path used by
the orchestrator until WP7 rewrites backfill onto season-scoped lines.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import asyncpg

from gravity_api.feature_engineering.positions import derive_position_group
from gravity_api.feature_engineering.sport_specs import get_position_spec, get_sport_spec
from gravity_api.scrapers.parsers.stat_catalog import all_stat_keys_for_sport
from gravity_api.scrapers.parsers.stat_normalizer import flatten_raw_for_stats
from gravity_api.scrapers.season_calendar import (
    current_season_year,
    parse_season_label,
    season_label as calendar_season_label,
    season_status,
)
from gravity_api.services.sport_pipeline.config import get_sport_pipeline_config

# Canonical EAV table after migration 038_athlete_season_stats_v2 (WP5).
EAV_TABLE = "athlete_season_stats"
_EAV_TABLE = EAV_TABLE  # back-compat alias for tests / monkeypatches
_TOT = "TOT"


async def upsert_season_stats_from_raw(
    conn: asyncpg.Connection,
    *,
    athlete_id: str,
    sport: str,
    position: str | None,
    raw: dict[str, Any],
    season_year: int | None = None,
) -> int:
    """Write numeric stat fields into EAV athlete_season_stats (TOT / regular)."""
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
    today = datetime.now(tz=timezone.utc).date()

    async def _write_eav(
        stats: dict[str, float],
        year: int,
        *,
        source_key: str,
        season_type: str = "regular",
        team_id: str = _TOT,
        team_name: str | None = None,
        is_total: bool = True,
        source_url: str | None = None,
        stats_as_of: datetime | None = None,
    ) -> int:
        count = 0
        games = int(stats.get("games_played_season") or stats.get("gp") or 0) or None
        label = calendar_season_label(sport, year)
        complete = season_status(sport, year, today) == "complete"
        as_of = stats_as_of or datetime.now(tz=timezone.utc)
        for key in store_keys:
            if key not in stats:
                continue
            val = stats[key]
            try:
                await conn.execute(
                    f"""INSERT INTO {_EAV_TABLE} (
                         athlete_id, sport, league, season_year, season_label,
                         season_type, team_id, team_name, is_total, is_complete,
                         position_group, stat_key, stat_value, games_played,
                         source_key, source_url, stats_as_of, observed_at,
                         validation_status
                       ) VALUES (
                         $1::uuid, $2, $3, $4, $5,
                         $6, $7, $8, $9, $10,
                         $11, $12, $13, $14,
                         $15, $16, $17, $18,
                         $19
                       )
                       ON CONFLICT (athlete_id, sport, season_year, season_type, team_id, stat_key)
                       DO UPDATE SET
                         stat_value = EXCLUDED.stat_value,
                         season_label = EXCLUDED.season_label,
                         team_name = COALESCE(EXCLUDED.team_name, {_EAV_TABLE}.team_name),
                         is_total = EXCLUDED.is_total,
                         is_complete = EXCLUDED.is_complete,
                         position_group = EXCLUDED.position_group,
                         games_played = EXCLUDED.games_played,
                         source_key = EXCLUDED.source_key,
                         source_url = COALESCE(EXCLUDED.source_url, {_EAV_TABLE}.source_url),
                         stats_as_of = EXCLUDED.stats_as_of,
                         observed_at = EXCLUDED.observed_at""",
                    athlete_id,
                    sport,
                    league,
                    year,
                    label,
                    season_type,
                    team_id,
                    team_name,
                    is_total,
                    complete,
                    position_group,
                    key,
                    float(val),
                    games,
                    source_key,
                    source_url,
                    as_of,
                    datetime.now(tz=timezone.utc),
                    "unvalidated",
                )
                count += 1
            except asyncpg.PostgresError:
                continue
        return count

    current_year = season_year or current_season_year(
        sport, datetime.now(tz=timezone.utc).date()
    )

    history = raw.get("season_stats_history")

    history_years: dict[int, dict[str, float]] = {}
    if isinstance(history, dict):
        for season_label_key, season_blob in history.items():
            if not isinstance(season_blob, dict):
                continue
            try:
                year = parse_season_label(sport, season_label_key)
            except (TypeError, ValueError):
                year = current_year
            normalized = flatten_raw_for_stats({"season_stats": season_blob}, sport)
            if not normalized:
                continue
            history_years[year] = normalized
            if year != current_year:
                written += await _write_eav(
                    normalized,
                    year,
                    source_key=str(raw.get("stats_source") or "espn_history"),
                )

    # B6: do NOT copy the latest completed season into the current-year row
    # ("scoring anchor"). Write the current-year row only from current-season data.
    current_blob = raw.get("season_stats")
    if isinstance(current_blob, dict) and current_blob:
        current_stats = flatten_raw_for_stats({"season_stats": current_blob}, sport)
    elif current_year in history_years:
        current_stats = history_years[current_year]
    else:
        # Flat raw may still carry current-season scalars without history.
        # Only write a current-year row when the payload is actually for that year
        # (explicit season_year arg or history entry) — never relabel prior seasons.
        current_stats = {}
        if season_year is not None and season_year == current_year:
            current_stats = flatten_raw_for_stats(raw, sport)

    if current_stats:
        written += await _write_eav(
            current_stats,
            current_year,
            source_key=str(raw.get("stats_source") or "scraper"),
        )

    # Optional history-client enrichment when espn_id is known (EAV via store).
    # Full SeasonStatLine backfill is WP7; callers with lines should use
    # ``upsert_season_stat_lines`` directly.
    espn_id = raw.get("espn_id")
    if espn_id:
        try:
            from gravity_api.scrapers.clients.espn_season_history import (
                EspnSeasonHistoryClient,
            )
            from gravity_api.services.sport_pipeline.season_stats_store import (
                upsert_season_stat_rows,
            )

            client = EspnSeasonHistoryClient()
            rows = await client.fetch_season_rows(str(espn_id), sport)
            written += await upsert_season_stat_rows(
                conn,
                athlete_id=athlete_id,
                rows=rows,
                position=position,
            )
        except Exception:
            pass

    return written


__all__ = ["EAV_TABLE", "upsert_season_stats_from_raw"]
