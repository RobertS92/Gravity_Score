#!/usr/bin/env python3
"""Prefetch CFBD team W-L records for all CFB schools (one call per team)."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import asyncpg

from gravity_api.config import get_settings
from gravity_api.scrapers.clients.cfbd import CfbdClient, cfbd_is_rate_limited
from gravity_api.services.sport_pipeline.season_stats import _current_season_year
from gravity_api.services.team_season_records import upsert_team_season_stats

logger = logging.getLogger(__name__)


async def main_async() -> int:
    conn = await asyncpg.connect(get_settings().pg_dsn, command_timeout=120)
    client = CfbdClient()
    if not client.enabled:
        raise SystemExit("CFBD_API_KEY required")
    year = _current_season_year()
    schools = await conn.fetch(
        """SELECT DISTINCT school FROM athletes
           WHERE sport = 'cfb' AND school IS NOT NULL AND TRIM(school) <> ''
           ORDER BY school"""
    )
    ok = fail = 0
    try:
        for row in schools:
            school = str(row["school"]).strip()
            if cfbd_is_rate_limited():
                logger.warning("CFBD rate limited after %d teams", ok)
                break
            record = await client.team_record(year=year, team=school)
            if not record:
                fail += 1
                continue
            await upsert_team_season_stats(
                conn,
                sport="cfb",
                team_id=school,
                season_year=year,
                wins=int(record["wins"]),
                losses=int(record["losses"]),
                ties=int(record.get("ties") or 0),
                team_name=str(record.get("team") or school),
                conference_wins=int(record.get("conference_wins") or 0) or None,
                conference_losses=int(record.get("conference_losses") or 0) or None,
                source_key="cfbd",
            )
            ok += 1
            if ok % 25 == 0:
                logger.info("Prefetched %d team records...", ok)
    finally:
        await conn.close()
    logger.info("Done: %d teams cached, %d misses", ok, fail)
    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
