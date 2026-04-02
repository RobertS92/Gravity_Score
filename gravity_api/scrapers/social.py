"""Social snapshot collection — wire to Firecrawl / free_apis in Phase 1."""

import logging

import asyncpg

logger = logging.getLogger(__name__)


async def collect_social_for_all_athletes(db: asyncpg.Connection) -> None:
    """Collect follower / engagement metrics per athlete (stub)."""
    logger.info(
        "collect_social_for_all_athletes: stub — connect scripts/scrape_social_firecrawl.py"
    )
