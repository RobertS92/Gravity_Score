#!/usr/bin/env python3
"""Full acceptance-sports gap-fill (Phase A), heuristic rescore (Phase B), reports (Phase C)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import asyncpg

from gravity_api.scraper_registry.acceptance_sports import ACCEPTANCE_SPORTS
from gravity_api.services.sport_pipeline.nightly import run_nightly_for_sport

# Headroom above current DB counts (queried 2026-07-02).
SPORT_LIMITS: dict[str, int] = {
    "cfb": 7000,
    "nfl": 3000,
    "ncaab_mens": 1100,
    "ncaab_womens": 900,
    "nba": 5000,
    "wnba": 250,
}

PHASE_A_LOG = Path(os.environ.get("GAP_FILL_LOG", "/tmp/gap_fill_all_sports_full.log"))
PHASE_B_LOG = Path(os.environ.get("RESCORE_LOG", "/tmp/all_sports_rescore.log"))
CHECKPOINT = Path(
    os.environ.get("CHECKPOINT", str(ROOT / "reports" / "gap_fill_checkpoint_full_v2.json"))
)
RESULTS_JSON = ROOT / "reports" / "gap_fill_full_v2_results.json"


def _configure_logging(log_path: Path) -> None:
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_path, mode="a", encoding="utf-8"),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
        force=True,
    )
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]


def _load_checkpoint() -> dict:
    if CHECKPOINT.exists():
        try:
            return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"completed_sports": {}, "rescore_completed": {}, "started_at": None}


def _save_checkpoint(data: dict) -> None:
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _save_results(data: dict) -> None:
    RESULTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_JSON.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _pgrep(pattern: str) -> bool:
    return subprocess.run(["pgrep", "-f", pattern], capture_output=True).returncode == 0


def wait_for_inflight_cfb_jobs(logger: logging.Logger) -> None:
    """Wait for overlapping CFB rescore/gap-fill jobs before DB-heavy work."""
    patterns = ("nightly_pipeline.*cfb", "run_gap_fill_durable")
    while any(_pgrep(p) for p in patterns):
        logger.info("Waiting for in-flight CFB/rescore jobs to finish...")
        time.sleep(60)
    logger.info("No in-flight CFB/rescore jobs detected; proceeding.")


def _result_payload(result) -> dict:
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


async def phase_a_gap_fill(
    conn: asyncpg.Connection,
    *,
    sports: tuple[str, ...],
    checkpoint: dict,
    results: dict,
    logger: logging.Logger,
) -> None:
    scrape_concurrency = int(os.environ.get("SCRAPE_CONCURRENCY", "2"))
    score_concurrency = int(os.environ.get("SCORE_CONCURRENCY", "8"))

    logger.info("=== Phase A: full gap-fill scrape+score ===")
    for sport in sports:
        if sport in checkpoint.get("completed_sports", {}):
            logger.info("Phase A skip %s (checkpoint)", sport)
            results.setdefault("phase_a", {})[sport] = checkpoint["completed_sports"][sport]
            continue

        limit = SPORT_LIMITS.get(sport, 1000)
        logger.info("=== Phase A sport: %s limit=%s ===", sport, limit)
        try:
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
            payload = _result_payload(result)
            checkpoint.setdefault("completed_sports", {})[sport] = payload
            results.setdefault("phase_a", {})[sport] = payload
            _save_checkpoint(checkpoint)
            _save_results(results)
            logger.info("Phase A done %s: %s", sport, payload)
        except Exception:
            logger.exception("Phase A failed for %s", sport)
            checkpoint.setdefault("failed_sports", {})[sport] = {
                "phase": "A",
                "failed_at": datetime.now(tz=timezone.utc).isoformat(),
            }
            _save_checkpoint(checkpoint)
            results.setdefault("phase_a_errors", {})[sport] = "failed"
            _save_results(results)


async def phase_b_rescore(
    conn: asyncpg.Connection,
    *,
    sports: tuple[str, ...],
    checkpoint: dict,
    results: dict,
    logger: logging.Logger,
) -> None:
    score_concurrency = int(os.environ.get("SCORE_CONCURRENCY", "8"))

    logger.info("=== Phase B: full heuristic rescore (skip scrape) ===")
    for sport in sports:
        if sport in checkpoint.get("rescore_completed", {}):
            logger.info("Phase B skip %s (checkpoint)", sport)
            results.setdefault("phase_b", {})[sport] = checkpoint["rescore_completed"][sport]
            continue

        limit = SPORT_LIMITS.get(sport, 1000)
        logger.info("=== Phase B sport: %s limit=%s ===", sport, limit)
        try:
            result = await run_nightly_for_sport(
                conn,
                sport=sport,
                athlete_limit=limit,
                score_concurrency=score_concurrency,
                scrape=False,
                rebuild_cohorts=False,
                score=True,
                rescore_all=True,
            )
            payload = _result_payload(result)
            checkpoint.setdefault("rescore_completed", {})[sport] = payload
            results.setdefault("phase_b", {})[sport] = payload
            _save_checkpoint(checkpoint)
            _save_results(results)
            logger.info("Phase B done %s: %s", sport, payload)
        except Exception:
            logger.exception("Phase B failed for %s", sport)
            checkpoint.setdefault("rescore_failed", {})[sport] = {
                "failed_at": datetime.now(tz=timezone.utc).isoformat(),
            }
            _save_checkpoint(checkpoint)
            results.setdefault("phase_b_errors", {})[sport] = "failed"
            _save_results(results)


def phase_c_reports(logger: logging.Logger) -> None:
    logger.info("=== Phase C: EDA report + training labels ===")
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(ROOT))
    env.setdefault(
        "REPORT_NOTE",
        "Post full all-sports gap-fill + heuristic rescore.",
    )

    eda = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_scrape_score_eda_report.py")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if eda.returncode != 0:
        logger.error("EDA report failed: %s", eda.stderr[-2000:])
    else:
        logger.info("EDA report written")

    labels = subprocess.run(
        [sys.executable, "-m", "gravity_api.jobs.ingest_training_labels"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if labels.returncode != 0:
        logger.error("Training label ingest failed: %s", labels.stderr[-2000:])
    else:
        logger.info("Training labels ingested: %s", labels.stdout.strip()[-500:])


async def main_async() -> int:
    dsn = os.environ.get("PG_DSN")
    if not dsn:
        raise SystemExit("PG_DSN required")

    sports = tuple(
        s.strip()
        for s in os.environ.get("SPORTS", ",".join(ACCEPTANCE_SPORTS)).split(",")
        if s.strip()
    )
    skip_phase_a = os.environ.get("SKIP_PHASE_A", "").strip() in ("1", "true", "yes")
    skip_phase_b = os.environ.get("SKIP_PHASE_B", "").strip() in ("1", "true", "yes")
    skip_phase_c = os.environ.get("SKIP_PHASE_C", "").strip() in ("1", "true", "yes")

    _configure_logging(PHASE_A_LOG)
    logger = logging.getLogger(__name__)

    wait_for_inflight_cfb_jobs(logger)

    checkpoint = _load_checkpoint()
    if not checkpoint.get("started_at"):
        checkpoint["started_at"] = datetime.now(tz=timezone.utc).isoformat()
        _save_checkpoint(checkpoint)

    results: dict = {
        "started_at": checkpoint["started_at"],
        "sports": sports,
        "sport_limits": {s: SPORT_LIMITS.get(s) for s in sports},
        "env": {
            "DISABLE_FIRECRAWL": os.environ.get("DISABLE_FIRECRAWL"),
            "FALLBACK_SCORER": os.environ.get("FALLBACK_SCORER", "heuristic_gravity_v1"),
            "SCRAPE_CONCURRENCY": os.environ.get("SCRAPE_CONCURRENCY", "2"),
            "SCORE_CONCURRENCY": os.environ.get("SCORE_CONCURRENCY", "8"),
        },
    }
    _save_results(results)

    conn = await asyncpg.connect(dsn, command_timeout=120)
    try:
        if not skip_phase_a:
            await phase_a_gap_fill(
                conn, sports=sports, checkpoint=checkpoint, results=results, logger=logger
            )
        if not skip_phase_b:
            _configure_logging(PHASE_B_LOG)
            await phase_b_rescore(
                conn, sports=sports, checkpoint=checkpoint, results=results, logger=logger
            )
    finally:
        await conn.close()

    checkpoint["finished_at"] = datetime.now(tz=timezone.utc).isoformat()
    results["finished_at"] = checkpoint["finished_at"]
    _save_checkpoint(checkpoint)
    _save_results(results)

    if not skip_phase_c:
        phase_c_reports(logger)

    logger.info("Full acceptance gap-fill orchestration complete")
    return 0


def main() -> None:
    started = datetime.now(tz=timezone.utc).isoformat()
    for log_path in (PHASE_A_LOG, PHASE_B_LOG):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n=== Full acceptance gap-fill started {started} ===\n")
            f.flush()
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
