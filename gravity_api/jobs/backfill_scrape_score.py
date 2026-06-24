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

load_dotenv(Path(__file__).parent.parent.parent / ".env", override=True)

import asyncpg

from gravity_api.services.sport_pipeline.nightly import run_nightly_for_sport

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_SPORTS = (
    "cfb",
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


async def _backfill_one_sport(
    conn: asyncpg.Connection,
    sport: str,
    *,
    batch_size: int,
    scrape_concurrency: int,
    score_concurrency: int,
    max_batches: int | None,
    scrape: bool,
    score: bool,
) -> None:
    batches = 0
    while True:
        remaining = await count_unscraped(conn, sport)
        if remaining == 0:
            logger.info("[%s] backfill complete (0 unscraped)", sport)
            break
        if max_batches is not None and batches >= max_batches:
            logger.info(
                "[%s] stopping after %d batches (%d unscraped left)",
                sport,
                batches,
                remaining,
            )
            break
        limit = min(batch_size, remaining)
        logger.info(
            "[%s] batch %d: %d unscraped, processing %d",
            sport,
            batches + 1,
            remaining,
            limit,
        )
        result = await run_nightly_for_sport(
            conn,
            sport=sport,
            athlete_limit=limit,
            scrape_concurrency=scrape_concurrency,
            score_concurrency=score_concurrency,
            scrape=scrape,
            rebuild_cohorts=False,
            score=score,
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


async def run_backfill(
    *,
    sports: tuple[str, ...],
    batch_size: int,
    scrape_concurrency: int,
    score_concurrency: int,
    max_batches: int | None,
    sport_parallel: int,
    scrape: bool,
    score: bool,
) -> None:
    dsn = os.environ.get("PG_DSN", "").strip()
    if not dsn:
        raise RuntimeError("PG_DSN required — set in .env or environment")
    conn = await asyncpg.connect(dsn, command_timeout=120)
    try:
        if sport_parallel <= 1:
            for sport in sports:
                await _backfill_one_sport(
                    conn,
                    sport,
                    batch_size=batch_size,
                    scrape_concurrency=scrape_concurrency,
                    score_concurrency=score_concurrency,
                    max_batches=max_batches,
                    scrape=scrape,
                    score=score,
                )
            return

        sem = asyncio.Semaphore(sport_parallel)

        async def run_sport(sport: str) -> None:
            async with sem:
                sport_conn = await asyncpg.connect(dsn, command_timeout=120)
                try:
                    await _backfill_one_sport(
                        sport_conn,
                        sport,
                        batch_size=batch_size,
                        scrape_concurrency=scrape_concurrency,
                        score_concurrency=score_concurrency,
                        max_batches=max_batches,
                        scrape=scrape,
                        score=score,
                    )
                finally:
                    await sport_conn.close()

        await asyncio.gather(*[run_sport(sp) for sp in sports])
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill scrape+score for unscraped athletes")
    parser.add_argument(
        "--sports",
        default=",".join(DEFAULT_SPORTS),
        help="Comma-separated sports",
    )
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Set both scrape and score concurrency (overrides split defaults)",
    )
    parser.add_argument(
        "--scrape-concurrency",
        type=int,
        default=int(os.environ.get("SCRAPE_CONCURRENCY", "3")),
    )
    parser.add_argument(
        "--score-concurrency",
        type=int,
        default=int(os.environ.get("SCORE_CONCURRENCY", "8")),
    )
    parser.add_argument(
        "--sport-parallel",
        type=int,
        default=int(os.environ.get("SPORT_PARALLEL", "1")),
        help="Number of sports to backfill concurrently (default 1)",
    )
    parser.add_argument("--max-batches", type=int, default=None, help="Max batches per sport")
    parser.add_argument("--scrape-only", action="store_true")
    parser.add_argument("--score-only", action="store_true")
    args = parser.parse_args()
    sports = tuple(s.strip() for s in args.sports.split(",") if s.strip())
    scrape_concurrency = args.scrape_concurrency
    score_concurrency = args.score_concurrency
    if args.concurrency is not None:
        scrape_concurrency = args.concurrency
        score_concurrency = args.concurrency

    scrape = not args.score_only
    score = not args.scrape_only

    asyncio.run(
        run_backfill(
            sports=sports,
            batch_size=args.batch_size,
            scrape_concurrency=scrape_concurrency,
            score_concurrency=score_concurrency,
            max_batches=args.max_batches,
            sport_parallel=args.sport_parallel,
            scrape=scrape,
            score=score,
        )
    )


if __name__ == "__main__":
    main()
