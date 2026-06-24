"""Backfill career / multi-season stats for athletes with ESPN IDs."""

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

from gravity_api.scrapers.orchestrator import run_scrapers_for_athlete
from gravity_api.services.sport_pipeline.run import run_athlete_pipeline

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


async def fetch_athletes_needing_career_stats(
    conn: asyncpg.Connection,
    *,
    sport: str,
    limit: int,
) -> list[str]:
    rows = await conn.fetch(
        """SELECT a.id
           FROM athletes a
           LEFT JOIN LATERAL (
             SELECT raw_data FROM raw_athlete_data
             WHERE athlete_id = a.id
             ORDER BY scraped_at DESC NULLS LAST LIMIT 1
           ) r ON TRUE
           WHERE a.sport = $1
             AND COALESCE(a.is_active, TRUE)
             AND (
               r.raw_data IS NULL
               OR NOT (r.raw_data ? 'season_stats_history')
               OR jsonb_typeof(r.raw_data->'season_stats_history') = 'null'
               OR r.raw_data->'season_stats_history' = '{}'::jsonb
             )
           ORDER BY a.updated_at DESC NULLS LAST
           LIMIT $2""",
        sport,
        limit,
    )
    return [str(r["id"]) for r in rows]


async def backfill_sport(
    conn: asyncpg.Connection,
    sport: str,
    *,
    batch_size: int,
    concurrency: int,
    max_batches: int | None,
    score_after: bool,
) -> None:
    sem = asyncio.Semaphore(concurrency)
    batches = 0
    while True:
        ids = await fetch_athletes_needing_career_stats(conn, sport, limit=batch_size)
        if not ids:
            logger.info("[%s] career stats backfill complete", sport)
            break
        if max_batches is not None and batches >= max_batches:
            logger.info("[%s] stopping after %d batches", sport, batches)
            break

        async def one(athlete_id: str) -> None:
            async with sem:
                try:
                    await run_scrapers_for_athlete(
                        conn,
                        athlete_id,
                        event_type="scheduled_full",
                        score_after=False,
                    )
                    if score_after:
                        await run_athlete_pipeline(conn, athlete_id, score=True)
                except Exception as exc:
                    logger.warning("[%s] athlete %s failed: %s", sport, athlete_id, exc)

        await asyncio.gather(*[one(aid) for aid in ids])
        logger.info("[%s] batch %d processed %d athletes", sport, batches + 1, len(ids))
        batches += 1


async def run_backfill(
    *,
    sports: tuple[str, ...],
    batch_size: int,
    concurrency: int,
    max_batches: int | None,
    sport_parallel: int,
    score_after: bool,
) -> None:
    dsn = os.environ.get("PG_DSN", "").strip()
    if not dsn:
        raise RuntimeError("PG_DSN required")

    if sport_parallel <= 1:
        conn = await asyncpg.connect(dsn, command_timeout=120)
        try:
            for sport in sports:
                await backfill_sport(
                    conn,
                    sport,
                    batch_size=batch_size,
                    concurrency=concurrency,
                    max_batches=max_batches,
                    score_after=score_after,
                )
        finally:
            await conn.close()
        return

    sem = asyncio.Semaphore(sport_parallel)

    async def sport_task(sport: str) -> None:
        async with sem:
            conn = await asyncpg.connect(dsn, command_timeout=120)
            try:
                await backfill_sport(
                    conn,
                    sport,
                    batch_size=batch_size,
                    concurrency=concurrency,
                    max_batches=max_batches,
                    score_after=score_after,
                )
            finally:
                await conn.close()

    await asyncio.gather(*[sport_task(sp) for sp in sports])


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill multi-season stats into raw_athlete_data")
    parser.add_argument("--sports", default=",".join(DEFAULT_SPORTS))
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=int(os.environ.get("SCRAPE_CONCURRENCY", "3")))
    parser.add_argument("--max-batches", type=int, default=None)
    parser.add_argument("--sport-parallel", type=int, default=1)
    parser.add_argument("--score-after", action="store_true")
    args = parser.parse_args()
    sports = tuple(s.strip() for s in args.sports.split(",") if s.strip())
    asyncio.run(
        run_backfill(
            sports=sports,
            batch_size=args.batch_size,
            concurrency=args.concurrency,
            max_batches=args.max_batches,
            sport_parallel=args.sport_parallel,
            score_after=args.score_after,
        )
    )


if __name__ == "__main__":
    main()
