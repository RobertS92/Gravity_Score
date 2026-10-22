"""Persist position-relevant stats from scraper raw fields.

Canonical storage is the wide ``athlete_season_stats`` table (see
``season_stats_store``). This module keeps the EAV dual-write used by cohort
baselines and also feeds the wide table when ``season_stats_history`` is present.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import asyncpg

from gravity_api.feature_engineering.positions import derive_position_group
from gravity_api.feature_engineering.sport_specs import get_position_spec, get_sport_spec
from gravity_api.scrapers.parsers.espn_season_year import espn_season_year
from gravity_api.scrapers.parsers.stat_catalog import all_stat_keys_for_sport
from gravity_api.scrapers.parsers.stat_normalizer import flatten_raw_for_stats
from gravity_api.services.sport_pipeline.config import get_sport_pipeline_config

# EAV table used by cohort baselines after migration 038.
_EAV_TABLE = "athlete_season_stats_eav"


async def upsert_season_stats_from_raw(
    conn: asyncpg.Connection,
    *,
    athlete_id: str,
    sport: str,
    position: str | None,
    raw: dict[str, Any],
    season_year: int | None = None,
) -> int:
    """Write numeric stat fields into EAV + wide athlete_season_stats."""
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

    async def _write_eav(
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
                    f"""INSERT INTO {_EAV_TABLE} (
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
            except asyncpg.UndefinedTableError:
                # Pre-migration env: fall back to legacy table name if present.
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
            except asyncpg.PostgresError:
                continue
        return count

    current_year = season_year or _current_season_year(sport)

    history = raw.get("season_stats_history")

    history_years: dict[int, dict[str, float]] = {}
    if isinstance(history, dict):
        for season_label, season_blob in history.items():
            if not isinstance(season_blob, dict):
                continue
            year = _parse_season_year(season_label, sport=sport, fallback=current_year)
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

    anchor_stats: dict[str, float] | None = None
    completed = [y for y in history_years if y < current_year]
    if completed:
        anchor_stats = history_years[max(completed)]
    elif history_years:
        anchor_stats = history_years[max(history_years)]

    current_stats = anchor_stats or flatten_raw_for_stats(raw, sport)
    written += await _write_eav(
        current_stats,
        current_year,
        source_key=str(raw.get("stats_source") or "scraper"),
    )

    # Prefer the dedicated season-history client when espn_id is known.
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
            # Wide-table path is best-effort from the orchestrator; EAV already written.
            pass

    return written


def _parse_season_year(label: str | int, *, sport: str, fallback: int) -> int:
    try:
        return espn_season_year(label, sport, fallback=fallback)
    except ValueError:
        return fallback


def _current_season_year(sport: str | None = None) -> int:
    from gravity_api.scrapers.parsers.espn_season_year import (
        is_current_espn_season,
        normalize_sport_key,
    )

    now = datetime.now(tz=timezone.utc)
    sport_n = normalize_sport_key(sport)
    # Probe a small window of candidate years.
    for candidate in (now.year + 1, now.year, now.year - 1):
        if is_current_espn_season(candidate, sport_n):
            return candidate
    return now.year if now.month >= 7 else now.year - 1


__all__ = ["upsert_season_stats_from_raw", "_current_season_year", "_parse_season_year"]
