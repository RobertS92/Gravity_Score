"""Backfill games + player box scores (WP10 stub).

Usage::

  PYTHONPATH=. python3 -m gravity_api.jobs.backfill_game_boxes \\
    --league ncaab_mens --season-year 2024 --limit 20

Orchestration is stubbed: lists CLI args, opens DB when ``PG_DSN`` is set,
and logs the intended crawl scope. Full ESPN scoreboard enumeration + box
upsert + CFB play pulls land once fixtures and quota gates are ready.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env", override=True)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SUPPORTED_LEAGUES = (
    "ncaab_mens",
    "ncaab_womens",
    "cfb",
    "nba",
    "wnba",
    "nfl",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill ESPN game boxes (WP10 stub)")
    p.add_argument(
        "--league",
        required=True,
        choices=SUPPORTED_LEAGUES,
        help="League key (ncaab_mens, cfb, …)",
    )
    p.add_argument(
        "--season-year",
        type=int,
        required=True,
        help="Season year in Gravity convention (end year for basketball)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Max games to process this run (default 50)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Log plan only; do not open DB or call ESPN",
    )
    return p.parse_args(argv)


async def run(
    *,
    league: str,
    season_year: int,
    limit: int,
    dry_run: bool,
) -> dict:
    """Stub entrypoint: validate scope and report what a full run would do."""
    summary = {
        "league": league,
        "season_year": season_year,
        "limit": limit,
        "dry_run": dry_run,
        "games_seen": 0,
        "games_upserted": 0,
        "box_rows_upserted": 0,
        "stub": True,
        "notes": [
            "Scoreboard enumeration + ESPN summary fetch not yet wired.",
            "Acceptance (NCAAB season box pts sum check) needs live DB + full crawl.",
        ],
    }
    logger.info(
        "WP10 backfill stub league=%s season_year=%s limit=%s dry_run=%s",
        league,
        season_year,
        limit,
        dry_run,
    )
    if dry_run:
        return summary

    dsn = (os.environ.get("PG_DSN") or os.environ.get("DATABASE_URL") or "").strip()
    if not dsn:
        logger.warning("PG_DSN/DATABASE_URL unset — stub exit without DB work")
        summary["notes"].append("No PG_DSN; skipped DB connection")
        return summary

    import asyncpg

    from gravity_api.scrapers.clients.espn_games import EspnGamesClient

    # Client constructed so imports / wiring stay live; crawl not started yet.
    _client = EspnGamesClient()
    del _client

    conn = await asyncpg.connect(dsn)
    try:
        # Presence check: migration 039 applied?
        exists = await conn.fetchval(
            """SELECT EXISTS (
                 SELECT 1 FROM information_schema.tables
                 WHERE table_schema = 'public' AND table_name = 'games'
               )"""
        )
        if not exists:
            logger.error("games table missing — apply migrations/039_games.sql")
            summary["notes"].append("games table missing")
            return summary
        logger.info("games table present; full crawl still stubbed (limit=%s)", limit)
    finally:
        await conn.close()
    return summary


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = asyncio.run(
        run(
            league=args.league,
            season_year=args.season_year,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    )
    logger.info("done: %s", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
