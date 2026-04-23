"""Operations dashboard — DB aggregates + optional gravity-scrapers HTTP."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg
import httpx
from fastapi import APIRouter, Depends

from gravity_api.auth_deps import require_user_id
from gravity_api.config import get_settings
from gravity_api.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


async def _safe_val(db: asyncpg.Connection, sql: str, *args: Any) -> Any:
    try:
        return await db.fetchval(sql, *args)
    except Exception as exc:
        logger.debug("operations metric skipped: %s", exc)
        return None


async def _collect_db(db: asyncpg.Connection) -> dict[str, Any]:
    out: dict[str, Any] = {
        "athletes_total": await _safe_val(db, "SELECT COUNT(*)::bigint FROM athletes"),
        "athletes_with_scores": await _safe_val(
            db,
            """SELECT COUNT(DISTINCT athlete_id)::bigint FROM athlete_gravity_scores""",
        ),
    }

    has_last_scraped = await _safe_val(
        db,
        """SELECT 1 FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'athletes' AND column_name = 'last_scraped_at'""",
    )
    if has_last_scraped:
        out["athletes_last_scraped_set"] = await _safe_val(
            db,
            "SELECT COUNT(*)::bigint FROM athletes WHERE last_scraped_at IS NOT NULL",
        )
        out["athletes_scraped_7d"] = await _safe_val(
            db,
            """SELECT COUNT(*)::bigint FROM athletes
               WHERE last_scraped_at > NOW() - INTERVAL '7 days'""",
        )

    has_dqs = await _safe_val(
        db,
        """SELECT 1 FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'athletes' AND column_name = 'data_quality_score'""",
    )
    if has_dqs:
        out["avg_data_quality_score"] = await _safe_val(
            db,
            "SELECT ROUND(AVG(data_quality_score)::numeric, 4) FROM athletes WHERE data_quality_score IS NOT NULL",
        )
        out["athletes_with_dqs"] = await _safe_val(
            db,
            "SELECT COUNT(*)::bigint FROM athletes WHERE data_quality_score IS NOT NULL",
        )

    reg_raw = await _safe_val(db, "SELECT to_regclass('public.raw_athlete_data')")
    if reg_raw:
        out["raw_athlete_data_rows"] = await _safe_val(
            db, "SELECT COUNT(*)::bigint FROM raw_athlete_data"
        )
        out["raw_athlete_data_latest"] = await _safe_val(
            db, "SELECT MAX(scraped_at) FROM raw_athlete_data"
        )

    reg_rs = await _safe_val(db, "SELECT to_regclass('public.roster_snapshots')")
    if reg_rs:
        out["roster_snapshots_rows"] = await _safe_val(
            db, "SELECT COUNT(*)::bigint FROM roster_snapshots"
        )
        out["roster_snapshots_latest"] = await _safe_val(
            db, "SELECT MAX(snapshot_date)::text FROM roster_snapshots"
        )

    reg_rv = await _safe_val(db, "SELECT to_regclass('public.scraper_jobs')")
    out["scraper_jobs_in_db"] = bool(reg_rv)
    if reg_rv:
        try:
            rows = await db.fetch(
                """SELECT job_type, status, processed_count, failed_count,
                          started_at, completed_at, progress
                   FROM scraper_jobs
                   ORDER BY started_at DESC
                   LIMIT 15"""
            )
        except Exception:
            rows = await db.fetch(
                """SELECT job_type, status, processed_count, failed_count,
                          started_at, completed_at
                   FROM scraper_jobs
                   ORDER BY started_at DESC
                   LIMIT 15"""
            )
        out["scraper_jobs_recent"] = [dict(r) for r in rows]

    has_rva = await _safe_val(
        db,
        """SELECT 1 FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'athletes' AND column_name = 'roster_verified_at'""",
    )
    if has_rva:
        out["athletes_roster_verified"] = await _safe_val(
            db,
            "SELECT COUNT(*)::bigint FROM athletes WHERE roster_verified_at IS NOT NULL",
        )
        out["athletes_roster_verified_180d"] = await _safe_val(
            db,
            """SELECT COUNT(*)::bigint FROM athletes
               WHERE roster_verified_at IS NOT NULL
                 AND roster_verified_at >= NOW() - INTERVAL '180 days'""",
        )

    return out


async def _fetch_scrapers_http() -> tuple[Optional[dict[str, Any]], Optional[str]]:
    settings = get_settings()
    base = settings.scrapers_service_url
    key = settings.scrapers_service_api_key
    if not base or not key:
        return None, "SCRAPERS_SERVICE_URL and SCRAPERS_SERVICE_API_KEY not set on API"

    headers = {"Authorization": f"Bearer {key}"}
    out: dict[str, Any] = {}
    err_parts: list[str] = []

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            try:
                r = await client.get(f"{base}/health")
                if r.status_code == 200:
                    out["health"] = r.json()
                else:
                    err_parts.append(f"health HTTP {r.status_code}")
            except Exception as e:
                err_parts.append(f"health: {e}")

            try:
                r = await client.get(f"{base}/jobs/status", headers=headers)
                if r.status_code == 200:
                    out["jobs_status"] = r.json()
                else:
                    err_parts.append(f"jobs/status HTTP {r.status_code}")
            except Exception as e:
                err_parts.append(f"jobs/status: {e}")

            try:
                r = await client.get(f"{base}/jobs/progress", headers=headers)
                if r.status_code == 200:
                    out["jobs_progress"] = r.json()
                elif r.status_code != 404:
                    err_parts.append(f"jobs/progress HTTP {r.status_code}")
            except Exception as e:
                err_parts.append(f"jobs/progress: {e}")

        return out, ("; ".join(err_parts) if err_parts else None)
    except Exception as e:
        return None, str(e)


@router.get("/dashboard")
async def operations_dashboard(
    _uid: uuid.UUID = Depends(require_user_id),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Aggregated pipeline health: Postgres counts + optional live gravity-scrapers
    (jobs, progress, health). Requires JWT (same as other terminal routes).
    """
    generated = datetime.now(timezone.utc).isoformat()
    database = await _collect_db(db)
    scrapers_payload, scrapers_err = await _fetch_scrapers_http()

    return {
        "generated_at": generated,
        "database": database,
        "scrapers": scrapers_payload,
        "scrapers_error": scrapers_err,
    }
