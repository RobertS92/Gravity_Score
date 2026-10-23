"""Persist games and player box rows (WP10).

Upserts are idempotent on ``games.game_id`` and
``game_player_box (game_id, espn_athlete_id)``. CFB play writers are deferred
until ``cfbd_plays`` fetchers are wired into the backfill job.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

import asyncpg


async def upsert_game(
    conn: asyncpg.Connection,
    *,
    game_id: str,
    league: str,
    season_year: int,
    season_type: str = "regular",
    start_time: datetime | None = None,
    home_team_id: str | None = None,
    away_team_id: str | None = None,
    home_score: int | None = None,
    away_score: int | None = None,
    neutral_site: bool | None = None,
    status: str | None = None,
    source_url: str | None = None,
    collected_at: datetime | None = None,
) -> str:
    """Insert or update one ``games`` row. Returns ``game_id``."""
    if season_type not in ("regular", "postseason"):
        raise ValueError(f"invalid season_type: {season_type}")
    when = collected_at or datetime.now(tz=timezone.utc)
    await conn.execute(
        """INSERT INTO games (
             game_id, league, season_year, season_type, start_time,
             home_team_id, away_team_id, home_score, away_score,
             neutral_site, status, source_url, collected_at
           ) VALUES (
             $1, $2, $3, $4, $5,
             $6, $7, $8, $9,
             $10, $11, $12, $13
           )
           ON CONFLICT (game_id) DO UPDATE SET
             league = EXCLUDED.league,
             season_year = EXCLUDED.season_year,
             season_type = EXCLUDED.season_type,
             start_time = COALESCE(EXCLUDED.start_time, games.start_time),
             home_team_id = COALESCE(EXCLUDED.home_team_id, games.home_team_id),
             away_team_id = COALESCE(EXCLUDED.away_team_id, games.away_team_id),
             home_score = COALESCE(EXCLUDED.home_score, games.home_score),
             away_score = COALESCE(EXCLUDED.away_score, games.away_score),
             neutral_site = COALESCE(EXCLUDED.neutral_site, games.neutral_site),
             status = COALESCE(EXCLUDED.status, games.status),
             source_url = COALESCE(EXCLUDED.source_url, games.source_url),
             collected_at = EXCLUDED.collected_at""",
        str(game_id),
        league,
        int(season_year),
        season_type,
        start_time,
        home_team_id,
        away_team_id,
        home_score,
        away_score,
        neutral_site,
        status,
        source_url,
        when,
    )
    return str(game_id)


async def upsert_box_rows(
    conn: asyncpg.Connection,
    game_id: str,
    rows: Iterable[Mapping[str, Any]],
) -> int:
    """Upsert player box rows for ``game_id``.

    Each row mapping may include:
    ``espn_athlete_id`` (required), ``athlete_id``, ``team_id``, ``started``,
    ``minutes``, ``snaps``, ``stats`` (dict → JSONB).
    """
    written = 0
    for row in rows:
        espn_athlete_id = str(row.get("espn_athlete_id") or "").strip()
        if not espn_athlete_id:
            continue
        stats = row.get("stats") or {}
        if not isinstance(stats, dict):
            stats = {}
        athlete_id = row.get("athlete_id")
        await conn.execute(
            """INSERT INTO game_player_box (
                 game_id, athlete_id, espn_athlete_id, team_id,
                 started, minutes, snaps, stats
               ) VALUES (
                 $1, $2::uuid, $3, $4,
                 $5, $6, $7, $8::jsonb
               )
               ON CONFLICT (game_id, espn_athlete_id) DO UPDATE SET
                 athlete_id = COALESCE(EXCLUDED.athlete_id, game_player_box.athlete_id),
                 team_id = COALESCE(EXCLUDED.team_id, game_player_box.team_id),
                 started = COALESCE(EXCLUDED.started, game_player_box.started),
                 minutes = COALESCE(EXCLUDED.minutes, game_player_box.minutes),
                 snaps = COALESCE(EXCLUDED.snaps, game_player_box.snaps),
                 stats = EXCLUDED.stats""",
            str(game_id),
            str(athlete_id) if athlete_id else None,
            espn_athlete_id,
            str(row["team_id"]) if row.get("team_id") is not None else None,
            row.get("started") if isinstance(row.get("started"), bool) else None,
            row.get("minutes"),
            row.get("snaps"),
            json.dumps(stats),
        )
        written += 1
    return written


__all__ = ["upsert_game", "upsert_box_rows"]
