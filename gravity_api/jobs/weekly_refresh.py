"""Weekly full refresh — rosters, social, NIL, scoring, comparables."""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import asyncpg

# Allow `python -m gravity_api.jobs.weekly_refresh` from repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from gravity_api.ml.inference import load_model, score_athlete
from gravity_api.scrapers.cfb_roster import ingest_power5_rosters
from gravity_api.scrapers.nil_deals import ingest_nil_deals_from_connectors
from gravity_api.scrapers.social import collect_social_for_all_athletes
from gravity_api.services.comparables import rebuild_comparables_index

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


async def score_all_athletes(db: asyncpg.Connection) -> None:
    athletes = await db.fetch("SELECT * FROM athletes")
    scored = 0
    failed = 0

    for athlete in athletes:
        try:
            athlete_dict = dict(athlete)
            social = await db.fetchrow(
                """SELECT * FROM social_snapshots
                   WHERE athlete_id = $1
                   ORDER BY scraped_at DESC LIMIT 1""",
                athlete["id"],
            )
            if social:
                athlete_dict.update(dict(social))

            perf = await db.fetchrow(
                """SELECT * FROM athlete_performance_snapshots
                   WHERE athlete_id = $1
                   ORDER BY season DESC, scraped_at DESC LIMIT 1""",
                athlete["id"],
            )
            if perf:
                perf_d = dict(perf)
                athlete_dict.update(perf_d)
                stats = perf_d.get("stats") or {}
                if isinstance(stats, str):
                    stats = json.loads(stats)
                athlete_dict["stats"] = stats

            program = await db.fetchrow(
                """SELECT * FROM programs
                   WHERE school ILIKE $1 AND sport = $2""",
                f"%{athlete['school']}%",
                athlete["sport"],
            )
            if program:
                athlete_dict.update(
                    {
                        "dma_rank": program["dma_rank"],
                        "collective_budget_usd": program["collective_budget_usd"],
                        "annual_tv_appearances": program["annual_tv_appearances"],
                    }
                )

            result = score_athlete(athlete_dict)

            await db.execute(
                """INSERT INTO athlete_gravity_scores
                   (athlete_id, gravity_score, brand_score, proof_score,
                    proximity_score, velocity_score, risk_score,
                    confidence, top_factors_up, top_factors_down, shap_values)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10::jsonb,$11::jsonb)""",
                athlete["id"],
                result["gravity_score"],
                result["brand_score"],
                result["proof_score"],
                result["proximity_score"],
                result["velocity_score"],
                result["risk_score"],
                result["confidence"],
                json.dumps(result["top_factors_up"]),
                json.dumps(result["top_factors_down"]),
                json.dumps(result["shap_values"]),
            )
            scored += 1
        except Exception as e:
            logger.error("Failed to score %s: %s", athlete.get("name"), e)
            failed += 1

    logger.info("Scored %s athletes, %s failed", scored, failed)


async def run_weekly_refresh() -> None:
    dsn = os.environ.get("PG_DSN")
    if not dsn:
        raise RuntimeError("PG_DSN required")

    load_model()
    db = await asyncpg.connect(dsn)

    try:
        logger.info("=== WEEKLY REFRESH START ===")
        logger.info("Step 1: Ingest CFB rosters")
        await ingest_power5_rosters(db, sport="cfb")
        logger.info("Step 2: Ingest MCBB rosters")
        await ingest_power5_rosters(db, sport="mcbb")
        logger.info("Step 3: Collect social data")
        await collect_social_for_all_athletes(db)
        logger.info("Step 4: Ingest NIL deals")
        await ingest_nil_deals_from_connectors(db)
        logger.info("Step 5: Score all athletes")
        await score_all_athletes(db)
        logger.info("Step 6: Rebuild comparables")
        await rebuild_comparables_index(db)
        logger.info("=== WEEKLY REFRESH COMPLETE ===")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(run_weekly_refresh())
