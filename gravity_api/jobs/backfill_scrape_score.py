"""Backfill scrape + score for athletes missing raw_athlete_data."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

load_dotenv()

import asyncpg

from gravity_api.services.sport_pipeline.nightly import run_nightly_for_sport

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_SPORTS = (
    "nfl",
    "ncaab_mens",
    "ncaab_womens",
    "ncaa_baseball",
    "ncaa_volleyball",
    "nba",
    "wnba",
)


async def count_unscraped(conn: asyncpg.Connection, sport: str) -> int:
    return int(
        await conn.fetchval(
            """SELECT COUNT(*)::int FROM athletes a
               WHERE a.sport = $1 AND COALESCE(a.is_active, TRUE)
                 AND NOT EXISTS (
                   SELECT 1 FROM raw_athlete_data r WHERE r.athlete_id = a.id
                 )""",
            sport,
        )
        or 0
    )


async def run_backfill(
    *,
    sports: tuple[str, ...],
    batch_size: int,
    concurrency: int,
    max_batches: int | None,
) -> None:
    dsn = os.environ["PG_DSN"]
    conn = await asyncpg.connect(dsn)
    try:
        for sport in sports:
            batches = 0
            while True:
                remaining = await count_unscraped(conn, sport)
                if remaining == 0:
                    logger.info("[%s] backfill complete (0 unscraped)", sport)
                    break
                if max_batches is not None and batches >= max_batches:
                    logger.info("[%s] stopping after %d batches (%d unscraped left)", sport, batches, remaining)
                    break
                limit = min(batch_size, remaining)
                logger.info("[%s] batch %d: %d unscraped, processing %d", sport, batches + 1, remaining, limit)
                result = await run_nightly_for_sport(
                    conn,
                    sport=sport,
                    athlete_limit=limit,
                    concurrency=concurrency,
                    scrape=True,
                    rebuild_cohorts=False,
                    score=True,
                )
                logger.info(
                    "[%s] scraped ok=%d fail=%d scored ok=%d fail=%d",
                    sport,
                    result.scraped_ok,
                    result.scraped_fail,
                    result.scored_ok,
                    result.scored_fail,
                )
                batches += 1
                if result.scraped_ok == 0 and result.scored_ok == 0:
                    logger.error("[%s] no progress in batch; stopping", sport)
                    break
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill scrape+score for unscraped athletes")
    parser.add_argument(
        "--sports",
        default=",".join(DEFAULT_SPORTS),
        help="Comma-separated sports (default: nfl,ncaab_mens,ncaab_womens,nba,wnba)",
    )
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--max-batches", type=int, default=None, help="Max batches per sport (default: until done)")
    args = parser.parse_args()
    sports = tuple(s.strip() for s in args.sports.split(",") if s.strip())
    asyncio.run(
        run_backfill(
            sports=sports,
            batch_size=args.batch_size,
            concurrency=args.concurrency,
            max_batches=args.max_batches,
        )
    )


if __name__ == "__main__":
    main()
