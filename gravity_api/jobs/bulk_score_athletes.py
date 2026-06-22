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
from gravity_api.services.sport_pipeline.nightly import rebuild_cohorts_for_sport

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def run_bulk(
    limit: int = 500,
    sport: str | None = None,
    concurrency: int = 8,
    *,
    rescore_fallback: bool = False,
    rebuild_cohorts: bool = False,
) -> None:
    dsn = os.environ["PG_DSN"]
    settings = get_settings()
    ml_url = settings.ml_service_url
    if not ml_url or not settings.ml_api_key:
        logger.error(
            "Set ML_SERVICE_URL and ML_SERVICE_API_KEY in .env (e.g. "
            "https://gravity-ml-production.up.railway.app). "
            "If you exported ML_API_KEY from gravity-scrapers, unset it — that key is different."
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

    if rebuild_cohorts:
        from gravity_api.services.sport_pipeline.config import ALL_SPORT_PIPELINES

        sports = [sport] if sport else list(ALL_SPORT_PIPELINES.keys())
        for s in sports:
            try:
                n = await rebuild_cohorts_for_sport(conn, s)
                logger.info("Cohort rebuild %s: %d baseline rows", s, n)
            except Exception as exc:
                logger.warning("Cohort rebuild failed for %s: %s", s, exc)

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

    # Post-run dispersion check: report the dollar/gravity spread on the
    # rows we just produced so operators can confirm the A-grade gates
    # (stddev dollar_p50_usd > 200K on SEC QBs, fallback share <40%).
    if ok:
        report_conn = await asyncpg.connect(dsn)
        try:
            await _log_dispersion_report(report_conn, sport=sport)
        finally:
            await report_conn.close()


async def _log_dispersion_report(
    conn: asyncpg.Connection,
    *,
    sport: str | None,
) -> None:
    """Log model-version mix + dollar/gravity dispersion for the last hour."""
    sport_clause = "AND a.sport = $1" if sport else ""
    params: list = [sport] if sport else []
    mix = await conn.fetch(
        f"""SELECT s.model_version, COUNT(*)::int AS n
              FROM athlete_gravity_scores s
              JOIN athletes a ON a.id = s.athlete_id
             WHERE s.calculated_at > NOW() - INTERVAL '1 hour'
               {sport_clause}
             GROUP BY 1
             ORDER BY n DESC""",
        *params,
    )
    if not mix:
        logger.warning("dispersion: no scores recorded in last hour")
        return
    total = sum(int(r["n"]) for r in mix)
    for r in mix:
        logger.info(
            "dispersion model_version=%s n=%d (%.1f%%)",
            r["model_version"],
            r["n"],
            100.0 * int(r["n"]) / max(total, 1),
        )
    fallback_share = (
        sum(int(r["n"]) for r in mix if "fallback" in (r["model_version"] or "").lower())
        / max(total, 1)
    )
    logger.info("dispersion fallback_share=%.1f%%", 100.0 * fallback_share)

    spread = await conn.fetchrow(
        f"""SELECT
              STDDEV_POP(s.dollar_p50_usd)::float AS stddev_p50,
              MAX(s.dollar_p50_usd) - MIN(s.dollar_p50_usd) AS spread_p50,
              STDDEV_POP(s.gravity_score)::float AS stddev_gravity
            FROM athlete_gravity_scores s
            JOIN athletes a ON a.id = s.athlete_id
           WHERE s.calculated_at > NOW() - INTERVAL '1 hour'
             AND s.dollar_p50_usd IS NOT NULL
             {sport_clause}""",
        *params,
    )
    if spread:
        logger.info(
            "dispersion stddev_p50=%.0f spread_p50=%.0f stddev_gravity=%.2f",
            spread["stddev_p50"] or 0.0,
            spread["spread_p50"] or 0.0,
            spread["stddev_gravity"] or 0.0,
        )
        stddev_p50 = spread["stddev_p50"] or 0.0
        if stddev_p50 < 50_000:
            logger.warning(
                "dollar_p50 stddev < $50K — model may be collapsing or fallback-only"
            )
        elif stddev_p50 < 200_000:
            # Above the collapse floor but below the A-grade dispersion target
            # (≈$200K on a tight cohort like SEC QBs). Informational, not a
            # failure — useful for tracking model-quality drift over time.
            logger.info(
                "dollar_p50 stddev $%.0f below A-grade target ($200K)", stddev_p50
            )


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
    ap.add_argument(
        "--rebuild-cohorts",
        action="store_true",
        help="Rebuild gravity_cohort_baselines before scoring",
    )
    args = ap.parse_args()
    asyncio.run(
        run_bulk(
            args.limit,
            args.sport,
            args.concurrency,
            rescore_fallback=args.rescore_fallback,
            rebuild_cohorts=args.rebuild_cohorts,
        )
    )


if __name__ == "__main__":
    main()
