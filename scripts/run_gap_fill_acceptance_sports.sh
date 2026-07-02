#!/usr/bin/env bash
# Gap-fill scrape + score for the 6 acceptance sports (excludes baseball/volleyball).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PYTHONPATH=.
LIMIT="${LIMIT:-500}"
SCRAPE_CONCURRENCY="${SCRAPE_CONCURRENCY:-3}"
SCORE_CONCURRENCY="${SCORE_CONCURRENCY:-8}"
SPORT_PARALLEL="${SPORT_PARALLEL:-2}"

if [ -z "${PG_DSN:-}" ]; then
  echo "PG_DSN required" >&2
  exit 1
fi

exec python3 -m gravity_api.jobs.nightly_pipeline \
  --gap-fill \
  --limit "$LIMIT" \
  --sport-parallel "$SPORT_PARALLEL" \
  --scrape-concurrency "$SCRAPE_CONCURRENCY" \
  --score-concurrency "$SCORE_CONCURRENCY"
