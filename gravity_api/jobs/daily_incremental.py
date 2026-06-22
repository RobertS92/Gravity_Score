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

    logger.info("daily_incremental → nightly_pipeline (all sports)")
    await main_async(
        sport=None,
        limit=int(os.environ.get("NIGHTLY_ATHLETE_LIMIT", "50")),
        concurrency=int(os.environ.get("NIGHTLY_CONCURRENCY", "4")),
        skip_scrape=False,
        skip_cohorts=False,
        skip_score=True,
    )


if __name__ == "__main__":
    asyncio.run(run_daily_incremental())
