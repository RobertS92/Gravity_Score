"""
Bulk score all athletes from the DB through the gravity-ml service.
Writes rows to athlete_gravity_scores table.

Run:
  PYTHONPATH=. .venv/bin/python -m gravity_api.jobs.bulk_score_athletes
  PYTHONPATH=. .venv/bin/python -m gravity_api.jobs.bulk_score_athletes --rescore-fallback
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

import httpx

from gravity_api.config import get_settings
from gravity_api.services.athlete_score_sync import sync_athlete_score_from_ml
from gravity_api.services.team_conferences import refresh_athlete_conference_backfill

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def run_bulk(
    limit: int = 500,
    sport: str | None = None,
    concurrency: int = 8,
    *,
    rescore_fallback: bool = False,
) -> None:
    dsn = os.environ["PG_DSN"]
    settings = get_settings()
    ml_url = settings.ml_service_url
    if not ml_url or not settings.ml_api_key:
        logger.error(
            "Set ML_SERVICE_URL and ML_API_KEY in .env (e.g. "
            "https://gravity-ml-production.up.railway.app)"
        )
        raise SystemExit(1)
    headers = {"Authorization": f"Bearer {settings.ml_api_key}"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(f"{ml_url}/health/ready", headers=headers)
            r.raise_for_status()
            ready = r.json()
            logger.info(
                "ML service reachable at %s (model_bundle=%s)",
                ml_url,
                ready.get("model_bundle"),
            )
            if not ready.get("model_bundle"):
                logger.warning(
                    "ML reports no bundle on disk — scores may use composite fallback"
                )
    except Exception as exc:
        logger.error(
            "Cannot reach ML at %s (%s). Fix ML_SERVICE_URL in .env — "
            "use https://gravity-ml-production.up.railway.app",
            ml_url,
            exc,
        )
        raise SystemExit(1) from exc

    conn = await asyncpg.connect(dsn)

    # Conference backfill runs before scoring so cohort cohorts in CSC
    # reports built later see the freshest mapping. Failures here are
    # logged but do not block the scoring sweep.
    try:
        backfill_counts = await refresh_athlete_conference_backfill(conn)
        logger.info(
            "Conference backfill: %d athletes updated, %d unmapped athletes logged",
            backfill_counts["athletes_updated"],
            backfill_counts["issues_logged"],
        )
    except Exception as exc:
        logger.warning("Conference backfill failed (non-fatal): %s", exc)

    try:
        sport_clause = "AND a.sport = $1" if sport else ""

        if rescore_fallback:
            # Re-score athletes whose latest row used heuristic/composite fallback.
            params: list = [limit]
            if sport:
                params.append(sport)
            rows = await conn.fetch(
                f"""
                SELECT a.id FROM athletes a
                INNER JOIN LATERAL (
                    SELECT model_version FROM athlete_gravity_scores
                    WHERE athlete_id = a.id
                    ORDER BY calculated_at DESC LIMIT 1
                ) s ON true
                WHERE (a.is_active IS TRUE)
                  AND (
                    s.model_version ILIKE '%fallback%'
                    OR s.model_version = 'ml_sync'
                  )
                  {sport_clause.replace("$1", "$2") if sport else ""}
                ORDER BY a.updated_at DESC
                LIMIT $1
                """,
                *params,
            )
        else:
            # Score active athletes without any score row.
            params = [sport] if sport else []
            rows = await conn.fetch(
                f"""
                SELECT a.id FROM athletes a
                LEFT JOIN LATERAL (
                    SELECT athlete_id FROM athlete_gravity_scores
                    WHERE athlete_id = a.id
                    ORDER BY calculated_at DESC LIMIT 1
                ) s ON true
                WHERE s.athlete_id IS NULL
                  AND (a.is_active IS TRUE)
                  {sport_clause}
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
    ap.add_argument(
        "--rescore-fallback",
        action="store_true",
        help="Re-score athletes whose latest model_version contains 'fallback'",
    )
    args = ap.parse_args()
    asyncio.run(
        run_bulk(
            args.limit,
            args.sport,
            args.concurrency,
            rescore_fallback=args.rescore_fallback,
        )
    )


if __name__ == "__main__":
    main()
