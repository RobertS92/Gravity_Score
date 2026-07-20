#!/usr/bin/env python3
"""Ingest ESPN season stats (+ Wikipedia popularity) for non-CFB sports.

Uses only free sources — ESPN public API for stats/roster/awards/injury and
Wikipedia pageviews as a brand/popularity proxy — with Firecrawl explicitly
disabled (the account is out of credits and would only waste time on 402s).
CFB already has rich CFBD-sourced data and baseball is intentionally excluded.

This refreshes stats for ALL active athletes in the target sports (not just
those missing stats), because the previous stat parser corrupted counting/rate
stats via a substring-alias bug — every existing row needs re-ingestion under
the corrected normalizer.

Scoring is intentionally skipped here; run cohort rebuild + rescore afterward.

Usage:
  PYTHONPATH=. .venv/bin/python scripts/run_espn_stats_ingest.py
  ... scripts/run_espn_stats_ingest.py --sports nfl --concurrency 10
  ... scripts/run_espn_stats_ingest.py --reset
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

# Alternative-sources mode: no Firecrawl (out of credits). ESPN + Wikipedia only.
os.environ["DISABLE_FIRECRAWL"] = "1"

import asyncpg

from gravity_api.scrapers.orchestrator import run_scrapers_for_athlete

logger = logging.getLogger("espn_stats_ingest")

DEFAULT_SPORTS = ("nfl", "nba", "wnba", "ncaab_mens", "ncaab_womens")
CHECKPOINT_PATH = ROOT / "reports" / "espn_stats_ingest_checkpoint.json"

# Only the free, high-signal scrapers: on-field stats (proof), awards, injury
# (risk), and Wikipedia pageviews (brand/popularity proxy). Running the full
# ~23-scraper set per athlete was ~10x slower with no added signal in
# alternative-sources mode.
_SCRAPER_SUFFIXES = ("espn_stats", "espn_awards", "injury_structured", "wikipedia_pageviews")
PER_ATHLETE_TIMEOUT_S = 45.0


def _scraper_keys(sport: str) -> list[str]:
    return [f"{suffix}_{sport}" for suffix in _SCRAPER_SUFFIXES]


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


async def _ingest_one(pool: asyncpg.Pool, athlete_id: str, sport: str) -> tuple[bool, str | None]:
    try:
        async with pool.acquire() as conn:
            res = await asyncio.wait_for(
                run_scrapers_for_athlete(
                    conn,
                    athlete_id,
                    scraper_keys=_scraper_keys(sport),
                    persist=True,
                    score_after=False,
                    include_extended=False,
                ),
                timeout=PER_ATHLETE_TIMEOUT_S,
            )
            if not res.get("fields_merged"):
                return False, "no fields merged"
            return True, None
    except asyncio.TimeoutError:
        return False, "timeout"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    return {"sports": {}, "updated_at": None}


def _save_checkpoint(data: dict) -> None:
    data["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


async def ingest_sport(dsn: str, sport: str, *, limit: int, concurrency: int, checkpoint: dict) -> None:
    conn = await asyncpg.connect(dsn, command_timeout=60, statement_cache_size=0)
    try:
        ids = await _fetch_ids(conn, sport, limit=limit)
    finally:
        await conn.close()

    cp = checkpoint.setdefault("sports", {}).setdefault(sport, {})
    offset = int(cp.get("offset", 0))
    pending = ids[offset:]
    logger.info("[%s] total=%d offset=%d pending=%d concurrency=%d", sport, len(ids), offset, len(pending), concurrency)
    if not pending:
        return

    pool = await asyncpg.create_pool(dsn, min_size=2, max_size=concurrency + 2, command_timeout=90, statement_cache_size=0)
    queue: asyncio.Queue[str] = asyncio.Queue()
    for aid in pending:
        queue.put_nowait(aid)

    ok = int(cp.get("ok", 0))
    fail = int(cp.get("fail", 0))
    done = 0
    errors: list[str] = []
    lock = asyncio.Lock()

    async def _worker() -> None:
        nonlocal ok, fail, done, offset
        while True:
            try:
                aid = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            success, err = await _ingest_one(pool, aid, sport)
            async with lock:
                if success:
                    ok += 1
                else:
                    fail += 1
                    if err and len(errors) < 20:
                        errors.append(f"{aid[:8]}: {err}")
                done += 1
                offset += 1
                if done % 50 == 0 or queue.empty():
                    cp.update({"offset": offset, "ok": ok, "fail": fail, "total": len(ids)})
                    _save_checkpoint(checkpoint)
                    logger.info("[%s] progress %d/%d ok=%d fail=%d", sport, offset, len(ids), ok, fail)

    try:
        await asyncio.gather(*[_worker() for _ in range(concurrency)])
    finally:
        await pool.close()
    if errors:
        logger.info("[%s] sample errors: %s", sport, errors[:10])


async def verify(dsn: str, sports: tuple[str, ...]) -> dict:
    conn = await asyncpg.connect(dsn, command_timeout=120, statement_cache_size=0)
    out: dict = {}
    try:
        for sport in sports:
            row = await conn.fetchrow(
                """SELECT COUNT(DISTINCT athlete_id) athletes, COUNT(*) rows
                   FROM athlete_season_stats WHERE sport = $1""",
                sport,
            )
            out[sport] = {"athletes_with_stats": int(row["athletes"] or 0), "stat_rows": int(row["rows"] or 0)}
    finally:
        await conn.close()
    return out


async def main_async() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sports", default=",".join(DEFAULT_SPORTS))
    parser.add_argument("--limit", type=int, default=20000)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for noisy in ("httpx", "gravity_api.scrapers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    dsn = os.environ.get("PG_DSN")
    if not dsn:
        raise SystemExit("PG_DSN required")
    sports = tuple(s.strip() for s in args.sports.split(",") if s.strip())

    if args.verify_only:
        print(json.dumps(await verify(dsn, sports), indent=2))
        return 0

    if args.reset and CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()
        logger.info("Checkpoint reset")

    checkpoint = _load_checkpoint()
    for sport in sports:
        await ingest_sport(dsn, sport, limit=args.limit, concurrency=args.concurrency, checkpoint=checkpoint)

    logger.info("Ingestion complete: %s", json.dumps(await verify(dsn, sports), indent=2))
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
