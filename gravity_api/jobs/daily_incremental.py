"""Placeholder job: social/news ingestion runs from the external scrapers repository."""

import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_daily_incremental() -> None:
    dsn = os.environ.get("PG_DSN")
    if not dsn:
        raise RuntimeError("PG_DSN required")
    logger.info(
        "daily_incremental: no-op in monorepo — scheduled scrapes run via "
        "gravity-scrapers (GitHub Actions → POST /jobs/daily). "
        "See docs/PLATFORM_PRODUCTION_AND_ROSTER_OPS.md."
    )


if __name__ == "__main__":
    asyncio.run(run_daily_incremental())
