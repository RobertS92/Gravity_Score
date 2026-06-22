"""Nightly per-sport pipeline: stale scrape → cohort rebuild → score."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import asyncpg

from gravity_api.config import get_settings
from gravity_api.feature_engineering.positions import SPORT_LEAGUE
from gravity_api.feature_engineering.sport_specs import ALL_SPORT_SPECS, get_sport_spec
from gravity_api.jobs.rebuild_cohort_baselines import rebuild_for_cohort
from gravity_api.scrapers.orchestrator import run_scrapers_for_athlete
from gravity_api.services.sport_pipeline.config import ALL_SPORT_PIPELINES
from gravity_api.services.sport_pipeline.run import run_athlete_pipeline
from gravity_api.services.sport_pipeline.season_stats import _current_season_year

logger = logging.getLogger(__name__)


@dataclass
class NightlySportResult:
    sport: str
    stale_found: int = 0
    scraped_ok: int = 0
    scraped_fail: int = 0
    cohort_baselines_written: int = 0
    scored_ok: int = 0
    scored_fail: int = 0
    errors: list[str] = field(default_factory=list)


async def fetch_stale_athlete_ids(
    conn: asyncpg.Connection,
    *,
    sport: str,
    limit: int,
    scrape_stale_days: int = 7,
    score_stale_days: int = 14,
) -> list[str]:
    rows = await conn.fetch(
        """SELECT a.id
           FROM athletes a
           LEFT JOIN LATERAL (
             SELECT scraped_at FROM raw_athlete_data
             WHERE athlete_id = a.id ORDER BY scraped_at DESC NULLS LAST LIMIT 1
           ) r ON TRUE
           LEFT JOIN LATERAL (
             SELECT calculated_at FROM athlete_gravity_scores
             WHERE athlete_id = a.id ORDER BY calculated_at DESC NULLS LAST LIMIT 1
           ) s ON TRUE
           WHERE a.sport = $1
             AND COALESCE(a.is_active, TRUE) = TRUE
             AND (
               r.scraped_at IS NULL
               OR r.scraped_at < NOW() - make_interval(days => $2)
               OR s.calculated_at IS NULL
               OR s.calculated_at < NOW() - make_interval(days => $3)
             )
           ORDER BY r.scraped_at NULLS FIRST, s.calculated_at NULLS FIRST
           LIMIT $4""",
        sport,
        scrape_stale_days,
        score_stale_days,
        limit,
    )
    return [str(r["id"]) for r in rows]


async def rebuild_cohorts_for_sport(conn: asyncpg.Connection, sport: str) -> int:
    season_year = _current_season_year()
    league = SPORT_LEAGUE.get(sport, "ncaa")
    spec = get_sport_spec(sport)
    total = 0
    for pg in spec.position_groups:
        try:
            n = await rebuild_for_cohort(
                conn,
                league=league,
                sport=sport,
                position_group=pg.position_group,
                season_year=season_year,
            )
            total += n
        except Exception as exc:
            logger.warning("Cohort rebuild failed %s/%s: %s", sport, pg.position_group, exc)
    return total


async def run_nightly_for_sport(
    conn: asyncpg.Connection,
    *,
    sport: str,
    athlete_limit: int = 100,
    concurrency: int = 4,
    scrape: bool = True,
    rebuild_cohorts: bool = True,
    score: bool = True,
) -> NightlySportResult:
    result = NightlySportResult(sport=sport)
    if sport not in ALL_SPORT_PIPELINES:
        result.errors.append(f"Unknown sport: {sport}")
        return result

    stale_ids = await fetch_stale_athlete_ids(conn, sport=sport, limit=athlete_limit)
    result.stale_found = len(stale_ids)
    logger.info("[%s] stale athletes: %d", sport, len(stale_ids))

    sem = asyncio.Semaphore(concurrency)
    dsn = get_settings().pg_dsn

    if scrape and stale_ids:
        async def scrape_one(aid: str) -> None:
            async with sem:
                task_conn = await asyncpg.connect(dsn)
                try:
                    summary = await run_scrapers_for_athlete(
                        task_conn, aid, score_after=False, persist=True
                    )
                    if summary.get("success_count", 0) > 0:
                        result.scraped_ok += 1
                    else:
                        result.scraped_fail += 1
                except Exception as exc:
                    result.scraped_fail += 1
                    result.errors.append(f"scrape {aid[:8]}: {exc}")
                finally:
                    await task_conn.close()

        await asyncio.gather(*[scrape_one(aid) for aid in stale_ids])

    if rebuild_cohorts:
        result.cohort_baselines_written = await rebuild_cohorts_for_sport(conn, sport)
        logger.info("[%s] cohort baselines upserted: %d", sport, result.cohort_baselines_written)

    if score and stale_ids:
        async def score_one(aid: str) -> None:
            async with sem:
                task_conn = await asyncpg.connect(dsn)
                try:
                    await run_athlete_pipeline(task_conn, aid, score=True)
                    result.scored_ok += 1
                except Exception as exc:
                    result.scored_fail += 1
                    result.errors.append(f"score {aid[:8]}: {exc}")
                finally:
                    await task_conn.close()

        await asyncio.gather(*[score_one(aid) for aid in stale_ids])

    return result


async def run_nightly_all_sports(
    conn: asyncpg.Connection,
    *,
    athlete_limit_per_sport: int = 100,
    concurrency: int = 4,
    sports: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    sport_list = sports or tuple(ALL_SPORT_PIPELINES.keys())
    results: dict[str, Any] = {}
    for sport in sport_list:
        logger.info("=== Nightly pipeline: %s ===", sport)
        r = await run_nightly_for_sport(
            conn,
            sport=sport,
            athlete_limit=athlete_limit_per_sport,
            concurrency=concurrency,
        )
        results[sport] = {
            "stale_found": r.stale_found,
            "scraped_ok": r.scraped_ok,
            "scraped_fail": r.scraped_fail,
            "cohort_baselines_written": r.cohort_baselines_written,
            "scored_ok": r.scored_ok,
            "scored_fail": r.scored_fail,
            "errors": r.errors[:10],
        }
    return {"sports": results, "sport_count": len(sport_list)}
