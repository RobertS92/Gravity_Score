"""Fetch sport cohort latent scores for display calibration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import asyncpg

from gravity_api.services.athlete_score_sync import athlete_to_raw_data, fetch_latest_scraped_raw
from gravity_api.services.heuristic_gravity import compute_heuristic_latent_v1
from gravity_api.services.score_imputation import apply_heuristic_imputations, apply_manual_imputations, load_manual_imputations
from gravity_ml.brand.taxonomy import enrich_raw_with_partnerships

logger = logging.getLogger(__name__)

_cohort_cache: dict[str, list[float]] = {}


async def _latent_for_athlete(conn: asyncpg.Connection, athlete_id: str) -> float | None:
    athlete = await conn.fetchrow("SELECT * FROM athletes WHERE id = $1::uuid", athlete_id)
    if not athlete:
        return None
    sport = str(athlete["sport"])
    scraped = await fetch_latest_scraped_raw(conn, athlete_id) or {}
    snap = await conn.fetchrow(
        """SELECT * FROM social_snapshots WHERE athlete_id = $1::uuid
           ORDER BY scraped_at DESC NULLS LAST LIMIT 1""",
        athlete_id,
    )
    raw = athlete_to_raw_data(athlete, snap, scraped_raw=scraped)
    manual = await load_manual_imputations(conn, athlete_id)
    apply_manual_imputations(raw, manual)
    apply_heuristic_imputations(raw, athlete)
    raw = enrich_raw_with_partnerships(raw)
    latent, _ = compute_heuristic_latent_v1(raw, sport, snapshot=None)
    return latent


async def fetch_sport_cohort_latents(
    conn: asyncpg.Connection,
    sport: str,
    *,
    limit: int = 15000,
    athlete_ids: list[str] | None = None,
    concurrency: int = 20,
) -> list[float]:
    """Compute latent G for active sport cohort (cached per sport)."""
    cache_key = f"{sport}:{limit}"
    if athlete_ids is None and cache_key in _cohort_cache:
        return _cohort_cache[cache_key]

    if athlete_ids is None:
        rows = await conn.fetch(
            """SELECT a.id::text
               FROM athletes a
               WHERE a.sport = $1
                 AND COALESCE(a.is_active, TRUE)
                 AND a.espn_id IS NOT NULL
               ORDER BY a.updated_at DESC NULLS LAST
               LIMIT $2""",
            sport,
            limit,
        )
        athlete_ids = [r["id"] for r in rows]

    sem = asyncio.Semaphore(concurrency)
    latents: list[float] = []

    async def _one(aid: str) -> None:
        async with sem:
            try:
                val = await _latent_for_athlete(conn, aid)
                if val is not None:
                    latents.append(val)
            except Exception as exc:
                logger.debug("cohort latent skip %s: %s", aid[:8], exc)

    batch_size = max(concurrency * 4, 32)
    for start in range(0, len(athlete_ids), batch_size):
        batch = athlete_ids[start : start + batch_size]
        await asyncio.gather(*[_one(aid) for aid in batch])

    if athlete_ids is not None and len(athlete_ids) == len(latents):
        _cohort_cache[cache_key] = latents
    elif athlete_ids is None:
        _cohort_cache[cache_key] = latents

    logger.info("[%s] cohort latents n=%d", sport, len(latents))
    return latents


def clear_cohort_cache() -> None:
    _cohort_cache.clear()


__all__ = ["clear_cohort_cache", "fetch_sport_cohort_latents"]
