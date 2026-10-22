"""Backfill per-season athlete_season_stats from ESPN.

Usage::

  PYTHONPATH=. python3 -m gravity_api.jobs.backfill_season_stats --sport nba --limit 20
  PYTHONPATH=. python3 -m gravity_api.jobs.backfill_season_stats --espn-id 1966 --sport nba
  PYTHONPATH=. python3 -m gravity_api.jobs.backfill_season_stats --refresh-season 2025 --sport nba

Default behavior: write missing seasons; always refresh the current in-progress
season; skip completed seasons that already have rows unless ``--refresh-season``
is set.
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

import asyncpg

from gravity_api.scrapers.clients.espn_season_history import (
    EspnSeasonHistoryClient,
    derive_career_from_seasons,
)
from gravity_api.scrapers.parsers.espn_season_year import is_current_espn_season
from gravity_api.services.sport_pipeline.season_stats_store import upsert_season_stat_rows

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_SPORTS = ("nba", "nfl", "cfb", "ncaab_mens", "ncaab_womens")


async def _athletes(
    conn: asyncpg.Connection,
    *,
    sport: str,
    limit: int,
    espn_id: str | None,
) -> list[asyncpg.Record]:
    if espn_id:
        return await conn.fetch(
            """SELECT id, espn_id, sport, position, name
               FROM athletes
               WHERE espn_id = $1 AND sport = $2
               LIMIT $3""",
            str(espn_id),
            sport,
            limit,
        )
    return await conn.fetch(
        """SELECT id, espn_id, sport, position, name
           FROM athletes
           WHERE sport = $1
             AND espn_id IS NOT NULL
             AND COALESCE(is_active, TRUE)
           ORDER BY updated_at DESC NULLS LAST
           LIMIT $2""",
        sport,
        limit,
    )


async def backfill_one(
    conn: asyncpg.Connection,
    row: asyncpg.Record,
    *,
    refresh_years: set[int],
    current_only: bool,
) -> dict:
    client = EspnSeasonHistoryClient()
    espn_id = str(row["espn_id"])
    sport = str(row["sport"])
    seasons = await client.fetch_season_rows(espn_id, sport)
    if current_only:
        seasons = [
            s for s in seasons if is_current_espn_season(s.espn_season_year, sport)
        ] or seasons[-1:]
    written = await upsert_season_stat_rows(
        conn,
        athlete_id=str(row["id"]),
        rows=seasons,
        position=row.get("position"),
        refresh_season_years=refresh_years,
        current_only=False,
    )
    career = derive_career_from_seasons(seasons)
    return {
        "athlete_id": str(row["id"]),
        "name": row.get("name"),
        "espn_id": espn_id,
        "sport": sport,
        "season_rows": len(seasons),
        "written": written,
        "career_gp": career.get("games_played_career"),
    }


async def main_async(args: argparse.Namespace) -> int:
    dsn = os.environ.get("PG_DSN", "").strip()
    if not dsn:
        logger.error("PG_DSN is required")
        return 2

    refresh_years = {int(y) for y in (args.refresh_season or [])}
    sports = [args.sport] if args.sport else list(DEFAULT_SPORTS)
    conn = await asyncpg.connect(dsn, command_timeout=180)
    try:
        for sport in sports:
            rows = await _athletes(
                conn, sport=sport, limit=args.limit, espn_id=args.espn_id
            )
            logger.info("[%s] %d athletes", sport, len(rows))
            for row in rows:
                try:
                    summary = await backfill_one(
                        conn,
                        row,
                        refresh_years=refresh_years,
                        current_only=args.current_only,
                    )
                    logger.info(
                        "[%s] %s seasons=%s written=%s career_gp=%s",
                        sport,
                        summary.get("name") or summary["espn_id"],
                        summary["season_rows"],
                        summary["written"],
                        summary.get("career_gp"),
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "[%s] %s failed: %s", sport, row.get("espn_id"), exc
                    )
    finally:
        await conn.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sport", default=None, help="Single sport key")
    p.add_argument("--espn-id", default=None, help="Backfill one ESPN id")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument(
        "--refresh-season",
        action="append",
        default=[],
        help="ESPN season year to force-refresh (repeatable). "
        "Completed seasons are otherwise write-once.",
    )
    p.add_argument(
        "--current-only",
        action="store_true",
        help="Only scrape/write the current in-progress season (scheduled path).",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
