"""Batch LLM gap-fill for high-priority college athletes."""

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

from gravity_api.services.llm_gap_fill import (
    is_llm_gap_fill_candidate,
    llm_estimate_nil_commercial,
    reset_run_budget,
)
from gravity_api.scrapers.observations import merge_raw_athlete_data

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main_async(*, sport: str, limit: int) -> None:
    dsn = os.environ.get("PG_DSN")
    if not dsn:
        raise SystemExit("PG_DSN required")
    reset_run_budget()
    conn = await asyncpg.connect(dsn, command_timeout=120)
    try:
        rows = await conn.fetch(
            """SELECT a.id, a.name, a.sport, a.school, a.position, r.raw_data
               FROM athletes a
               JOIN LATERAL (
                 SELECT raw_data FROM raw_athlete_data
                 WHERE athlete_id = a.id ORDER BY scraped_at DESC NULLS LAST LIMIT 1
               ) r ON TRUE
               WHERE a.sport = $1
                 AND COALESCE(a.is_active, TRUE) = TRUE
               ORDER BY
                 COALESCE((r.raw_data->>'recruiting_stars')::float, 0) DESC,
                 COALESCE((r.raw_data->>'instagram_followers')::float, 0) DESC
               LIMIT $2""",
            sport,
            limit,
        )
        written = 0
        for row in rows:
            raw = dict(row["raw_data"] or {})
            if not is_llm_gap_fill_candidate(raw, sport):
                continue
            fields = await llm_estimate_nil_commercial(
                name=str(row["name"]),
                sport=sport,
                school=row["school"],
                position=row["position"],
                raw=raw,
            )
            if fields:
                await merge_raw_athlete_data(conn, athlete_id=str(row["id"]), fields=fields)
                written += 1
                logger.info("LLM gap-fill %s (%s)", row["name"], row["id"])
        logger.info("LLM gap-fill complete: %d athletes updated", written)
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sport", default="cfb")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()
    asyncio.run(main_async(sport=args.sport, limit=args.limit))


if __name__ == "__main__":
    main()
