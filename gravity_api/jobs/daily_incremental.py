"""Placeholder job — delegates to nightly_pipeline."""

import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_daily_incremental() -> None:
    from gravity_api.jobs.nightly_pipeline import main_async

    logger.info("daily_incremental → nightly_pipeline (stale athletes, all sports)")
    concurrency = int(os.environ.get("NIGHTLY_CONCURRENCY", "4"))
    # Prefer stale-mode scheduled_full over gap-fill-only so follower/stats
    # refresh on a cadence. Set DAILY_GAP_FILL=1 to keep hole-filling behavior.
    gap_fill = os.environ.get("DAILY_GAP_FILL", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    await main_async(
        sport=None,
        sports=None,
        limit=int(os.environ.get("NIGHTLY_ATHLETE_LIMIT", "50")),
        concurrency=concurrency,
        scrape_concurrency=concurrency,
        score_concurrency=int(os.environ.get("SCORE_CONCURRENCY", "8")),
        sport_parallel=int(os.environ.get("SPORT_PARALLEL", "1")),
        skip_scrape=False,
        skip_cohorts=False,
        skip_score=False,
        gap_fill=gap_fill,
        rescore_all=False,
        scrape_stale_days=int(os.environ.get("SCRAPE_STALE_DAYS", "3")),
        score_stale_days=int(os.environ.get("SCORE_STALE_DAYS", "7")),
    )


if __name__ == "__main__":
    asyncio.run(run_daily_incremental())
