"""Placeholder job: roster sync + comparables rebuild."""

import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_weekly_refresh(*, skip_roster: bool = False) -> None:
    dsn = os.environ.get("PG_DSN")
    if not dsn:
        raise RuntimeError("PG_DSN required")
    import asyncpg

    from gravity_api.services.comparables import rebuild_comparables_index

    conn = await asyncpg.connect(dsn)
    try:
        if not skip_roster and os.environ.get("WEEKLY_SKIP_ROSTER_SYNC", "").lower() not in (
            "1",
            "true",
            "yes",
        ):
            from gravity_api.services.roster_sync import sync_power5_sports

            logger.info("weekly_refresh: roster sync (in-process)")
            await sync_power5_sports(conn, rescrape_transfers=None)

        logger.info("weekly_refresh: rebuilding comparable_sets from latest scores")
        n = await rebuild_comparables_index(conn)
        logger.info("weekly_refresh: comparables pairs written: %s", n)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_weekly_refresh())
