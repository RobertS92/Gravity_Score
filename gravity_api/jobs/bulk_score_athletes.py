"""
Bulk score all athletes from the DB through the gravity-ml service.
Writes rows to athlete_gravity_scores table.

Run: python -m gravity_api.jobs.bulk_score_athletes [--limit N] [--sport cfb]
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

from gravity_api.services.athlete_score_sync import sync_athlete_score_from_ml

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def run_bulk(
    limit: int = 500,
    sport: str | None = None,
    concurrency: int = 8,
) -> None:
    dsn = os.environ["PG_DSN"]
    conn = await asyncpg.connect(dsn)

    try:
        where = "WHERE a.gravity_score IS NULL"
        params: list = []
        if sport:
            where += f" AND a.sport = ${len(params)+1}"
            params.append(sport)

        # athletes without a score yet — join on latest gravity_scores
        rows = await conn.fetch(
            f"""
            SELECT a.id FROM athletes a
            LEFT JOIN LATERAL (
                SELECT athlete_id FROM athlete_gravity_scores
                WHERE athlete_id = a.id
                ORDER BY calculated_at DESC LIMIT 1
            ) s ON true
            WHERE s.athlete_id IS NULL
            {"AND a.sport = $1" if sport else ""}
            ORDER BY a.updated_at DESC
            LIMIT {limit}
            """,
            *params,
        )
    except Exception as exc:
        logger.error("Query failed: %s", exc)
        # Simple fallback: just get all athlete IDs
        rows = await conn.fetch(
            "SELECT id FROM athletes ORDER BY updated_at DESC LIMIT $1",
            limit,
        )

    ids = [str(r["id"]) for r in rows]
    logger.info("Scoring %d athletes (concurrency=%d)", len(ids), concurrency)
    await conn.close()

    # Use a pool so concurrent coroutines each get their own connection
    pool = await asyncpg.create_pool(dsn, min_size=2, max_size=concurrency + 2)
    sem = asyncio.Semaphore(concurrency)
    ok = err = 0

    async def score_one(aid: str) -> None:
        nonlocal ok, err
        async with sem:
            async with pool.acquire() as pconn:
                try:
                    result = await sync_athlete_score_from_ml(pconn, aid)
                    g = result.get("gravity_score")
                    logger.info("OK  %s  gravity=%.1f", aid[:8], g or 0)
                    ok += 1
                except Exception as exc:
                    logger.warning("FAIL %s: %s", aid[:8], exc)
                    err += 1

    await asyncio.gather(*[score_one(a) for a in ids])

    await pool.close()
    logger.info("Done: %d ok, %d errors out of %d athletes", ok, err, len(ids))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--sport", default=None)
    ap.add_argument("--concurrency", type=int, default=8)
    args = ap.parse_args()
    asyncio.run(run_bulk(args.limit, args.sport, args.concurrency))


if __name__ == "__main__":
    main()
