"""CLI: rebuild comparable_sets (run after scores are populated)."""

import asyncio
import logging

import asyncpg

from gravity_api.config import get_settings
from gravity_api.services.comparables import rebuild_comparables_index

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    conn = await asyncpg.connect(settings.pg_dsn)
    try:
        n = await rebuild_comparables_index(conn)
        logger.info("Done: %d comparable pairs", n)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
