#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.
export DISABLE_FIRECRAWL="${DISABLE_FIRECRAWL:-1}"
export FALLBACK_SCORER="${FALLBACK_SCORER:-heuristic_gravity_v1}"
export SCRAPE_CONCURRENCY="${SCRAPE_CONCURRENCY:-2}"
export SCORE_CONCURRENCY="${SCORE_CONCURRENCY:-8}"
export CHECKPOINT="${CHECKPOINT:-reports/gap_fill_checkpoint_full_v2.json}"
LOG="${GAP_FILL_LOG:-/tmp/gap_fill_all_sports_full.log}"
PIDFILE="/tmp/gap_fill_orchestrator.pid"
exec >>"$LOG" 2>&1
echo "=== Launcher started $(date -u +%Y-%m-%dT%H:%M:%SZ) pid=$$ ==="
exec python3 -u scripts/run_full_acceptance_gap_fill.py
