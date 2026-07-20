#!/usr/bin/env python3
"""Backfill team_season_stats from ESPN for NFL/NBA/WNBA (and optional college).

Fetches each league's team list once, then pulls regular-season W-L into
team_season_stats so scoring enrich_raw_with_team_season hits cache.

Usage:
  PYTHONPATH=. .venv/bin/python scripts/backfill_team_records_espn.py
  PYTHONPATH=. .venv/bin/python scripts/backfill_team_records_espn.py --sports nfl nba --years 2025 2024
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import asyncpg

from gravity_api.config import get_settings
from gravity_api.scrapers.clients.espn import EspnClient
from gravity_api.scrapers.roster.pro_league_resolver import fetch_pro_league_entries
from gravity_api.services.team_season_records import upsert_team_season_stats

logger = logging.getLogger("backfill_team_records")

DEFAULT_SPORTS = ("nfl", "nba", "wnba")


async def backfill_sport(
    conn: asyncpg.Connection,
    client: EspnClient,
    sport: str,
    years: list[int],
) -> dict[str, int]:
    entries = fetch_pro_league_entries(sport)
    if not entries:
        logger.warning("[%s] no teams from ESPN league list", sport)
        return {"teams": 0, "written": 0, "missed": 0}

    written = 0
    missed = 0
    for entry in entries:
        tid = str(entry.get("espn_team_id") or "")
        name = str(entry.get("school_name") or tid)
        if not tid:
            continue
        for year in years:
            record = await client.fetch_team_season_record(
                sport,
                season_year=year,
                team_name=name,
                espn_team_id=tid,
            )
            if not record or (record["wins"] + record["losses"]) <= 0:
                missed += 1
                logger.debug("[%s] miss %s %s", sport, name, year)
                continue
            await upsert_team_season_stats(
                conn,
                sport=sport,
                team_id=name,
                season_year=year,
                wins=int(record["wins"]),
                losses=int(record["losses"]),
                ties=int(record.get("ties") or 0),
                team_name=name,
                source_key="espn",
                metadata={
                    "espn_team_id": tid,
                    "summary": record.get("summary"),
                    "season_type": record.get("season_type"),
                },
            )
            # Also write under scoring-anchor year if caller asked for current
            # season that maps to prior completed year — already covered by years list.
            written += 1
            logger.info(
                "[%s] %s %s → %s (%s)",
                sport,
                name,
                year,
                record.get("summary"),
                record.get("win_pct"),
            )
    return {"teams": len(entries), "written": written, "missed": missed}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sports", nargs="+", default=list(DEFAULT_SPORTS))
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=None,
        help="Season years to fetch (default: current scoring year + prior)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    from gravity_api.services.sport_pipeline.season_stats import _current_season_year

    years = args.years or [_current_season_year(), _current_season_year() - 1]
    years = sorted(set(years), reverse=True)

    settings = get_settings()
    pool = await asyncpg.create_pool(
        settings.pg_dsn, min_size=1, max_size=4, statement_cache_size=0
    )
    client = EspnClient()
    try:
        async with pool.acquire() as conn:
            for sport in args.sports:
                stats = await backfill_sport(conn, client, sport, years)
                logger.info("[%s] done %s", sport, stats)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
