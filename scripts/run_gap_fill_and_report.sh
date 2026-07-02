#!/usr/bin/env bash
# Gap-fill all acceptance sports, then generate EDA report.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PYTHONPATH=.
LIMIT="${LIMIT:-500}"
SCRAPE_CONCURRENCY="${SCRAPE_CONCURRENCY:-3}"
SCORE_CONCURRENCY="${SCORE_CONCURRENCY:-8}"
SPORT_PARALLEL="${SPORT_PARALLEL:-2}"
LOG="${LOG:-/tmp/gap_fill_run.log}"

if [ -z "${PG_DSN:-}" ]; then
  if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
  fi
fi
if [ -z "${PG_DSN:-}" ]; then
  echo "PG_DSN required" >&2
  exit 1
fi

echo "=== Gap fill started $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
python3 -m gravity_api.jobs.nightly_pipeline \
  --gap-fill \
  --limit "$LIMIT" \
  --sport-parallel "$SPORT_PARALLEL" \
  --scrape-concurrency "$SCRAPE_CONCURRENCY" \
  --score-concurrency "$SCORE_CONCURRENCY" \
  2>&1 | tee -a "$LOG"

echo "=== Generating EDA report $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
export REPORT_NOTE="Post gap-fill run (limit=${LIMIT} per sport)."
python3 scripts/generate_scrape_score_eda_report.py 2>&1 | tee -a "$LOG"
echo "=== Done $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
