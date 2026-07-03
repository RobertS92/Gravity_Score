"""Team season win/loss records — CFBD and DB persistence."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


def normalize_team_id(name: str | None) -> str:
    if not name:
        return ""
    return " ".join(re.sub(r"[^a-z0-9\s'-]", " ", str(name).lower()).split())


async def upsert_team_season_stats(
    conn: asyncpg.Connection,
    *,
    sport: str,
    team_id: str,
    season_year: int,
    wins: int,
    losses: int,
    ties: int = 0,
    team_name: str | None = None,
    conference_wins: int | None = None,
    conference_losses: int | None = None,
    source_key: str = "cfbd",
    metadata: dict[str, Any] | None = None,
) -> None:
    total = max(wins + losses + ties, 0)
    win_pct = round(wins / total, 4) if total > 0 else None
    await conn.execute(
        """INSERT INTO team_season_stats (
             sport, team_id, team_name, season_year, wins, losses, ties, win_pct,
             conference_wins, conference_losses, source_key, metadata
           ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb)
           ON CONFLICT (sport, team_id, season_year) DO UPDATE SET
             team_name = COALESCE(EXCLUDED.team_name, team_season_stats.team_name),
             wins = EXCLUDED.wins,
             losses = EXCLUDED.losses,
             ties = EXCLUDED.ties,
             win_pct = EXCLUDED.win_pct,
             conference_wins = COALESCE(EXCLUDED.conference_wins, team_season_stats.conference_wins),
             conference_losses = COALESCE(EXCLUDED.conference_losses, team_season_stats.conference_losses),
             source_key = EXCLUDED.source_key,
             observed_at = NOW(),
             metadata = team_season_stats.metadata || EXCLUDED.metadata""",
        sport,
        normalize_team_id(team_id),
        team_name or team_id,
        season_year,
        wins,
        losses,
        ties,
        win_pct,
        conference_wins,
        conference_losses,
        source_key,
        metadata or {},
    )


async def fetch_team_season_stats(
    conn: asyncpg.Connection,
    *,
    sport: str,
    team_id: str,
    season_year: int,
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """SELECT * FROM team_season_stats
           WHERE sport = $1 AND team_id = $2 AND season_year = $3""",
        sport,
        normalize_team_id(team_id),
        season_year,
    )


async def team_win_pct_percentile(
    conn: asyncpg.Connection,
    *,
    sport: str,
    season_year: int,
    win_pct: float,
) -> float:
    """Percentile rank of win_pct within sport-season cohort (0–100)."""
    row = await conn.fetchrow(
        """SELECT COUNT(*) AS n,
                  COUNT(*) FILTER (WHERE win_pct <= $3) AS le
           FROM team_season_stats
           WHERE sport = $1 AND season_year = $2 AND win_pct IS NOT NULL""",
        sport,
        season_year,
        win_pct,
    )
    n = int(row["n"] or 0) if row else 0
    if n < 3:
        return min(100.0, max(0.0, win_pct * 100.0))
    le = int(row["le"] or 0)
    return round(100.0 * le / n, 2)


async def upsert_athlete_team_season(
    conn: asyncpg.Connection,
    *,
    athlete_id: str,
    sport: str,
    team_id: str,
    season_year: int,
    games_played: int | None = None,
    games_started: int | None = None,
    team_name: str | None = None,
    source_key: str = "pipeline",
) -> None:
    await conn.execute(
        """INSERT INTO athlete_team_seasons (
             athlete_id, sport, team_id, team_name, season_year,
             games_played, games_started, source_key
           ) VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8)
           ON CONFLICT (athlete_id, sport, season_year, team_id) DO UPDATE SET
             games_played = COALESCE(EXCLUDED.games_played, athlete_team_seasons.games_played),
             games_started = COALESCE(EXCLUDED.games_started, athlete_team_seasons.games_started),
             team_name = COALESCE(EXCLUDED.team_name, athlete_team_seasons.team_name),
             source_key = EXCLUDED.source_key,
             observed_at = NOW()""",
        athlete_id,
        sport,
        normalize_team_id(team_id),
        team_name or team_id,
        season_year,
        games_played,
        games_started,
        source_key,
    )


async def ensure_team_season_from_cfbd(
    conn: asyncpg.Connection,
    *,
    sport: str,
    team_name: str,
    season_year: int,
) -> asyncpg.Record | None:
    """Load team record from DB or fetch once from CFBD and cache."""
    team_id = normalize_team_id(team_name)
    row = await fetch_team_season_stats(conn, sport=sport, team_id=team_id, season_year=season_year)
    if row:
        return row
    if sport != "cfb":
        return None
    from gravity_api.scrapers.clients.cfbd import CfbdClient, cfbd_is_rate_limited

    if cfbd_is_rate_limited():
        return None
    client = CfbdClient()
    if not client.enabled:
        return None
    record = await client.team_record(year=season_year, team=team_name)
    if not record:
        return None
    await upsert_team_season_stats(
        conn,
        sport=sport,
        team_id=team_id,
        season_year=season_year,
        wins=int(record["wins"]),
        losses=int(record["losses"]),
        ties=int(record.get("ties") or 0),
        team_name=str(record.get("team") or team_name),
        conference_wins=int(record.get("conference_wins") or 0) or None,
        conference_losses=int(record.get("conference_losses") or 0) or None,
        source_key="cfbd",
    )
    return await fetch_team_season_stats(conn, sport=sport, team_id=team_id, season_year=season_year)


async def enrich_raw_with_team_season(
    conn: asyncpg.Connection,
    *,
    athlete_id: str,
    sport: str,
    team_name: str | None,
    season_year: int,
    raw: dict[str, Any],
) -> dict[str, Any]:
    """Attach team win/loss context and persist athlete-team-season row."""
    if sport != "cfb" or not team_name:
        return raw
    team_id = normalize_team_id(team_name)
    row = await fetch_team_season_stats(conn, sport=sport, team_id=team_id, season_year=season_year)
    if row is None and raw.get("team_win_pct") is None:
        row = await ensure_team_season_from_cfbd(
            conn, sport=sport, team_name=team_name, season_year=season_year
        )
    out = dict(raw)
    if row:
        out["team_wins"] = int(row["wins"] or 0)
        out["team_losses"] = int(row["losses"] or 0)
        out["team_ties"] = int(row["ties"] or 0)
        if row["win_pct"] is not None:
            out["team_win_pct"] = float(row["win_pct"])
            out["team_win_pct_percentile"] = await team_win_pct_percentile(
                conn,
                sport=sport,
                season_year=season_year,
                win_pct=float(row["win_pct"]),
            )
        out["team_record_observed"] = 1

    gp = raw.get("games_played_season") or raw.get("gp")
    gs = raw.get("games_started") or raw.get("gs")
    try:
        gp_i = int(float(gp)) if gp is not None else None
    except (TypeError, ValueError):
        gp_i = None
    try:
        gs_i = int(float(gs)) if gs is not None else None
    except (TypeError, ValueError):
        gs_i = None

    if team_id:
        await upsert_athlete_team_season(
            conn,
            athlete_id=athlete_id,
            sport=sport,
            team_id=team_id,
            season_year=season_year,
            games_played=gp_i,
            games_started=gs_i,
            team_name=team_name,
            source_key=str(raw.get("stats_source") or "pipeline"),
        )
    return out
