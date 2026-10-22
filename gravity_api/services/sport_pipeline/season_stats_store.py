"""Persist wide athlete_season_stats rows (+ EAV dual-write for cohort)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable

import asyncpg

from gravity_api.feature_engineering.positions import derive_position_group
from gravity_api.scrapers.clients.espn_season_history import SeasonStatRow
from gravity_api.scrapers.parsers.espn_season_year import is_current_espn_season
from gravity_api.services.sport_pipeline.config import get_sport_pipeline_config


async def upsert_season_stat_rows(
    conn: asyncpg.Connection,
    *,
    athlete_id: str,
    rows: Iterable[SeasonStatRow],
    position: str | None = None,
    refresh_season_years: set[int] | None = None,
    current_only: bool = False,
) -> int:
    """Write wide season rows.

    By default only inserts missing completed seasons and always refreshes the
    current in-progress season. Pass ``refresh_season_years`` (or CLI
    ``--refresh-season``) to force rewrite of completed seasons.
    """
    written = 0
    refresh = {int(y) for y in (refresh_season_years or set())}

    for row in rows:
        is_current = is_current_espn_season(row.espn_season_year, row.sport)
        if current_only and not is_current and row.espn_season_year not in refresh:
            continue

        # Completed seasons are write-once unless --refresh-season.
        if (
            row.is_complete
            and not is_current
            and row.espn_season_year not in refresh
        ):
            exists = await conn.fetchval(
                """SELECT 1 FROM athlete_season_stats
                   WHERE athlete_id = $1::uuid
                     AND league = $2
                     AND espn_season_year = $3
                     AND season_type = $4
                     AND team_id = $5""",
                athlete_id,
                row.league,
                row.espn_season_year,
                row.season_type,
                row.team_id,
            )
            if exists:
                continue

        position_group = derive_position_group(position, row.sport)
        try:
            league = get_sport_pipeline_config(row.sport).league
        except Exception:  # noqa: BLE001
            league = row.league

        counting = row.counting_stats()
        await conn.execute(
            """INSERT INTO athlete_season_stats (
                 athlete_id, espn_id, sport, league, season_label, espn_season_year,
                 season_type, team_id, team_abbr, games_played, stats,
                 is_complete, is_total, stats_as_of, source, source_url,
                 collected_at, collection_errors, position_group, metadata
               ) VALUES (
                 $1::uuid, $2, $3, $4, $5, $6,
                 $7, $8, $9, $10, $11::jsonb,
                 $12, $13, $14, $15, $16,
                 $17, $18::jsonb, $19, $20::jsonb
               )
               ON CONFLICT (athlete_id, league, espn_season_year, season_type, team_id)
               DO UPDATE SET
                 espn_id = EXCLUDED.espn_id,
                 sport = EXCLUDED.sport,
                 season_label = EXCLUDED.season_label,
                 team_abbr = EXCLUDED.team_abbr,
                 games_played = EXCLUDED.games_played,
                 stats = EXCLUDED.stats,
                 is_complete = EXCLUDED.is_complete,
                 is_total = EXCLUDED.is_total,
                 stats_as_of = EXCLUDED.stats_as_of,
                 source = EXCLUDED.source,
                 source_url = EXCLUDED.source_url,
                 collected_at = EXCLUDED.collected_at,
                 collection_errors = EXCLUDED.collection_errors,
                 position_group = COALESCE(EXCLUDED.position_group, athlete_season_stats.position_group),
                 metadata = EXCLUDED.metadata""",
            athlete_id,
            row.espn_id,
            row.sport,
            league,
            row.season_label,
            row.espn_season_year,
            row.season_type,
            row.team_id,
            row.team_abbr,
            row.games_played,
            json.dumps(counting),
            row.is_complete,
            row.is_total,
            row.stats_as_of,
            row.source,
            row.source_url,
            datetime.now(tz=timezone.utc),
            json.dumps(row.collection_errors),
            position_group,
            json.dumps({"raw_team_slug": row.raw_team_slug} if row.raw_team_slug else {}),
        )
        written += 1

        # Dual-write EAV for cohort baselines (skip TOT rows to avoid double-count).
        if not row.is_total:
            await _dual_write_eav(
                conn,
                athlete_id=athlete_id,
                sport=row.sport,
                league=league,
                season_year=row.espn_season_year,
                position_group=position_group,
                stats=counting,
                games_played=row.games_played,
                source_key=row.source,
            )
    return written


async def _dual_write_eav(
    conn: asyncpg.Connection,
    *,
    athlete_id: str,
    sport: str,
    league: str,
    season_year: int,
    position_group: str | None,
    stats: dict[str, float],
    games_played: int | None,
    source_key: str,
) -> None:
    # Detect whether EAV table exists (fresh envs after migration).
    try:
        for key, val in stats.items():
            await conn.execute(
                """INSERT INTO athlete_season_stats_eav (
                     athlete_id, sport, league, season_year, position_group,
                     stat_key, stat_value, games_played, source_key, observed_at
                   ) VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                   ON CONFLICT (athlete_id, sport, season_year, stat_key)
                   DO UPDATE SET
                     stat_value = EXCLUDED.stat_value,
                     position_group = EXCLUDED.position_group,
                     games_played = EXCLUDED.games_played,
                     observed_at = EXCLUDED.observed_at,
                     source_key = EXCLUDED.source_key""",
                athlete_id,
                sport,
                league,
                season_year,
                position_group,
                key,
                float(val),
                games_played,
                source_key,
                datetime.now(tz=timezone.utc),
            )
    except asyncpg.UndefinedTableError:
        return


async def load_season_rows_for_athlete(
    conn: asyncpg.Connection,
    athlete_id: str,
    *,
    league: str | None = None,
    as_of: datetime | None = None,
) -> list[dict[str, Any]]:
    """Load wide season rows; optional point-in-time filter on stats_as_of."""
    if as_of is not None:
        return [
            dict(r)
            for r in await conn.fetch(
                """SELECT * FROM athlete_season_stats
                   WHERE athlete_id = $1::uuid
                     AND ($2::text IS NULL OR league = $2)
                     AND stats_as_of <= $3
                   ORDER BY espn_season_year, season_type, is_total, team_id""",
                athlete_id,
                league,
                as_of,
            )
        ]
    return [
        dict(r)
        for r in await conn.fetch(
            """SELECT * FROM athlete_season_stats
               WHERE athlete_id = $1::uuid
                 AND ($2::text IS NULL OR league = $2)
               ORDER BY espn_season_year, season_type, is_total, team_id""",
            athlete_id,
            league,
        )
    ]


__all__ = [
    "load_season_rows_for_athlete",
    "upsert_season_stat_rows",
]
