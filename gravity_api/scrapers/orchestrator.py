"""Run micro-scrapers for an athlete."""

from __future__ import annotations

import logging
import uuid
from typing import Any

import asyncpg

from gravity_api.scraper_registry import resolve_event_scraper_keys
from gravity_api.scraper_registry.sports import SPORTS
from gravity_api.scrapers.implementations import get_scraper_impl, load_program_context
from gravity_api.scrapers.observations import merge_raw_athlete_data, persist_observations
from gravity_api.scrapers.types import AthleteScrapeContext, ScraperResult
from gravity_api.services.athlete_score_sync import fetch_latest_scraped_raw
from gravity_api.services.scraper_registry_service import record_run_result

logger = logging.getLogger(__name__)


async def build_context(conn: asyncpg.Connection, athlete_id: str) -> AthleteScrapeContext:
    row = await conn.fetchrow("SELECT * FROM athletes WHERE id = $1::uuid", athlete_id)
    if not row:
        raise ValueError("Athlete not found")
    sport = str(row["sport"])
    cfg = SPORTS.get(sport, {})
    scraped = await fetch_latest_scraped_raw(conn, athlete_id)
    ctx = AthleteScrapeContext(
        athlete_id=str(row["id"]),
        name=str(row["name"]),
        sport=sport,
        school=row.get("school"),
        team=row.get("team") or row.get("school"),
        position=row.get("position"),
        conference=row.get("conference"),
        class_year=row.get("class_year"),
        college=row.get("school"),
        existing_raw=scraped,
        league_tier=cfg.get("league_tier", "college"),
    )
    await load_program_context(conn, ctx)
    return ctx


async def run_scrapers_for_athlete(
    conn: asyncpg.Connection,
    athlete_id: str,
    *,
    event_type: str = "scheduled_full",
    scraper_keys: list[str] | None = None,
    persist: bool = True,
    score_after: bool = True,
) -> dict[str, Any]:
    ctx = await build_context(conn, athlete_id)
    keys = list(scraper_keys or resolve_event_scraper_keys(event_type, ctx.sport))
    if ctx.is_pro and "college_experience_pro" not in keys:
        keys.append("college_experience_pro")

    run_id = str(uuid.uuid4())
    results: list[ScraperResult] = []
    merged_fields: dict[str, Any] = dict(ctx.existing_raw)

    for key in keys:
        impl = get_scraper_impl(key)
        if not impl:
            logger.info("No implementation for scraper_key=%s", key)
            continue
        ctx.existing_raw = merged_fields
        try:
            result = await impl.run(ctx, key)
        except Exception as exc:
            logger.exception("Scraper %s failed", key)
            result = ScraperResult(
                scraper_key=key,
                status="failed",
                error_message=str(exc),
            )
        results.append(result)
        merged_fields.update(result.fields)

        if persist:
            try:
                await record_run_result(
                    conn,
                    scraper_key=key,
                    status=result.status,
                    athlete_id=athlete_id,
                    sport=ctx.sport,
                    fields_written=result.fields_written,
                    fields_failed=result.fields_failed,
                    error_message=result.error_message,
                    metadata={"run_id": run_id},
                )
            except Exception:
                logger.debug("scraper_run_results table unavailable", exc_info=True)
            try:
                await persist_observations(
                    conn, athlete_id=athlete_id, result=result, collection_run_id=run_id
                )
            except Exception:
                logger.debug("gravity_observations unavailable", exc_info=True)

    if persist and merged_fields != ctx.existing_raw:
        await merge_raw_athlete_data(conn, athlete_id=athlete_id, fields=merged_fields)

    pipeline_result = None
    if persist:
        try:
            from gravity_api.services.sport_pipeline.run import run_athlete_pipeline

            pipeline_result = await run_athlete_pipeline(
                conn, athlete_id, score=score_after
            )
        except Exception:
            logger.exception("Post-scrape sport pipeline failed for %s", athlete_id)

    success = sum(1 for r in results if r.status == "success")
    return {
        "athlete_id": athlete_id,
        "sport": ctx.sport,
        "run_id": run_id,
        "scrapers_run": len(results),
        "success_count": success,
        "fields_merged": list(merged_fields.keys()),
        "pipeline": pipeline_result,
        "results": [
            {
                "scraper_key": r.scraper_key,
                "status": r.status,
                "fields_written": r.fields_written,
                "error": r.error_message,
            }
            for r in results
        ],
    }
