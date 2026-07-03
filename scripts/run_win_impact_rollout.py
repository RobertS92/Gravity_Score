#!/usr/bin/env python3
"""Wait for legacy jobs, then gap-fill CFB team records + rescore-all with win_impact."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = Path(os.environ.get("WIN_IMPACT_LOG", "/tmp/win_impact_rollout.log"))


def _pgrep(pattern: str) -> bool:
    return subprocess.run(["pgrep", "-f", pattern], capture_output=True).returncode == 0


def wait_for_legacy_jobs(logger: logging.Logger) -> None:
    patterns = (
        "nightly_pipeline.*cfb.*skip-scrape",
        "run_gap_fill_durable",
    )
    while any(_pgrep(p) for p in patterns):
        logger.info("Waiting for legacy CFB rescore / gap-fill durable...")
        time.sleep(120)
    if os.environ.get("WAIT_FULL_ACCEPTANCE", "1").strip() not in ("0", "false", "no"):
        while _pgrep("run_full_acceptance_gap_fill"):
            logger.info("Waiting for full acceptance gap-fill orchestrator...")
            time.sleep(180)
    logger.info("Conflicting jobs cleared.")


def run_cmd(logger: logging.Logger, cmd: list[str], *, env: dict[str, str]) -> int:
    logger.info("RUN: %s", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    if proc.stdout:
        logger.info(proc.stdout[-4000:])
    if proc.returncode != 0:
        logger.error("FAILED (%s): %s", proc.returncode, proc.stderr[-4000:])
    return proc.returncode


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG, mode="a", encoding="utf-8"),
        ],
        force=True,
    )
    logger = logging.getLogger("win_impact_rollout")
    logger.info("=== Win impact rollout started %s ===", datetime.now(tz=timezone.utc).isoformat())

    wait_for_legacy_jobs(logger)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env.setdefault("FALLBACK_SCORER", "heuristic_gravity_v1")
    env.setdefault("DISABLE_FIRECRAWL", "1")

    py = sys.executable

    if os.environ.get("SKIP_PREFETCH", "").strip() not in ("1", "true", "yes"):
        run_cmd(logger, [py, str(ROOT / "scripts" / "prefetch_cfb_team_records.py")], env=env)

    if os.environ.get("SKIP_GAP_FILL", "").strip() not in ("1", "true", "yes"):
        rc = run_cmd(
            logger,
            [
                py,
                "-m",
                "gravity_api.jobs.nightly_pipeline",
                "--sport",
                "cfb",
                "--gap-fill",
                "--limit",
                os.environ.get("WIN_IMPACT_GAP_FILL_LIMIT", "7000"),
                "--scrape-concurrency",
                os.environ.get("SCRAPE_CONCURRENCY", "2"),
                "--score-concurrency",
                os.environ.get("SCORE_CONCURRENCY", "8"),
            ],
            env=env,
        )
        if rc != 0:
            logger.warning("Gap-fill returned %s; continuing to rescore-all", rc)

    # Phase 2: full rescore with win_impact (skip scrape)
    rc = run_cmd(
        logger,
        [
            py,
            "-m",
            "gravity_api.jobs.nightly_pipeline",
            "--sport",
            "cfb",
            "--rescore-all",
            "--skip-scrape",
            "--limit",
            "7000",
            "--score-concurrency",
            os.environ.get("SCORE_CONCURRENCY", "12"),
        ],
        env=env,
    )
    if rc != 0:
        logger.error("Rescore-all failed with %s", rc)
        return rc

    # Phase 3: labels + train
    run_cmd(logger, [py, "-m", "gravity_api.jobs.ingest_training_labels"], env=env)
    rc = run_cmd(logger, [py, str(ROOT / "scripts" / "train_cfb_impact_v1.py")], env=env)
    if rc != 0:
        logger.warning("Impact training skipped or failed (%s) — need >=30 labeled rows", rc)

    logger.info("=== Win impact rollout complete ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
