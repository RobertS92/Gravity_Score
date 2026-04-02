"""Daily social + news incremental job (stub)."""

import asyncio
import logging
import os
import sys
from pathlib import Path

import asyncpg

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from gravity_api.scrapers.social import collect_social_for_all_athletes

logging.basicConfig(level=logging.INFO)


async def run_daily_incremental() -> None:
    dsn = os.environ.get("PG_DSN")
    if not dsn:
        raise RuntimeError("PG_DSN required")
    db = await asyncpg.connect(dsn)
    try:
        await collect_social_for_all_athletes(db)
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(run_daily_incremental())
