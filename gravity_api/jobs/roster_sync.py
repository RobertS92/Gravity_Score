"""
ESPN roster sync — seeds/updates athletes from official rosters.

Run manually:
  PYTHONPATH=. python3 -m gravity_api.jobs.roster_sync --sports cfb --no-rescrape
  PYTHONPATH=. python3 -m gravity_api.jobs.roster_sync --sport cfb --team-ids 61,333,194,251,228
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
from gravity_api.services.roster_coverage import (
    POWER5_CANARY_TEAM_IDS,
    coverage_report,
)
from gravity_api.services.roster_sync import sync_power5_sports, sync_sport_rosters

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_ATTEMPTS = int(os.getenv("ROSTER_SYNC_ATTEMPTS", "3"))
DEFAULT_BACKOFF_S = float(os.getenv("ROSTER_SYNC_RETRY_BACKOFF_S", "8"))


async def _rescrape_transfer(conn: asyncpg.Connection, athlete_id: str) -> None:
    await run_scrapers_for_athlete(
        conn,
        athlete_id,
        event_type="roster_sync",
        score_after=True,
    )


def _flatten_team_results(payload: dict) -> tuple[str, list[dict]]:
    if "team_results" in payload:
        return str(payload.get("sport") or "cfb"), list(payload.get("team_results") or [])
    for block in payload.get("sports") or []:
        if block.get("sport") == "cfb":
            return "cfb", list(block.get("team_results") or [])
    sports = payload.get("sports") or []
    if sports:
        return str(sports[0].get("sport") or "cfb"), list(sports[0].get("team_results") or [])
    return "cfb", []


async def _run_once(
    conn: asyncpg.Connection,
    *,
    sport: str | None,
    sports: list[str] | None,
    team_ids: list[str] | None,
    roster_season: str | None,
    rescrape: bool,
) -> dict:
    rescrape_fn = _rescrape_transfer if rescrape else None
    if team_ids and sport:
        return await sync_sport_rosters(
            conn,
            sport,
            team_ids,
            roster_season=roster_season,
            rescrape_transfers=rescrape_fn,
        )
    want = sports or ([sport] if sport else None)
    results = await sync_power5_sports(
        conn,
        want,
        roster_season=roster_season,
        rescrape_transfers=rescrape_fn,
    )
    logger.info("Roster sync complete: %d sport(s)", len(results))
    for row in results:
        logger.info(
            "  %s: %s snapshots, retired=%s, events=%s",
            row.get("sport"),
            row.get("snapshots_written"),
            (row.get("retirement") or {}).get("deactivated"),
            row.get("diff_event_counts"),
        )
    return {"sports": results, "count": len(results)}


async def main_async(
    *,
    sport: str | None,
    sports: list[str] | None,
    team_ids: list[str] | None,
    roster_season: str | None,
    rescrape: bool,
    require_coverage: int,
    attempts: int,
) -> dict:
    dsn = os.environ.get("PG_DSN")
    if not dsn:
        raise RuntimeError("PG_DSN required")

    last_error: BaseException | None = None
    last_payload: dict = {}
    for attempt in range(1, max(1, attempts) + 1):
        conn = await asyncpg.connect(dsn, statement_cache_size=0, command_timeout=180)
        try:
            logger.info("Roster sync attempt %s/%s", attempt, attempts)
            payload = await _run_once(
                conn,
                sport=sport,
                sports=sports,
                team_ids=team_ids,
                roster_season=roster_season,
                rescrape=rescrape,
            )
            last_payload = payload
            if require_coverage > 0:
                sport_key, team_results = _flatten_team_results(payload)
                report = coverage_report(
                    team_results,
                    sport=sport_key,
                    min_teams=require_coverage,
                    required_ids=list(POWER5_CANARY_TEAM_IDS)
                    if sport_key == "cfb"
                    else None,
                )
                logger.info("Coverage gate: %s", {k: report[k] for k in ("passed", "complete_teams", "missing_ids")})
                if not report["passed"]:
                    raise RuntimeError(f"roster coverage failed: {report}")
            return payload
        except Exception as exc:
            last_error = exc
            logger.exception("Roster sync attempt %s failed", attempt)
            if attempt >= attempts:
                break
            await asyncio.sleep(DEFAULT_BACKOFF_S * attempt)
        finally:
            await conn.close()
    raise RuntimeError(f"roster sync failed after {attempts} attempt(s): {last_error}") from last_error


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
    parser.add_argument(
        "--require-coverage",
        type=int,
        default=int(os.getenv("ROSTER_SYNC_REQUIRE_COVERAGE", "5")),
        help="Fail unless this many complete Power 5 CFB rosters synced (0 disables)",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=DEFAULT_ATTEMPTS,
        help="Retry the full sync this many times on crash or coverage failure",
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
            require_coverage=args.require_coverage,
            attempts=args.attempts,
        )
    )


if __name__ == "__main__":
    main()
