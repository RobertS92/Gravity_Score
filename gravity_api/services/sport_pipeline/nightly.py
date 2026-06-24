"""Nightly per-sport pipeline: stale scrape → cohort rebuild → score."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import asyncpg

from gravity_api.config import get_settings
from gravity_api.feature_engineering.positions import SPORT_LEAGUE
from gravity_api.feature_engineering.sport_specs import get_sport_spec
from gravity_api.jobs.rebuild_cohort_baselines import rebuild_for_cohort
from gravity_api.scrapers.orchestrator import run_scrapers_for_athlete
from gravity_api.services.sport_pipeline.config import ALL_SPORT_PIPELINES
from gravity_api.services.sport_pipeline.run import run_athlete_pipeline
from gravity_api.services.sport_pipeline.season_stats import _current_season_year

logger = logging.getLogger(__name__)

_DB_RETRY_EXCEPTIONS = (
    TimeoutError,
    OSError,
    asyncpg.exceptions.TooManyConnectionsError,
    asyncpg.exceptions.ConnectionDoesNotExistError,
    asyncpg.exceptions.InterfaceError,
)


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


async def _create_worker_pool(
    dsn: str,
    *,
    scrape_concurrency: int,
    score_concurrency: int,
) -> asyncpg.Pool:
    pool_max = max(scrape_concurrency, score_concurrency) + 2
    return await asyncpg.create_pool(
        dsn,
        min_size=1,
        max_size=pool_max,
        command_timeout=120,
        max_inactive_connection_lifetime=300,
    )


async def _run_with_pool_retry(
    pool: asyncpg.Pool,
    fn,
    *,
    retries: int = 3,
):
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            async with pool.acquire() as task_conn:
                return await fn(task_conn)
        except _DB_RETRY_EXCEPTIONS as exc:
            last_exc = exc
            if attempt + 1 >= retries:
                break
            delay = 2**attempt
            logger.warning("DB retry %d/%d after %s", attempt + 1, retries, exc)
            await asyncio.sleep(delay)
    if last_exc:
        raise last_exc
    raise RuntimeError("pool retry failed without exception")


async def run_nightly_for_sport(
    conn: asyncpg.Connection,
    *,
    sport: str,
    athlete_limit: int = 100,
    concurrency: int | None = None,
    scrape_concurrency: int = 3,
    score_concurrency: int = 8,
    scrape: bool = True,
    rebuild_cohorts: bool = True,
    score: bool = True,
    pool: asyncpg.Pool | None = None,
) -> NightlySportResult:
    if concurrency is not None:
        scrape_concurrency = concurrency
        score_concurrency = concurrency

    result = NightlySportResult(sport=sport)
    if sport not in ALL_SPORT_PIPELINES:
        result.errors.append(f"Unknown sport: {sport}")
        return result

    stale_ids = await fetch_stale_athlete_ids(conn, sport=sport, limit=athlete_limit)
    result.stale_found = len(stale_ids)
    logger.info("[%s] stale athletes: %d", sport, len(stale_ids))

    if not stale_ids:
        if rebuild_cohorts:
            result.cohort_baselines_written = await rebuild_cohorts_for_sport(conn, sport)
        return result

    dsn = get_settings().pg_dsn
    owned_pool = pool is None
    if owned_pool:
        pool = await _create_worker_pool(
            dsn,
            scrape_concurrency=scrape_concurrency,
            score_concurrency=score_concurrency,
        )

    scrape_sem = asyncio.Semaphore(scrape_concurrency)
    score_sem = asyncio.Semaphore(score_concurrency)

    try:
        if scrape:
            async def scrape_one(aid: str) -> tuple[bool, str | None]:
                async with scrape_sem:
                    try:
                        async def work(task_conn: asyncpg.Connection) -> bool:
                            summary = await run_scrapers_for_athlete(
                                task_conn, aid, score_after=False, persist=True
                            )
                            return summary.get("success_count", 0) > 0

                        ok = await _run_with_pool_retry(pool, work)
                        return ok, None
                    except Exception as exc:
                        return False, f"scrape {aid[:8]}: {exc}"

            scrape_outcomes = await asyncio.gather(*[scrape_one(aid) for aid in stale_ids])
            for ok, err in scrape_outcomes:
                if ok:
                    result.scraped_ok += 1
                else:
                    result.scraped_fail += 1
                    if err:
                        result.errors.append(err)

        if rebuild_cohorts:
            result.cohort_baselines_written = await rebuild_cohorts_for_sport(conn, sport)
            logger.info(
                "[%s] cohort baselines upserted: %d",
                sport,
                result.cohort_baselines_written,
            )

        if score:
            async def score_one(aid: str) -> tuple[bool, str | None]:
                async with score_sem:
                    try:
                        async def work(task_conn: asyncpg.Connection) -> None:
                            await run_athlete_pipeline(task_conn, aid, score=True)

                        await _run_with_pool_retry(pool, work)
                        return True, None
                    except Exception as exc:
                        return False, f"score {aid[:8]}: {exc}"

            score_outcomes = await asyncio.gather(*[score_one(aid) for aid in stale_ids])
            for ok, err in score_outcomes:
                if ok:
                    result.scored_ok += 1
                else:
                    result.scored_fail += 1
                    if err:
                        result.errors.append(err)
    finally:
        if owned_pool and pool is not None:
            await pool.close()

    return result


async def run_nightly_all_sports(
    conn: asyncpg.Connection,
    *,
    athlete_limit_per_sport: int = 100,
    concurrency: int | None = None,
    scrape_concurrency: int = 3,
    score_concurrency: int = 8,
    sports: tuple[str, ...] | None = None,
    sport_parallel: int = 1,
) -> dict[str, Any]:
    if concurrency is not None:
        scrape_concurrency = concurrency
        score_concurrency = concurrency

    sport_list = sports or tuple(ALL_SPORT_PIPELINES.keys())
    results: dict[str, Any] = {}

    async def run_one(sp: str) -> tuple[str, dict[str, Any]]:
        logger.info("=== Nightly pipeline: %s ===", sp)
        r = await run_nightly_for_sport(
            conn,
            sport=sp,
            athlete_limit=athlete_limit_per_sport,
            scrape_concurrency=scrape_concurrency,
            score_concurrency=score_concurrency,
        )
        payload = {
            "stale_found": r.stale_found,
            "scraped_ok": r.scraped_ok,
            "scraped_fail": r.scraped_fail,
            "cohort_baselines_written": r.cohort_baselines_written,
            "scored_ok": r.scored_ok,
            "scored_fail": r.scored_fail,
            "errors": r.errors[:10],
        }
        return sp, payload

    if sport_parallel <= 1:
        for sport in sport_list:
            sp, payload = await run_one(sport)
            results[sp] = payload
    else:
        sem = asyncio.Semaphore(sport_parallel)

        async def guarded(sp: str) -> tuple[str, dict[str, Any]]:
            async with sem:
                return await run_one(sp)

        pairs = await asyncio.gather(*[guarded(sp) for sp in sport_list])
        for sp, payload in pairs:
            results[sp] = payload

    return {"sports": results, "sport_count": len(sport_list)}
