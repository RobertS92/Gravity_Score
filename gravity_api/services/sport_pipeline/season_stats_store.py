"""Persist athlete_season_stats EAV rows (SCRAPER_FIX_SPEC §4.2 / WP5).

Canonical storage is the classic EAV table ``athlete_season_stats`` with grain
``(athlete_id, sport, season_year, season_type, team_id, stat_key)``.
Prefer ``upsert_season_stat_lines`` for ``SeasonStatLine`` inputs.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Iterable

import asyncpg

from gravity_api.feature_engineering.positions import derive_position_group
from gravity_api.scrapers.clients.espn_season_history import SeasonStatRow
from gravity_api.scrapers.parsers.espn_season_year import is_current_espn_season
from gravity_api.scrapers.parsers.stat_catalog import filter_counting_stats
from gravity_api.scrapers.parsers.stat_normalizer import normalize_namespaced_stats
from gravity_api.scrapers.season_calendar import (
    season_label as calendar_season_label,
    season_status,
)
from gravity_api.scrapers.types import SeasonStatLine
from gravity_api.services.sport_pipeline.config import get_sport_pipeline_config

_EAV_TABLE = "athlete_season_stats"
_TOT = "TOT"


def _canonical_stats(league: str, stats: dict[str, float]) -> dict[str, float]:
    """Normalize namespaced keys when present; otherwise pass flat keys through."""
    if not stats:
        return {}
    if any("." in str(k) for k in stats):
        return normalize_namespaced_stats(league, stats)
    return {str(k): float(v) for k, v in stats.items() if v is not None}


def _games_played(stats: dict[str, float]) -> int | None:
    for key in ("games_played_season", "gp", "g", "games_played"):
        if key in stats and stats[key] is not None:
            try:
                return int(stats[key])
            except (TypeError, ValueError):
                continue
    return None


def _games_started(stats: dict[str, float]) -> int | None:
    for key in ("games_started", "gs"):
        if key in stats and stats[key] is not None:
            try:
                return int(stats[key])
            except (TypeError, ValueError):
                continue
    return None


def _is_complete(league: str, season_year: int, on: date | None = None) -> bool:
    day = on or datetime.now(tz=timezone.utc).date()
    return season_status(league, season_year, day) == "complete"


async def upsert_season_stat_lines(
    conn: asyncpg.Connection,
    athlete_id: str,
    lines: list[SeasonStatLine],
    *,
    position: str | None = None,
    sport: str | None = None,
) -> int:
    """Write EAV rows + athlete_team_seasons for one athlete in a single transaction.

    Stats are passed through ``normalize_namespaced_stats`` when keys are
    ``category.stat`` namespaced. Returns the number of EAV stat rows upserted.
    """
    if not lines:
        return 0

    written = 0
    # One transaction per athlete (caller may already be in a tx; use nested savepoint).
    tr = conn.transaction()
    async with tr:
        for line in lines:
            league = line.league
            try:
                pipeline_league = get_sport_pipeline_config(
                    sport or line.league
                ).league
            except Exception:  # noqa: BLE001
                pipeline_league = league

            row_sport = sport or line.league
            position_group = derive_position_group(position, row_sport)
            canonical = _canonical_stats(row_sport, dict(line.stats))
            if not canonical:
                continue

            games = _games_played(canonical)
            label = calendar_season_label(row_sport, line.season_year)
            complete = _is_complete(row_sport, line.season_year)
            team_id = line.team_id or _TOT
            is_total = bool(line.is_total) or team_id == _TOT
            stats_as_of = line.stats_as_of
            if stats_as_of is not None and stats_as_of.tzinfo is None:
                stats_as_of = stats_as_of.replace(tzinfo=timezone.utc)

            # Optional validation stamp: source_key may end with ``|matched`` etc.
            source_key = line.source_key or "espn"
            validation_status = "unvalidated"
            if "|" in source_key:
                base_key, maybe_status = source_key.rsplit("|", 1)
                if maybe_status in {
                    "unvalidated",
                    "matched",
                    "mismatch",
                    "no_second_source",
                }:
                    source_key = base_key
                    validation_status = maybe_status

            for key, val in canonical.items():
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
                         position_group = COALESCE(EXCLUDED.position_group, {_EAV_TABLE}.position_group),
                         games_played = EXCLUDED.games_played,
                         source_key = EXCLUDED.source_key,
                         source_url = EXCLUDED.source_url,
                         stats_as_of = EXCLUDED.stats_as_of,
                         observed_at = EXCLUDED.observed_at,
                         validation_status = COALESCE(
                           EXCLUDED.validation_status, {_EAV_TABLE}.validation_status
                         ),
                         league = EXCLUDED.league""",
                    athlete_id,
                    row_sport,
                    pipeline_league,
                    int(line.season_year),
                    label,
                    line.season_type,
                    team_id,
                    line.team_name,
                    is_total,
                    complete,
                    position_group,
                    key,
                    float(val),
                    games,
                    source_key,
                    line.source_url,
                    stats_as_of,
                    datetime.now(tz=timezone.utc),
                    validation_status,
                )
                written += 1

            # athlete_team_seasons: one row per real team (skip pure TOT aggregates).
            if team_id != _TOT:
                gs = _games_started(canonical)
                try:
                    await conn.execute(
                        """INSERT INTO athlete_team_seasons (
                             athlete_id, sport, team_id, team_name, season_year,
                             games_played, games_started, source_key, observed_at
                           ) VALUES (
                             $1::uuid, $2, $3, $4, $5, $6, $7, $8, $9
                           )
                           ON CONFLICT (athlete_id, sport, season_year, team_id)
                           DO UPDATE SET
                             team_name = COALESCE(EXCLUDED.team_name, athlete_team_seasons.team_name),
                             games_played = EXCLUDED.games_played,
                             games_started = EXCLUDED.games_started,
                             source_key = EXCLUDED.source_key,
                             observed_at = EXCLUDED.observed_at""",
                        athlete_id,
                        row_sport,
                        team_id,
                        line.team_name,
                        int(line.season_year),
                        games,
                        gs,
                        line.source_key,
                        datetime.now(tz=timezone.utc),
                    )
                except asyncpg.UndefinedTableError:
                    pass

    return written


async def upsert_season_stat_rows(
    conn: asyncpg.Connection,
    *,
    athlete_id: str,
    rows: Iterable[SeasonStatRow],
    position: str | None = None,
    refresh_season_years: set[int] | None = None,
    current_only: bool = False,
) -> int:
    """Adapt legacy ``SeasonStatRow`` wide-path rows into EAV ``SeasonStatLine`` writes.

    Kept for ``backfill_season_stats`` until WP7 rewrites that job onto
    ``SeasonStatLine`` / ``upsert_season_stat_lines`` directly.
    """
    refresh = {int(y) for y in (refresh_season_years or set())}
    row_list = list(rows)
    lines: list[SeasonStatLine] = []

    for row in row_list:
        is_current = is_current_espn_season(row.espn_season_year, row.sport)
        if current_only and not is_current and row.espn_season_year not in refresh:
            continue

        if (
            row.is_complete
            and not is_current
            and row.espn_season_year not in refresh
        ):
            exists = await conn.fetchval(
                f"""SELECT 1 FROM {_EAV_TABLE}
                   WHERE athlete_id = $1::uuid
                     AND sport = $2
                     AND season_year = $3
                     AND season_type = $4
                     AND team_id = $5
                   LIMIT 1""",
                athlete_id,
                row.sport,
                row.espn_season_year,
                row.season_type,
                row.team_id,
            )
            if exists:
                continue

        # Flat counting stats (already de-rated) → SeasonStatLine with flat keys.
        counting = filter_counting_stats(row.counting_stats())
        # Preserve GP even when filter_counting keeps it; counting_stats already drops rates.
        stats = dict(counting)
        if row.games_played is not None and "gp" not in stats and "games_played_season" not in stats:
            stats["games_played_season"] = float(row.games_played)

        lines.append(
            SeasonStatLine(
                league=row.league or row.sport,
                season_year=int(row.espn_season_year),
                season_type=row.season_type,
                team_id=row.team_id,
                team_name=row.team_abbr,
                is_total=bool(row.is_total),
                stats=stats,
                source_key=row.source,
                source_url=row.source_url,
                stats_as_of=row.stats_as_of,
            )
        )

    if not lines:
        return 0
    # Group is already one athlete; one transaction inside upsert_season_stat_lines.
    sport = row_list[0].sport if row_list else None
    return await upsert_season_stat_lines(
        conn, athlete_id, lines, position=position, sport=sport
    )


async def load_season_rows_for_athlete(
    conn: asyncpg.Connection,
    athlete_id: str,
    *,
    league: str | None = None,
    sport: str | None = None,
    as_of: datetime | None = None,
    team_id: str = _TOT,
    season_type: str = "regular",
) -> list[dict[str, Any]]:
    """Load EAV season rows for one athlete (default: TOT regular grain)."""
    params: list[Any] = [athlete_id, team_id, season_type]
    clauses = [
        "athlete_id = $1::uuid",
        "team_id = $2",
        "season_type = $3",
    ]
    if sport is not None:
        params.append(sport)
        clauses.append(f"sport = ${len(params)}")
    if league is not None:
        params.append(league)
        clauses.append(f"league = ${len(params)}")
    if as_of is not None:
        params.append(as_of)
        clauses.append(f"stats_as_of <= ${len(params)}")

    where = " AND ".join(clauses)
    rows = await conn.fetch(
        f"""SELECT * FROM {_EAV_TABLE}
           WHERE {where}
           ORDER BY season_year, season_type, is_total DESC, team_id, stat_key""",
        *params,
    )
    return [dict(r) for r in rows]


__all__ = [
    "load_season_rows_for_athlete",
    "upsert_season_stat_lines",
    "upsert_season_stat_rows",
]
