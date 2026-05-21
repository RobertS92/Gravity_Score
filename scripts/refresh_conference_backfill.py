"""
Standalone conference backfill — reapplies migration 022's mapping pass without
running the full bulk scoring job.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/refresh_conference_backfill.py
    PYTHONPATH=. .venv/bin/python scripts/refresh_conference_backfill.py --report

When ``--report`` is set, prints the post-backfill coverage by sport so we can
verify the >=95% CFB target before redeploying scoring.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import asyncpg  # noqa: E402

from gravity_api.services.team_conferences import (  # noqa: E402
    list_unmapped_athletes,
    refresh_athlete_conference_backfill,
)

logger = logging.getLogger("refresh_conference_backfill")


async def _coverage_report(conn: asyncpg.Connection) -> None:
    rows = await conn.fetch(
        """SELECT
              a.sport,
              COUNT(*) FILTER (WHERE a.conference IS NOT NULL AND TRIM(a.conference) <> '')::int AS mapped,
              COUNT(*)::int                                                                       AS total
           FROM athletes a
           GROUP BY a.sport
           ORDER BY a.sport"""
    )
    for r in rows:
        mapped = r["mapped"] or 0
        total = r["total"] or 0
        pct = (mapped / total * 100.0) if total else 0.0
        logger.info(
            "sport=%s mapped=%d/%d (%.1f%%)", r["sport"], mapped, total, pct
        )


async def main_async(*, report: bool) -> None:
    dsn = os.environ["PG_DSN"]
    conn = await asyncpg.connect(dsn)
    try:
        counts = await refresh_athlete_conference_backfill(conn)
        logger.info(
            "athletes_updated=%d issues_logged=%d",
            counts["athletes_updated"],
            counts["issues_logged"],
        )
        if report:
            await _coverage_report(conn)
            for sport in ("cfb", "ncaab"):
                misses = await list_unmapped_athletes(conn, sport=sport)
                logger.info(
                    "%s unmapped athletes: %d (sample %s)",
                    sport,
                    len(misses),
                    [m.get("school") for m in misses[:10]],
                )
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh athlete conference backfill")
    parser.add_argument("--report", action="store_true", help="Print coverage summary")
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    asyncio.run(main_async(report=args.report))


if __name__ == "__main__":
    main()
