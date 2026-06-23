"""
ESPN roster sync — seeds/updates athletes from official rosters.

Run manually:
  PYTHONPATH=. python3 -m gravity_api.jobs.roster_sync
  PYTHONPATH=. python3 -m gravity_api.jobs.roster_sync --sport cfb --team-ids 61,333
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

from gravity_api.scrapers.orchestrator import run_scrapers_for_athlete
from gravity_api.scrapers.roster.school_index import default_team_ids_for_sport
from gravity_api.services.roster_sync import sync_power5_sports, sync_sport_rosters

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def _rescrape_transfer(conn: asyncpg.Connection, athlete_id: str) -> None:
    await run_scrapers_for_athlete(
        conn,
        athlete_id,
        event_type="roster_sync",
        score_after=True,
    )


async def main_async(
    *,
    sport: str | None,
    sports: list[str] | None,
    team_ids: list[str] | None,
    roster_season: str | None,
    rescrape: bool,
) -> None:
    dsn = os.environ.get("PG_DSN")
    if not dsn:
        raise RuntimeError("PG_DSN required")

    conn = await asyncpg.connect(dsn)
    rescrape_fn = _rescrape_transfer if rescrape else None
    try:
        if team_ids and sport:
            result = await sync_sport_rosters(
                conn,
                sport,
                team_ids,
                roster_season=roster_season,
                rescrape_transfers=rescrape_fn,
            )
            logger.info("Roster sync done: %s", result)
        else:
            want = sports or ([sport] if sport else None)
            results = await sync_power5_sports(
                conn,
                want,
                roster_season=roster_season,
                rescrape_transfers=rescrape_fn,
            )
            logger.info("Roster sync complete: %d sport(s)", len(results))
            for r in results:
                logger.info(
                    "  %s: %s snapshots, events=%s",
                    r.get("sport"),
                    r.get("snapshots_written"),
                    r.get("diff_event_counts"),
                )
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="ESPN roster sync")
    parser.add_argument("--sport", default=os.getenv("ROSTER_SYNC_DEFAULT_SPORT", "cfb"))
    parser.add_argument(
        "--sports",
        default=os.getenv(
            "ROSTER_SYNC_SPORTS",
            "cfb,ncaab_mens,ncaab_womens,ncaa_baseball,ncaa_volleyball,nfl,nba,wnba",
        ),
        help="Comma-separated sports when syncing full index",
    )
    parser.add_argument(
        "--team-ids",
        default="",
        help="ESPN team ids (comma-separated); default from ROSTER_SYNC_DEFAULT_TEAM_IDS or school index",
    )
    parser.add_argument("--roster-season", default=None)
    parser.add_argument(
        "--no-rescrape",
        action="store_true",
        help="Skip post-transfer micro-scrape",
    )
    args = parser.parse_args()

    team_ids = [t.strip() for t in args.team_ids.split(",") if t.strip()]
    sports = [s.strip() for s in args.sports.split(",") if s.strip()] or None
    if not team_ids and not sports and args.sport:
        team_ids = default_team_ids_for_sport(args.sport)

    asyncio.run(
        main_async(
            sport=args.sport if team_ids and not sports else None,
            sports=sports,
            team_ids=team_ids or None,
            roster_season=args.roster_season,
            rescrape=not args.no_rescrape,
        )
    )


if __name__ == "__main__":
    main()
