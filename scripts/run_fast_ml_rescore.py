#!/usr/bin/env python3
"""Fast ML-only rescore: Railway inference + DB persist (no scrape/cohorts/win-impact)."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import asyncpg

from gravity_api.services.athlete_score_sync import athlete_to_raw_data, fetch_latest_scraped_raw
from gravity_api.services.score_imputation import (
    apply_heuristic_imputations,
    apply_manual_imputations,
    load_manual_imputations,
)
from gravity_api.services.heuristic_gravity import compute_heuristic_gravity_v1, compute_heuristic_latent_v1
from gravity_api.services.sport_pipeline.config import get_sport_pipeline_config
from gravity_api.services.sport_pipeline.run import _persist_score_row
from gravity_api.services.sport_pipeline.score import score_with_sport_model
from gravity_api.services.scoring_stack import finalize_score_metadata
from gravity_ml.brand.taxonomy import enrich_raw_with_partnerships

logger = logging.getLogger("fast_ml_rescore")

DEFAULT_SPORTS = ("cfb", "nfl", "nba", "ncaab_mens", "ncaab_womens", "wnba")
CHECKPOINT_PATH = ROOT / "reports" / "ml_rescore_checkpoint.json"


async def _fetch_ids(conn: asyncpg.Connection, sport: str, *, limit: int) -> list[str]:
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
    return [r["id"] for r in rows]


async def _build_cohort_latents(
    pool: asyncpg.Pool,
    sport: str,
    ids: list[str],
    sem: asyncio.Semaphore,
    *,
    batch_size: int,
) -> list[float]:
    latents: list[float] = []

    async def _one(aid: str) -> None:
        async with sem:
            try:
                async with pool.acquire() as conn:
                    athlete = await conn.fetchrow("SELECT * FROM athletes WHERE id = $1::uuid", aid)
                    if not athlete:
                        return
                    scraped = await fetch_latest_scraped_raw(conn, aid) or {}
                    snap = await conn.fetchrow(
                        """SELECT * FROM social_snapshots WHERE athlete_id = $1::uuid
                           ORDER BY scraped_at DESC NULLS LAST LIMIT 1""",
                        aid,
                    )
                    raw = athlete_to_raw_data(athlete, snap, scraped_raw=scraped)
                    manual = await load_manual_imputations(conn, aid)
                    apply_manual_imputations(raw, manual)
                    apply_heuristic_imputations(raw, athlete)
                    raw = enrich_raw_with_partnerships(raw)
                    latent, _ = compute_heuristic_latent_v1(raw, sport, snapshot=None)
                    latents.append(latent)
            except Exception as exc:
                logger.debug("latent skip %s: %s", aid[:8], exc)

    batch_size = max(batch_size, 32)
    for start in range(0, len(ids), batch_size):
        batch = ids[start : start + batch_size]
        await asyncio.gather(*[_one(aid) for aid in batch])
    return latents


async def _score_one(
    pool: asyncpg.Pool,
    athlete_id: str,
    sem: asyncio.Semaphore,
    *,
    mode: str,
    cohort_latents: list[float] | None = None,
) -> tuple[bool, str | None]:
    async with sem:
        try:
            async with pool.acquire() as conn:
                athlete = await conn.fetchrow("SELECT * FROM athletes WHERE id = $1::uuid", athlete_id)
                if not athlete:
                    return False, "not found"
                sport = str(athlete["sport"])
                pipeline = get_sport_pipeline_config(sport)
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

                if mode == "heuristic":
                    score_data = compute_heuristic_gravity_v1(
                        raw, sport, snapshot=None, cohort_latent_scores=cohort_latents
                    )
                    score_data["model_key"] = pipeline.model_key
                else:
                    score_data = await score_with_sport_model(
                        conn,
                        athlete_id=athlete_id,
                        sport=sport,
                        raw_data=raw,
                        snapshot=None,
                        pipeline=pipeline,
                    )
                score_data = finalize_score_metadata(score_data)
                if mode == "ml" and score_data.get("fallback_used"):
                    return False, f"fallback model={score_data.get('model_version')}"
                if mode == "ml":
                    mv = str(score_data.get("model_version") or "")
                    if mv == "heuristic_gravity_v1":
                        return False, "heuristic fallback in ml mode"
                    if sport != "cfb":
                        return False, f"ml mode only enabled for cfb, got {sport}"
                if mode == "heuristic" and score_data.get("model_version") != "heuristic_gravity_v1":
                    return False, f"unexpected version={score_data.get('model_version')}"

                await _persist_score_row(conn, athlete, score_data, raw, manual, pipeline.model_key)
                return True, None
        except Exception as exc:
            return False, str(exc)


def _load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    return {"sports": {}, "updated_at": None}


def _save_checkpoint(data: dict) -> None:
    data["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


async def rescore_sport(
    dsn: str,
    sport: str,
    *,
    limit: int,
    concurrency: int,
    checkpoint: dict,
    mode: str,
) -> dict:
    conn = await asyncpg.connect(dsn, command_timeout=60)
    try:
        ids = await _fetch_ids(conn, sport, limit=limit)
    finally:
        await conn.close()

    offset = int(checkpoint.get("sports", {}).get(sport, {}).get("offset", 0))
    pending = ids[offset:]
    logger.info("[%s] total=%d offset=%d pending=%d concurrency=%d", sport, len(ids), offset, len(pending), concurrency)

    pool = await asyncpg.create_pool(
        dsn,
        min_size=2,
        max_size=concurrency + 2,
        command_timeout=180,
    )
    sem = asyncio.Semaphore(concurrency)
    cohort_latents: list[float] | None = None
    if mode == "heuristic":
        logger.info("[%s] pass 1: building cohort latents for n=%d", sport, len(ids))
        cohort_latents = await _build_cohort_latents(
            pool, sport, ids, sem, batch_size=max(concurrency * 4, 32)
        )
        logger.info("[%s] pass 1 done: cohort_latents=%d", sport, len(cohort_latents))

    ok = fail = 0
    errors: list[str] = []
    sport_ok = int(checkpoint.get("sports", {}).get(sport, {}).get("ok", 0))
    sport_fail = int(checkpoint.get("sports", {}).get(sport, {}).get("fail", 0))

    batch_size = max(concurrency * 4, 32)
    for start in range(0, len(pending), batch_size):
        batch = pending[start : start + batch_size]
        batch_ok = batch_fail = 0
        outcomes = await asyncio.gather(
            *[_score_one(pool, aid, sem, mode=mode, cohort_latents=cohort_latents) for aid in batch]
        )
        for aid, (success, err) in zip(batch, outcomes):
            if success:
                batch_ok += 1
            else:
                batch_fail += 1
                if err and len(errors) < 20:
                    errors.append(f"{aid[:8]}: {err}")
        sport_ok += batch_ok
        sport_fail += batch_fail
        offset += len(batch)
        checkpoint.setdefault("sports", {}).setdefault(sport, {})
        checkpoint["sports"][sport].update(
            {
                "offset": offset,
                "ok": sport_ok,
                "fail": sport_fail,
                "total": len(ids),
            }
        )
        _save_checkpoint(checkpoint)
        logger.info(
            "[%s] progress %d/%d ok=%d fail=%d",
            sport,
            offset,
            len(ids),
            sport_ok,
            sport_fail,
        )

    await pool.close()
    sport_cp = checkpoint["sports"].get(sport, {})
    return {
        "sport": sport,
        "total": len(ids),
        "done": offset,
        "errors_sample": errors[:10],
    }


async def verify_bucket_distribution(dsn: str, sports: tuple[str, ...]) -> dict[str, dict]:
    conn = await asyncpg.connect(dsn, command_timeout=120)
    out: dict[str, dict] = {}
    try:
        for sport in sports:
            row = await conn.fetchrow(
                """
                WITH active AS (
                  SELECT id FROM athletes
                  WHERE sport = $1 AND COALESCE(is_active, TRUE) AND espn_id IS NOT NULL
                ),
                latest AS (
                  SELECT DISTINCT ON (s.athlete_id) s.gravity_score
                  FROM athlete_gravity_scores s
                  JOIN active a ON a.id = s.athlete_id
                  WHERE s.model_version = 'heuristic_gravity_v1'
                  ORDER BY s.athlete_id, s.calculated_at DESC NULLS LAST
                )
                SELECT
                  COUNT(*) AS n,
                  COUNT(*) FILTER (WHERE gravity_score >= 60 AND gravity_score < 70) AS b_60_70,
                  COUNT(*) FILTER (WHERE gravity_score >= 75 AND gravity_score < 90) AS b_75_89,
                  COUNT(*) FILTER (WHERE gravity_score >= 90 AND gravity_score <= 99) AS b_90_99,
                  ROUND(AVG(gravity_score)::numeric, 2) AS avg_g,
                  ROUND(MIN(gravity_score)::numeric, 2) AS min_g,
                  ROUND(MAX(gravity_score)::numeric, 2) AS max_g
                FROM latest
                """,
                sport,
            )
            n = int(row["n"] or 0)
            out[sport] = {
                "n": n,
                "60_70": int(row["b_60_70"] or 0),
                "75_89": int(row["b_75_89"] or 0),
                "90_99": int(row["b_90_99"] or 0),
                "pct_60_70": round(100.0 * int(row["b_60_70"] or 0) / n, 1) if n else 0.0,
                "pct_75_89": round(100.0 * int(row["b_75_89"] or 0) / n, 1) if n else 0.0,
                "pct_90_99": round(100.0 * int(row["b_90_99"] or 0) / n, 1) if n else 0.0,
                "avg": float(row["avg_g"] or 0),
                "min": float(row["min_g"] or 0),
                "max": float(row["max_g"] or 0),
            }
    finally:
        await conn.close()
    return out


async def verify_sports(dsn: str, sports: tuple[str, ...], *, mode: str) -> dict[str, dict]:
    expected_version = "heuristic_gravity_v1" if mode == "heuristic" else "1.0.0"
    conn = await asyncpg.connect(dsn, command_timeout=120)
    out: dict[str, dict] = {}
    try:
        for sport in sports:
            row = await conn.fetchrow(
                """
                WITH active AS (
                  SELECT id FROM athletes
                  WHERE sport = $1 AND COALESCE(is_active, TRUE) AND espn_id IS NOT NULL
                ),
                latest AS (
                  SELECT DISTINCT ON (s.athlete_id)
                    s.gravity_score, s.model_version, s.calculated_at
                  FROM athlete_gravity_scores s
                  JOIN active a ON a.id = s.athlete_id
                  ORDER BY s.athlete_id, s.calculated_at DESC NULLS LAST
                )
                SELECT
                  (SELECT COUNT(*) FROM active) AS active_n,
                  COUNT(*) AS scored_n,
                  COUNT(*) FILTER (WHERE model_version = $2) AS ml_n,
                  ROUND(AVG(gravity_score)::numeric, 2) AS avg_g,
                  ROUND(STDDEV(gravity_score)::numeric, 2) AS std_g,
                  ROUND(MIN(gravity_score)::numeric, 2) AS min_g,
                  ROUND(MAX(gravity_score)::numeric, 2) AS max_g
                FROM latest
                """,
                sport,
                expected_version,
            )
            active_n = int(row["active_n"] or 0)
            scored_n = int(row["scored_n"] or 0)
            ml_n = int(row["ml_n"] or 0)
            out[sport] = {
                "active_n": active_n,
                "scored_n": scored_n,
                "ml_n": ml_n,
                "ml_pct": round(100.0 * ml_n / active_n, 1) if active_n else 0.0,
                "avg": float(row["avg_g"] or 0),
                "std": float(row["std_g"] or 0),
                "min": float(row["min_g"] or 0),
                "max": float(row["max_g"] or 0),
            }
    finally:
        await conn.close()
    return out


async def main_async() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sports", default=",".join(DEFAULT_SPORTS))
    parser.add_argument("--limit", type=int, default=15000)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--mode", choices=("heuristic", "ml"), default="heuristic")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--min-ml-pct", type=float, default=95.0)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    dsn = os.environ.get("PG_DSN")
    if not dsn:
        raise SystemExit("PG_DSN required")

    sports = tuple(s.strip() for s in args.sports.split(",") if s.strip())
    if args.verify_only:
        stats = await verify_sports(dsn, sports, mode=args.mode)
        print(json.dumps(stats, indent=2))
        return 0

    os.environ.setdefault("FALLBACK_SCORER", "ml_only" if args.mode == "ml" else "heuristic_gravity_v1")
    if args.mode == "ml":
        os.environ.pop("SCORING_MODE", None)

    checkpoint = _load_checkpoint()
    for sport in sports:
        await rescore_sport(
            dsn,
            sport,
            limit=args.limit,
            concurrency=args.concurrency,
            checkpoint=checkpoint,
            mode=args.mode,
        )

    stats = await verify_sports(dsn, sports, mode=args.mode)
    buckets = await verify_bucket_distribution(dsn, sports)
    report_path = ROOT / "reports" / "ml_rescore_distribution.json"
    report_path.write_text(
        json.dumps(
            {
                "sports": stats,
                "buckets": buckets,
                "at": datetime.now(tz=timezone.utc).isoformat(),
            },
            indent=2,
        )
    )
    logger.info("Wrote %s", report_path)

    bad = [s for s, v in stats.items() if v["ml_pct"] < args.min_ml_pct]
    if bad:
        logger.error("Sports below ML threshold: %s", bad)
        return 1
    logger.info("All sports meet ML threshold (>=%.0f%%)", args.min_ml_pct)
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
