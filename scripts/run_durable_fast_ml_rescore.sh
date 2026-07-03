#!/usr/bin/env bash
# Durable ML rescore loop for acceptance sports (excludes baseball/volleyball).
set -euo pipefail
cd "$(dirname "$0")/.."

export PYTHONPATH=.
export FALLBACK_SCORER=ml_only
set -a
source .env 2>/dev/null || true
set +a

SPORTS="cfb,nfl,nba,ncaab_mens,ncaab_womens,wnba"
LOG="/tmp/fast_ml_rescore.log"
CONCURRENCY="${CONCURRENCY:-24}"
LIMIT="${LIMIT:-15000}"

echo "=== durable fast ML rescore $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee "$LOG"

attempt=0
until python3 scripts/run_fast_ml_rescore.py \
  --sports "$SPORTS" \
  --limit "$LIMIT" \
  --concurrency "$CONCURRENCY" \
  --min-ml-pct 95 \
  2>&1 | tee -a "$LOG"; do
  attempt=$((attempt + 1))
  echo "Retry attempt $attempt $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"
  sleep 10
  if [[ $attempt -ge 5 ]]; then
    echo "Giving up after $attempt attempts" | tee -a "$LOG"
    exit 1
  fi
done

python3 scripts/generate_scrape_score_eda_report.py 2>&1 | tee -a "$LOG"
echo "Complete. Distribution: reports/ml_rescore_distribution.json" | tee -a "$LOG"
