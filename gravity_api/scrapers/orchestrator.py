"""Run micro-scrapers for an athlete."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

import asyncpg

from gravity_api.config import get_settings
from gravity_api.scraper_registry import resolve_event_scraper_keys
from gravity_api.scraper_registry.sports import SPORTS
from gravity_api.scrapers.clients.espn import begin_espn_cache, clear_espn_cache
from gravity_api.scrapers.clients.firecrawl import begin_scrape_cache, clear_scrape_cache
from gravity_api.scrapers.clients.http_fetch import begin_http_cache, clear_http_cache
from gravity_api.scrapers.db_context import begin_scrape_db, clear_scrape_db
from gravity_api.scrapers.implementations import get_scraper_impl, load_program_context
from gravity_api.scrapers.observations import merge_raw_athlete_data, merge_scraper_fields, persist_observations
from gravity_api.scrapers.types import AthleteScrapeContext, ScraperResult
from gravity_api.services.athlete_score_sync import fetch_latest_scraped_raw
from gravity_api.services.score_imputation import apply_manual_imputations, load_manual_imputations
from gravity_api.services.scraper_registry_service import record_run_result

logger = logging.getLogger(__name__)

# Scrapers that must run before parallel batch (populate handles for downstream scrapers).
BOOTSTRAP_SERIAL_SUFFIXES = frozenset({"social_handle_discovery"})

# Downstream of handle discovery — never parallel with bootstrap pass.
HANDLE_DEPENDENT_SUFFIXES = frozenset(
    {
        "instagram_followers",
        "tiktok_followers",
        "twitter_followers",
        "social_engagement_instagram",
        "social_engagement_tiktok",
    }
)
# ESPN / lightweight scrapers safe to run concurrently (shared ESPN GET cache).
PARALLEL_SCRAPER_SUFFIXES = frozenset(
    {
        "espn_roster",
        "espn_stats",
        "espn_awards",
        "injury_structured",
        "wikipedia_pageviews",
        "stats_freshness",
        "identity_consensus",
        "social_authenticity",
        "all_american",
        "conference_honors",
        "championship_results",
        "national_awards",
        "cfbd_api_stats",
    }
)

# Scrapers that read Postgres via get_scrape_db(); must not run in parallel gather
# (asyncpg connections are not safe for concurrent use; gather child tasks inherit contextvars).
SERIAL_DB_SCRAPER_SUFFIXES = frozenset(
    {
        "news_rss",
        "social_growth_delta",
    }
)


def _scraper_suffix(scraper_key: str, sport: str) -> str:
    suffix = f"_{sport}"
    if scraper_key.endswith(suffix):
        return scraper_key[: -len(suffix)]
    return scraper_key


def _is_serial_db_scraper(scraper_key: str, sport: str) -> bool:
    suffix = _scraper_suffix(scraper_key, sport)
    for db_suffix in SERIAL_DB_SCRAPER_SUFFIXES:
        if suffix == db_suffix or scraper_key.startswith(f"{db_suffix}_"):
            return True
    return False


def _partition_scraper_keys(keys: list[str], sport: str) -> tuple[list[str], list[str], list[str]]:
    """Return (bootstrap_serial, parallel, serial) execution groups."""
    bootstrap: list[str] = []
    parallel: list[str] = []
    serial: list[str] = []
    for key in keys:
        suffix = _scraper_suffix(key, sport)
        if suffix in BOOTSTRAP_SERIAL_SUFFIXES:
            bootstrap.append(key)
        elif suffix in HANDLE_DEPENDENT_SUFFIXES or _is_serial_db_scraper(key, sport):
            serial.append(key)
        elif suffix in PARALLEL_SCRAPER_SUFFIXES:
            parallel.append(key)
        else:
            serial.append(key)
    return bootstrap, parallel, serial


async def build_context(conn: asyncpg.Connection, athlete_id: str) -> AthleteScrapeContext:
    row = await conn.fetchrow("SELECT * FROM athletes WHERE id = $1::uuid", athlete_id)
    if not row:
        raise ValueError("Athlete not found")
    sport = str(row["sport"])
    cfg = SPORTS.get(sport, {})
    scraped = await fetch_latest_scraped_raw(conn, athlete_id)
    manual = await load_manual_imputations(conn, athlete_id)
    if manual:
        apply_manual_imputations(scraped, manual)
    ctx = AthleteScrapeContext(
        athlete_id=str(row["id"]),
        name=str(row["name"]),
        sport=sport,
        school=row.get("school"),
        team=row.get("team") or row.get("school"),
        position=row.get("position"),
        conference=row.get("conference"),
        class_year=row.get("class_year"),
        espn_id=row.get("espn_id"),
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
    gap_fill: bool = False,
    include_extended: bool | None = None,
) -> dict[str, Any]:
    ctx = await build_context(conn, athlete_id)
    settings = get_settings()
    ext = settings.scrape_extended if include_extended is None else include_extended

    if scraper_keys:
        keys = list(scraper_keys)
        gap_info = None
    elif gap_fill or event_type == "gap_fill":
        from gravity_api.scraper_registry.gap_fill import (
            analyze_field_gaps,
            resolve_gap_fill_scraper_keys,
        )

        keys = resolve_gap_fill_scraper_keys(ctx, include_extended=ext)
        gap_info = {
            "gaps": analyze_field_gaps(ctx.existing_raw),
            "scraper_keys": keys,
        }
        if not keys:
            return {
                "athlete_id": athlete_id,
                "sport": ctx.sport,
                "run_id": None,
                "scrapers_run": 0,
                "success_count": 0,
                "skipped": True,
                "reason": "no_data_gaps",
                "gap_fill": gap_info,
                "fields_merged": list(ctx.existing_raw.keys()),
                "results": [],
            }
    else:
        keys = list(
            resolve_event_scraper_keys(event_type, ctx.sport, include_extended=ext)
        )
        gap_info = None
    if ctx.is_pro and "college_experience_pro" not in keys:
        keys.append("college_experience_pro")

    run_id = str(uuid.uuid4())
    results: list[ScraperResult] = []
    merged_fields: dict[str, Any] = dict(ctx.existing_raw)
    raw_before = dict(ctx.existing_raw)

    bootstrap_keys, parallel_keys, serial_keys = _partition_scraper_keys(keys, ctx.sport)

    begin_scrape_cache()
    begin_http_cache()
    begin_espn_cache()
    try:

        async def run_key(key: str) -> ScraperResult:
            impl = get_scraper_impl(key)
            if not impl:
                logger.info("No implementation for scraper_key=%s", key)
                return ScraperResult(
                    scraper_key=key,
                    status="skipped",
                    error_message="no implementation",
                )
            ctx.existing_raw = merged_fields
            try:
                return await impl.run(ctx, key)
            except Exception as exc:
                logger.exception("Scraper %s failed", key)
                return ScraperResult(
                    scraper_key=key,
                    status="failed",
                    error_message=str(exc),
                )

        async def persist_result(result: ScraperResult) -> None:
            if not persist:
                return
            try:
                await record_run_result(
                    conn,
                    scraper_key=result.scraper_key,
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
                    conn,
                    athlete_id=athlete_id,
                    result=result,
                    collection_run_id=run_id,
                )
            except Exception:
                logger.debug("gravity_observations unavailable", exc_info=True)

        async def run_serial_group(group: list[str]) -> None:
            nonlocal merged_fields
            for key in group:
                result = await run_key(key)
                results.append(result)
                merged_fields = merge_scraper_fields(merged_fields, result.fields)
                await persist_result(result)

        if bootstrap_keys:
            await run_serial_group(bootstrap_keys)

        if parallel_keys:
            clear_scrape_db()
            parallel_out = await asyncio.gather(*[run_key(k) for k in parallel_keys])
            for result in parallel_out:
                results.append(result)
                merged_fields = merge_scraper_fields(merged_fields, result.fields)
                await persist_result(result)

        if serial_keys:
            begin_scrape_db(conn)
            try:
                await run_serial_group(serial_keys)
            finally:
                clear_scrape_db()
    finally:
        clear_scrape_cache()
        clear_http_cache()
        clear_espn_cache()
        clear_scrape_db()

    from gravity_api.services.sport_pipeline.raw_stats_sync import (
        apply_ass_enrichment_to_raw,
        enrich_raw_from_athlete_season_stats,
    )
    from gravity_api.services.sport_pipeline.season_stats import upsert_season_stats_from_raw

    ass_enrichment = await enrich_raw_from_athlete_season_stats(conn, athlete_id, ctx.sport)
    merged_fields = apply_ass_enrichment_to_raw(merged_fields, ass_enrichment)

    from gravity_api.scrapers.parsers.stat_normalizer import finalize_stat_fields

    merged_fields = finalize_stat_fields(ctx.sport, merged_fields)

    if persist and merged_fields != raw_before:
        await merge_raw_athlete_data(conn, athlete_id=athlete_id, fields=merged_fields)
        athlete_row = await conn.fetchrow(
            "SELECT position FROM athletes WHERE id = $1::uuid", athlete_id
        )
        await upsert_season_stats_from_raw(
            conn,
            athlete_id=athlete_id,
            sport=ctx.sport,
            position=athlete_row.get("position") if athlete_row else None,
            raw=merged_fields,
        )

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
    if success == 0 and merged_fields != raw_before:
        success = 1

    return {
        "athlete_id": athlete_id,
        "sport": ctx.sport,
        "run_id": run_id,
        "scrapers_run": len(results),
        "success_count": success,
        "fields_merged": list(merged_fields.keys()),
        "gap_fill": gap_info,
        "pipeline": pipeline_result,
        "results": [
            {
                "scraper_key": r.scraper_key,
                "status": r.status,
                "fields": r.fields,
                "fields_written": r.fields_written,
                "fields_failed": r.fields_failed,
                "confidence": r.confidence,
                "error": r.error_message,
                "error_message": r.error_message,
            }
            for r in results
        ],
    }
