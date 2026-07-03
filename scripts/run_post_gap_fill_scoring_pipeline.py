#!/usr/bin/env python3
"""
Post gap-fill scoring pipeline — apply four-tier stack after scrape completes.

Typical flow after a full gap-fill run:
  1. Tier 2 rescore: heuristic_gravity_v1 on full active cohort (--rescore-all, skip scrape)
  2. EDA report + training label ingest
  3. Print Tier 1 (Railway ML) redeploy checklist

Usage:
  export PYTHONPATH=. FALLBACK_SCORER=heuristic_gravity_v1
  python3 scripts/run_post_gap_fill_scoring_pipeline.py --sport cfb
  python3 scripts/run_post_gap_fill_scoring_pipeline.py --all-acceptance-sports
"""

from __future__ import annotations

import argparse
import asyncio
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

SPORT_LIMITS: dict[str, int] = {
    "cfb": 7000,
    "nfl": 3000,
    "ncaab_mens": 1100,
    "ncaab_womens": 900,
    "nba": 5000,
    "wnba": 250,
}

LOG_PATH = Path(os.environ.get("POST_GAP_FILL_LOG", "/tmp/post_gap_fill_scoring.log"))


def _configure_logging() -> logging.Logger:
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
    return logging.getLogger(__name__)


def _wait_for_process(pattern: str, logger: logging.Logger) -> None:
    while subprocess.run(["pgrep", "-f", pattern], capture_output=True).returncode == 0:
        logger.info("Waiting for %s to finish...", pattern)
        time.sleep(60)


async def rescore_sports(
    conn: asyncpg.Connection,
    sports: tuple[str, ...],
    *,
    score_concurrency: int,
    logger: logging.Logger,
) -> dict[str, dict]:
    os.environ.setdefault("FALLBACK_SCORER", "heuristic_gravity_v1")
    results: dict[str, dict] = {}
    for sport in sports:
        limit = SPORT_LIMITS.get(sport, 5000)
        logger.info("Tier 2 rescore: sport=%s limit=%s FALLBACK_SCORER=%s", sport, limit, os.environ.get("FALLBACK_SCORER"))
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
        payload = {
            "rescore_found": result.stale_found,
            "scored_ok": result.scored_ok,
            "scored_fail": result.scored_fail,
            "errors": result.errors[:10],
        }
        results[sport] = payload
        logger.info("Done %s rescore: %s", sport, payload)
    return results


def run_eda_and_labels(logger: logging.Logger, report_note: str) -> None:
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(ROOT))
    env["REPORT_NOTE"] = report_note

    eda = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_scrape_score_eda_report.py")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if eda.returncode != 0:
        logger.error("EDA failed: %s", eda.stderr[-2000:])
        raise SystemExit(eda.returncode)
    logger.info("EDA report: reports/scrape_score_eda_report.md")

    labels = subprocess.run(
        [sys.executable, "-m", "gravity_api.jobs.ingest_training_labels"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if labels.returncode != 0:
        logger.error("Label ingest failed: %s", labels.stderr[-2000:])
        raise SystemExit(labels.returncode)
    logger.info("Training labels ingested")


def print_railway_tier1_checklist(logger: logging.Logger) -> None:
    logger.info(
        "\n=== Tier 1 (Railway ML) redeploy — manual ===\n"
        "1. Railway → gravity-ml service → Deploy from main\n"
        "2. Root: gravity_ml (see gravity_ml/railway.toml)\n"
        "3. Env: MODEL_BUNDLE_ROOT, ML_API_KEY, bundle index includes gravity_athlete_cfb_value_v1\n"
        "4. Verify: POST /score/athlete/cfb returns 200 (not 404)\n"
        "5. Re-run rescore after deploy so Tier 1 replaces weak ML / flat ~77 cluster\n"
    )


async def main_async(args: argparse.Namespace) -> int:
    logger = _configure_logging()
    dsn = os.environ.get("PG_DSN")
    if not dsn:
        raise SystemExit("PG_DSN required")

    sports = tuple(ACCEPTANCE_SPORTS) if args.all_acceptance_sports else (args.sport,)
    if args.wait_for_gap_fill:
        _wait_for_process("run_gap_fill_durable", logger)
        _wait_for_process("run_full_acceptance_gap_fill", logger)

    if args.wait_for_rescore and not args.skip_rescore:
        _wait_for_process("nightly_pipeline.*--skip-scrape", logger)

    conn = await asyncpg.connect(dsn, command_timeout=120)
    rescore_results: dict[str, dict] = {}
    try:
        if not args.skip_rescore:
            rescore_results = await rescore_sports(
                conn,
                sports,
                score_concurrency=args.score_concurrency,
                logger=logger,
            )
    finally:
        await conn.close()

    if not args.skip_reports:
        note = args.report_note or f"Post gap-fill Tier 2 rescore ({', '.join(sports)})."
        run_eda_and_labels(logger, note)

    if args.railway_checklist:
        print_railway_tier1_checklist(logger)

    logger.info("Post gap-fill scoring pipeline complete: %s", rescore_results)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Post gap-fill Tier 2 rescore + EDA + labels")
    parser.add_argument("--sport", default="cfb", help="Single sport (default cfb)")
    parser.add_argument("--all-acceptance-sports", action="store_true")
    parser.add_argument("--score-concurrency", type=int, default=int(os.environ.get("SCORE_CONCURRENCY", "12")))
    parser.add_argument("--skip-rescore", action="store_true")
    parser.add_argument("--skip-reports", action="store_true")
    parser.add_argument("--wait-for-gap-fill", action="store_true")
    parser.add_argument("--wait-for-rescore", action="store_true", help="Wait for in-flight skip-scrape jobs")
    parser.add_argument("--report-note", default=None)
    parser.add_argument("--railway-checklist", action="store_true", default=True)
    parser.add_argument("--no-railway-checklist", action="store_false", dest="railway_checklist")
    args = parser.parse_args()

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n=== Post gap-fill scoring started {datetime.now(tz=timezone.utc).isoformat()} ===\n")
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
