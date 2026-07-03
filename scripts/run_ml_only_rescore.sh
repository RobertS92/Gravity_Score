#!/usr/bin/env bash
# Rescore acceptance sports with Tier-1 ML bundles (local weights, no heuristic tier-2).
set -euo pipefail
cd "$(dirname "$0")/.."

export PYTHONPATH=.
export SCORING_MODE=local_ml
export FALLBACK_SCORER=ml_only
export MODEL_BUNDLE_ROOT="${MODEL_BUNDLE_ROOT:-models/bundles}"
set -a
source .env 2>/dev/null || true
set +a

LIMIT="${1:-10000}"
LOG="/tmp/ml_only_rescore.log"
echo "=== ML-only local rescore $(date -u +%Y-%m-%dT%H:%M:%SZ) limit=$LIMIT ===" | tee "$LOG"

for sport in cfb nfl nba ncaab_mens ncaab_womens wnba; do
  echo "--- $sport ---" | tee -a "$LOG"
  python3 -m gravity_api.jobs.nightly_pipeline \
    --sport "$sport" \
    --rescore-all \
    --skip-scrape \
    --limit "$LIMIT" \
    2>&1 | tee -a "$LOG"
done

python3 scripts/generate_scrape_score_eda_report.py 2>&1 | tee -a "$LOG"
echo "Done. Log: $LOG" | tee -a "$LOG"
