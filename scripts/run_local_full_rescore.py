#!/usr/bin/env python3
"""Full-pipeline rescore in LOCAL scoring mode for every active athlete.

Unlike ``run_fast_ml_rescore.py`` (which either hits the remote Railway model or
scores heuristically with ``snapshot=None``), this driver runs the complete
``run_athlete_pipeline`` locally so the BPXVR snapshot is built and passed into
scoring. That is required for the proof-scaling fixes (``perf_index_to_score`` +
``_block_index`` + percentile-dominant proof) to actually take effect, without
waiting on a Railway redeploy.

Usage:
  SCORING_MODE=local PYTHONPATH=. .venv/bin/python scripts/run_local_full_rescore.py
  SCORING_MODE=local ... scripts/run_local_full_rescore.py --sports nfl --concurrency 12
  scripts/run_local_full_rescore.py --verify-only
  scripts/run_local_full_rescore.py --reset            # clear checkpoint offsets
"""

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

# Force local in-process scoring so our fixed gravity_ml / heuristic code runs
# (the remote Railway service still ships the previous bundle until redeployed).
os.environ["SCORING_MODE"] = "local"
os.environ.setdefault("MODEL_BUNDLE_ROOT", str((ROOT / "models" / "bundles").resolve()))

import asyncpg

from gravity_api.services.sport_pipeline.run import run_athlete_pipeline

logger = logging.getLogger("local_full_rescore")

DEFAULT_SPORTS = ("cfb", "nfl", "nba", "ncaab_mens", "ncaab_womens", "wnba")
CHECKPOINT_PATH = ROOT / "reports" / "local_full_rescore_checkpoint.json"
REPORT_PATH = ROOT / "reports" / "local_full_rescore_distribution.json"


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


async def _score_one(
    pool: asyncpg.Pool, athlete_id: str, sem: asyncio.Semaphore
) -> tuple[bool, str | None]:
    async with sem:
        try:
            async with pool.acquire() as conn:
                result = await run_athlete_pipeline(conn, athlete_id, score=True)
                score = result.get("score") or {}
                if score.get("gravity_score") is None:
                    return False, "no gravity_score returned"
                return True, None
        except Exception as exc:  # noqa: BLE001 - record and continue the sweep
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
    dsn: str, sport: str, *, limit: int, concurrency: int, checkpoint: dict
) -> dict:
    conn = await asyncpg.connect(dsn, command_timeout=60)
    try:
        ids = await _fetch_ids(conn, sport, limit=limit)
    finally:
        await conn.close()

    sport_cp = checkpoint.setdefault("sports", {}).setdefault(sport, {})
    offset = int(sport_cp.get("offset", 0))
    pending = ids[offset:]
    logger.info(
        "[%s] total=%d offset=%d pending=%d concurrency=%d",
        sport, len(ids), offset, len(pending), concurrency,
    )
    if not pending:
        return {"sport": sport, "total": len(ids), "done": offset, "errors_sample": []}

    pool = await asyncpg.create_pool(dsn, min_size=2, max_size=concurrency + 2, command_timeout=300)
    sem = asyncio.Semaphore(concurrency)

    sport_ok = int(sport_cp.get("ok", 0))
    sport_fail = int(sport_cp.get("fail", 0))
    errors: list[str] = []

    batch_size = max(concurrency * 4, 32)
    try:
        for start in range(0, len(pending), batch_size):
            batch = pending[start : start + batch_size]
            outcomes = await asyncio.gather(
                *[_score_one(pool, aid, sem) for aid in batch]
            )
            for aid, (success, err) in zip(batch, outcomes):
                if success:
                    sport_ok += 1
                else:
                    sport_fail += 1
                    if err and len(errors) < 20:
                        errors.append(f"{aid[:8]}: {err}")
            offset += len(batch)
            sport_cp.update({"offset": offset, "ok": sport_ok, "fail": sport_fail, "total": len(ids)})
            _save_checkpoint(checkpoint)
            logger.info("[%s] progress %d/%d ok=%d fail=%d", sport, offset, len(ids), sport_ok, sport_fail)
    finally:
        await pool.close()

    return {"sport": sport, "total": len(ids), "done": offset, "errors_sample": errors[:10]}


async def verify_sports(dsn: str, sports: tuple[str, ...]) -> dict[str, dict]:
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
                    s.gravity_score, s.proof_score, s.calculated_at
                  FROM athlete_gravity_scores s
                  JOIN active a ON a.id = s.athlete_id
                  ORDER BY s.athlete_id, s.calculated_at DESC NULLS LAST
                )
                SELECT
                  (SELECT COUNT(*) FROM active) AS active_n,
                  COUNT(*) AS scored_n,
                  COUNT(*) FILTER (WHERE calculated_at > NOW() - INTERVAL '6 hours') AS fresh_n,
                  ROUND(AVG(gravity_score)::numeric, 2) AS avg_g,
                  ROUND(STDDEV(gravity_score)::numeric, 2) AS std_g,
                  ROUND(MIN(gravity_score)::numeric, 2) AS min_g,
                  ROUND(MAX(gravity_score)::numeric, 2) AS max_g,
                  ROUND(AVG(proof_score)::numeric, 2) AS avg_p,
                  ROUND(STDDEV(proof_score)::numeric, 2) AS std_p
                FROM latest
                """,
                sport,
            )
            active_n = int(row["active_n"] or 0)
            out[sport] = {
                "active_n": active_n,
                "scored_n": int(row["scored_n"] or 0),
                "fresh_n": int(row["fresh_n"] or 0),
                "avg_gravity": float(row["avg_g"] or 0),
                "std_gravity": float(row["std_g"] or 0),
                "min_gravity": float(row["min_g"] or 0),
                "max_gravity": float(row["max_g"] or 0),
                "avg_proof": float(row["avg_p"] or 0),
                "std_proof": float(row["std_p"] or 0),
            }
    finally:
        await conn.close()
    return out


async def main_async() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sports", default=",".join(DEFAULT_SPORTS))
    parser.add_argument("--limit", type=int, default=20000)
    parser.add_argument("--concurrency", type=int, default=12)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--reset", action="store_true", help="Clear checkpoint offsets first")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    dsn = os.environ.get("PG_DSN")
    if not dsn:
        raise SystemExit("PG_DSN required")

    sports = tuple(s.strip() for s in args.sports.split(",") if s.strip())

    if args.verify_only:
        print(json.dumps(await verify_sports(dsn, sports), indent=2))
        return 0

    if args.reset and CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()
        logger.info("Checkpoint reset")

    checkpoint = _load_checkpoint()
    for sport in sports:
        await rescore_sport(
            dsn, sport, limit=args.limit, concurrency=args.concurrency, checkpoint=checkpoint
        )

    stats = await verify_sports(dsn, sports)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps({"sports": stats, "at": datetime.now(tz=timezone.utc).isoformat()}, indent=2),
        encoding="utf-8",
    )
    logger.info("Wrote %s", REPORT_PATH)
    logger.info("Distribution: %s", json.dumps(stats, indent=2))
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
