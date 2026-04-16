"""Placeholder job: roster refresh + scoring run in external scrapers / ML repos."""

import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_weekly_refresh() -> None:
    dsn = os.environ.get("PG_DSN")
    if not dsn:
        raise RuntimeError("PG_DSN required")
    import asyncpg

    from gravity_api.services.comparables import rebuild_comparables_index

    logger.info(
        "weekly_refresh: rebuilding comparable_sets from latest scores "
        "(roster + scoring still run via gravity-scrapers / gravity-ml)."
    )
    conn = await asyncpg.connect(dsn)
    try:
        n = await rebuild_comparables_index(conn)
        logger.info("weekly_refresh: comparables pairs written: %s", n)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_weekly_refresh())
