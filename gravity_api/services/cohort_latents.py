"""Fetch sport cohort latent scores for display calibration.

The display calibration ranks an athlete's latent G against the sport cohort.
For that ranking to be meaningful the cohort must be (a) the full population and
(b) computed with the *same* method used to score the athlete (snapshot-based).

Two historical bugs broke this:
  1. Concurrency: up to 20 coroutines shared a single asyncpg connection, which
     asyncpg forbids — most raised "another operation is in progress", the error
     was swallowed, and the cohort silently collapsed to a tiny random subset
     (e.g. 37 of 2924 NFL athletes). Percentiles were computed against noise.
  2. Method mismatch: the cohort latents were computed with ``snapshot=None``
     (fallback proof) while the scored athlete used the BPXVR snapshot (composite
     proof). Ranking a snapshot-based latent against a snapshot-free cohort put
     mediocre players in the top percentile.

The fix: prefer the persisted ``gravity_score_latent`` from each athlete's latest
score row — those were computed with the same snapshot path during scoring, cover
the whole population, and are read in a single cheap query. Only when too few
persisted latents exist (cold start) do we compute them, and that compute path now
uses a dedicated pool so each concurrent task gets its own connection.
"""

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

# Below this many persisted latents we don't trust the cohort as representative
# and bootstrap by computing latents directly.
MIN_PERSISTED_COHORT = 50


async def _fetch_persisted_latents(conn: asyncpg.Connection, sport: str, *, limit: int) -> list[float]:
    """Read latest-per-athlete persisted latent G (computed with snapshots at scoring time)."""
    rows = await conn.fetch(
        """
        WITH latest AS (
          SELECT DISTINCT ON (s.athlete_id)
                 s.athlete_id,
                 (s.dollar_confidence->>'gravity_score_latent')::float AS latent
          FROM athlete_gravity_scores s
          JOIN athletes a ON a.id = s.athlete_id
          WHERE a.sport = $1
            AND COALESCE(a.is_active, TRUE)
            AND a.espn_id IS NOT NULL
            AND s.dollar_confidence ? 'gravity_score_latent'
          ORDER BY s.athlete_id, s.calculated_at DESC NULLS LAST
        )
        SELECT latent FROM latest WHERE latent IS NOT NULL LIMIT $2
        """,
        sport,
        limit,
    )
    return [float(r["latent"]) for r in rows if r["latent"] is not None]


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


async def _compute_latents_pooled(
    conn: asyncpg.Connection,
    athlete_ids: list[str],
    *,
    concurrency: int,
) -> list[float]:
    """Compute latents concurrently, giving each task its own pooled connection.

    asyncpg connections cannot be shared across concurrent operations, so a single
    shared ``conn`` here would silently drop most results. We derive a pool from the
    live connection's DSN when possible and fall back to sequential use of ``conn``.
    """
    dsn = _dsn_from_settings()
    latents: list[float] = []
    sem = asyncio.Semaphore(max(1, concurrency))

    if dsn is None:
        # No DSN available (e.g. tests with an injected connection): run sequentially
        # on the provided connection to stay correct, just slower.
        for aid in athlete_ids:
            try:
                val = await _latent_for_athlete(conn, aid)
                if val is not None:
                    latents.append(val)
            except Exception as exc:  # noqa: BLE001
                logger.debug("cohort latent skip %s: %s", aid[:8], exc)
        return latents

    pool = await asyncpg.create_pool(dsn, min_size=2, max_size=concurrency + 2, command_timeout=120)
    try:
        async def _one(aid: str) -> None:
            async with sem:
                try:
                    async with pool.acquire() as c:
                        val = await _latent_for_athlete(c, aid)
                    if val is not None:
                        latents.append(val)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("cohort latent skip %s: %s", aid[:8], exc)

        batch_size = max(concurrency * 4, 32)
        for start in range(0, len(athlete_ids), batch_size):
            batch = athlete_ids[start : start + batch_size]
            await asyncio.gather(*[_one(aid) for aid in batch])
    finally:
        await pool.close()
    return latents


def _dsn_from_settings() -> str | None:
    try:
        from gravity_api.config import get_settings

        dsn = get_settings().pg_dsn
        return str(dsn) if dsn else None
    except Exception:  # noqa: BLE001
        import os

        return os.environ.get("PG_DSN")


async def fetch_sport_cohort_latents(
    conn: asyncpg.Connection,
    sport: str,
    *,
    limit: int = 15000,
    athlete_ids: list[str] | None = None,
    concurrency: int = 12,
) -> list[float]:
    """Return latent G scores for the active sport cohort (cached per sport).

    Prefers persisted, snapshot-consistent latents from the latest score rows.
    Falls back to a pooled, per-task-connection compute when too few exist.
    """
    cache_key = f"{sport}:{limit}"
    if athlete_ids is None and cache_key in _cohort_cache:
        return _cohort_cache[cache_key]

    if athlete_ids is None:
        # Preferred path: persisted latents (full population, snapshot-consistent, one query).
        try:
            persisted = await _fetch_persisted_latents(conn, sport, limit=limit)
        except Exception as exc:  # noqa: BLE001
            logger.debug("persisted latent read failed for %s: %s", sport, exc)
            persisted = []
        if len(persisted) >= MIN_PERSISTED_COHORT:
            _cohort_cache[cache_key] = persisted
            logger.info("[%s] cohort latents n=%d (persisted)", sport, len(persisted))
            return persisted

        # Cold-start bootstrap: compute from active roster.
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
        latents = await _compute_latents_pooled(conn, athlete_ids, concurrency=concurrency)
        _cohort_cache[cache_key] = latents
        logger.info("[%s] cohort latents n=%d (computed)", sport, len(latents))
        return latents

    # Explicit id list: always compute.
    latents = await _compute_latents_pooled(conn, athlete_ids, concurrency=concurrency)
    if len(athlete_ids) == len(latents):
        _cohort_cache[cache_key] = latents
    logger.info("[%s] cohort latents n=%d (computed, explicit ids)", sport, len(latents))
    return latents


def clear_cohort_cache() -> None:
    _cohort_cache.clear()


__all__ = ["clear_cohort_cache", "fetch_sport_cohort_latents", "MIN_PERSISTED_COHORT"]
