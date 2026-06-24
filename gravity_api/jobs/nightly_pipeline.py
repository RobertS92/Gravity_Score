"""
Nightly pipeline: per-sport stale scrape → cohort rebuild → BPXVR score.

Run manually:
  PYTHONPATH=. python3 -m gravity_api.jobs.nightly_pipeline
  PYTHONPATH=. python3 -m gravity_api.jobs.nightly_pipeline --sport cfb --limit 50
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

from gravity_api.services.sport_pipeline.nightly import run_nightly_all_sports, run_nightly_for_sport

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main_async(
    *,
    sport: str | None,
    limit: int,
    concurrency: int | None,
    scrape_concurrency: int,
    score_concurrency: int,
    sport_parallel: int,
    skip_scrape: bool,
    skip_cohorts: bool,
    skip_score: bool,
) -> None:
    dsn = os.environ.get("PG_DSN")
    if not dsn:
        raise RuntimeError("PG_DSN required")

    conn = await asyncpg.connect(dsn, command_timeout=120)
    try:
        if sport:
            result = await run_nightly_for_sport(
                conn,
                sport=sport,
                athlete_limit=limit,
                concurrency=concurrency,
                scrape_concurrency=scrape_concurrency,
                score_concurrency=score_concurrency,
                scrape=not skip_scrape,
                rebuild_cohorts=not skip_cohorts,
                score=not skip_score,
            )
            logger.info("Done %s: %s", sport, result)
        else:
            summary = await run_nightly_all_sports(
                conn,
                athlete_limit_per_sport=limit,
                concurrency=concurrency,
                scrape_concurrency=scrape_concurrency,
                score_concurrency=score_concurrency,
                sport_parallel=sport_parallel,
            )
            logger.info("Nightly complete: %s", summary)
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Nightly sport pipeline")
    parser.add_argument("--sport", default=None, help="Single sport; default all 8")
    parser.add_argument("--limit", type=int, default=100, help="Max stale athletes per sport")
    parser.add_argument("--concurrency", type=int, default=None, help="Override scrape+score concurrency")
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
    )
    parser.add_argument("--skip-scrape", action="store_true")
    parser.add_argument("--skip-cohorts", action="store_true")
    parser.add_argument("--skip-score", action="store_true")
    args = parser.parse_args()
    asyncio.run(
        main_async(
            sport=args.sport,
            limit=args.limit,
            concurrency=args.concurrency,
            scrape_concurrency=args.scrape_concurrency,
            score_concurrency=args.score_concurrency,
            sport_parallel=args.sport_parallel,
            skip_scrape=args.skip_scrape,
            skip_cohorts=args.skip_cohorts,
            skip_score=args.skip_score,
        )
    )


if __name__ == "__main__":
    main()
