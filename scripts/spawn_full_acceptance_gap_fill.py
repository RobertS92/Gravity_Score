#!/usr/bin/env python3
"""Spawn run_full_acceptance_gap_fill.py in a detached session (survives agent exit)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = Path(os.environ.get("GAP_FILL_LOG", "/tmp/gap_fill_all_sports_full.log"))
PIDFILE = Path("/tmp/gap_fill_orchestrator.pid")


def main() -> None:
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(ROOT))
    env.setdefault("DISABLE_FIRECRAWL", "1")
    env.setdefault("FALLBACK_SCORER", "heuristic_gravity_v1")
    env.setdefault("SCRAPE_CONCURRENCY", "2")
    env.setdefault("SCORE_CONCURRENCY", "8")
    env.setdefault("CHECKPOINT", "reports/gap_fill_checkpoint_full_v2.json")

    log_fp = open(LOG, "a", encoding="utf-8")  # noqa: SIM115
    proc = subprocess.Popen(
        [sys.executable, "-u", str(ROOT / "scripts" / "run_full_acceptance_gap_fill.py")],
        cwd=ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )
    PIDFILE.write_text(str(proc.pid), encoding="utf-8")
    print(f"Detached orchestrator pid={proc.pid} log={LOG}")


if __name__ == "__main__":
    main()
