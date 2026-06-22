"""
Bulk scrape + cohort rebuild for athletes already scraped (post bulk scrape pass).

Run after external gravity-scrapers bulk job completes:
  PYTHONPATH=. python3 -m gravity_api.jobs.bulk_scrape_pipeline --rebuild-cohorts
  PYTHONPATH=. python3 -m gravity_api.jobs.bulk_scrape_pipeline --sport cfb --limit 200
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

load_dotenv()

import asyncpg

from gravity_api.services.sport_pipeline.config import ALL_SPORT_PIPELINES
from gravity_api.services.sport_pipeline.nightly import rebuild_cohorts_for_sport, run_nightly_for_sport

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def rebuild_all_cohorts(conn: asyncpg.Connection) -> dict[str, int]:
    totals: dict[str, int] = {}
    for sport in ALL_SPORT_PIPELINES:
        n = await rebuild_cohorts_for_sport(conn, sport)
        totals[sport] = n
        logger.info("Cohort rebuild %s: %d baseline rows", sport, n)
    return totals


async def run(
    *,
    sport: str | None,
    limit: int,
    rebuild_cohorts: bool,
    score: bool,
    scrape: bool,
) -> None:
    dsn = os.environ["PG_DSN"]
    conn = await asyncpg.connect(dsn)
    try:
        if rebuild_cohorts:
            if sport:
                n = await rebuild_cohorts_for_sport(conn, sport)
                logger.info("Rebuilt cohorts for %s: %d rows", sport, n)
            else:
                await rebuild_all_cohorts(conn)

        if scrape or score:
            sports = (sport,) if sport else tuple(ALL_SPORT_PIPELINES.keys())
            for s in sports:
                await run_nightly_for_sport(
                    conn,
                    sport=s,
                    athlete_limit=limit,
                    scrape=scrape,
                    rebuild_cohorts=False,
                    score=score,
                )
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sport", default=None)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument(
        "--rebuild-cohorts",
        action="store_true",
        help="Rebuild gravity_cohort_baselines (run after bulk scrape)",
    )
    parser.add_argument("--score", action="store_true", help="Run BPXVR pipeline score")
    parser.add_argument("--scrape", action="store_true", help="Re-scrape stale athletes")
    args = parser.parse_args()

    if not any([args.rebuild_cohorts, args.score, args.scrape]):
        args.rebuild_cohorts = True

    asyncio.run(
        run(
            sport=args.sport,
            limit=args.limit,
            rebuild_cohorts=args.rebuild_cohorts,
            score=args.score,
            scrape=args.scrape,
        )
    )


if __name__ == "__main__":
    main()
