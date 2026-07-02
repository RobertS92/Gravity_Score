#!/usr/bin/env python3
"""Run gap-fill sport-by-sport with checkpointing and unbuffered logs."""

from __future__ import annotations

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

from gravity_api.scraper_registry.acceptance_sports import ACCEPTANCE_SPORTS
from gravity_api.services.sport_pipeline.nightly import run_nightly_for_sport

CHECKPOINT = Path(
    os.environ.get("CHECKPOINT", str(ROOT / "reports" / "gap_fill_checkpoint.json"))
)
LOG_PATH = Path(os.environ.get("GAP_FILL_LOG", "/tmp/gap_fill_run.log"))


def _configure_logging() -> None:
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, mode="a", encoding="utf-8"),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
        force=True,
    )
    for h in handlers:
        h.flush = getattr(h, "flush", lambda: None)  # type: ignore[method-assign]
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]


def _load_checkpoint() -> dict:
    if CHECKPOINT.exists():
        try:
            return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"completed_sports": {}, "started_at": None}


def _save_checkpoint(data: dict) -> None:
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


async def run_sport(
    conn: asyncpg.Connection,
    *,
    sport: str,
    limit: int,
    scrape_concurrency: int,
    score_concurrency: int,
) -> dict:
    result = await run_nightly_for_sport(
        conn,
        sport=sport,
        athlete_limit=limit,
        scrape_concurrency=scrape_concurrency,
        score_concurrency=score_concurrency,
        scrape=True,
        rebuild_cohorts=True,
        score=True,
        gap_fill=True,
    )
    return {
        "stale_found": result.stale_found,
        "scraped_ok": result.scraped_ok,
        "scraped_fail": result.scraped_fail,
        "cohort_baselines_written": result.cohort_baselines_written,
        "scored_ok": result.scored_ok,
        "scored_fail": result.scored_fail,
        "errors": result.errors[:20],
        "finished_at": datetime.now(tz=timezone.utc).isoformat(),
    }


async def main_async() -> int:
    dsn = os.environ.get("PG_DSN")
    if not dsn:
        raise SystemExit("PG_DSN required")

    limit = int(os.environ.get("LIMIT", "500"))
    scrape_concurrency = int(os.environ.get("SCRAPE_CONCURRENCY", "3"))
    score_concurrency = int(os.environ.get("SCORE_CONCURRENCY", "8"))
    sports = tuple(
        s.strip()
        for s in os.environ.get("SPORTS", ",".join(ACCEPTANCE_SPORTS)).split(",")
        if s.strip()
    )

    checkpoint = _load_checkpoint()
    if not checkpoint.get("started_at"):
        checkpoint["started_at"] = datetime.now(tz=timezone.utc).isoformat()
        _save_checkpoint(checkpoint)

    logger = logging.getLogger(__name__)
    logger.info(
        "Durable gap-fill start sports=%s limit=%s scrape=%s score=%s",
        sports,
        limit,
        scrape_concurrency,
        score_concurrency,
    )

    conn = await asyncpg.connect(dsn, command_timeout=120)
    try:
        for sport in sports:
            if sport in checkpoint.get("completed_sports", {}):
                logger.info("Skipping %s (already in checkpoint)", sport)
                continue
            logger.info("=== Gap-fill sport: %s ===", sport)
            try:
                payload = await run_sport(
                    conn,
                    sport=sport,
                    limit=limit,
                    scrape_concurrency=scrape_concurrency,
                    score_concurrency=score_concurrency,
                )
                checkpoint.setdefault("completed_sports", {})[sport] = payload
                _save_checkpoint(checkpoint)
                logger.info("Done %s: %s", sport, payload)
            except Exception:
                logger.exception("Sport %s failed", sport)
                checkpoint.setdefault("failed_sports", {})[sport] = {
                    "failed_at": datetime.now(tz=timezone.utc).isoformat(),
                }
                _save_checkpoint(checkpoint)
                raise
    finally:
        await conn.close()

    checkpoint["finished_at"] = datetime.now(tz=timezone.utc).isoformat()
    _save_checkpoint(checkpoint)
    logger.info("All sports complete: %s", list(checkpoint.get("completed_sports", {}).keys()))
    return 0


def main() -> None:
    _configure_logging()
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n=== Durable gap-fill started {datetime.now(tz=timezone.utc).isoformat()} ===\n")
        f.flush()
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
