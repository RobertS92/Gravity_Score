#!/usr/bin/env python3
"""Retry scoring for athletes that failed with Postgres statement timeout."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import asyncpg

from gravity_api.services.sport_pipeline.run import run_athlete_pipeline

FAILED_IDS = (
    "501bebf6-b28a-4bd0-94af-b936552174c9",
    "0959ad68-0000-0000-0000-000000000000",  # placeholder - use prefixes from log
)

# Resolved from cfb_rescore.log error prefixes (full UUIDs from DB lookup)
PREFIXES = ("501bebf6", "0959ad68", "881f1a4a", "549702d2", "e9a87ef8")


async def main_async() -> int:
    dsn = os.environ.get("PG_DSN")
    if not dsn:
        raise SystemExit("PG_DSN required")
    logging.basicConfig(level=logging.INFO)
    conn = await asyncpg.connect(dsn, command_timeout=300)
    ok = fail = 0
    try:
        rows = await conn.fetch(
            """SELECT id::text FROM athletes
               WHERE sport = 'cfb'
                 AND substring(id::text, 1, 8) = ANY($1::text[])""",
            list(PREFIXES),
        )
        ids = [r["id"] for r in rows]
        if len(ids) < len(PREFIXES):
            logging.warning("Found %d/%d athletes by prefix", len(ids), len(PREFIXES))
        for aid in ids:
            try:
                await run_athlete_pipeline(conn, aid, score=True)
                logging.info("OK %s", aid)
                ok += 1
            except Exception as exc:
                logging.error("FAIL %s: %s", aid, exc)
                fail += 1
    finally:
        await conn.close()
    logging.info("Retry complete: ok=%d fail=%d", ok, fail)
    return 0 if fail == 0 else 1


def main() -> None:
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
