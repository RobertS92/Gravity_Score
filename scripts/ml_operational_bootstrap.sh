#!/usr/bin/env bash
# Operational bootstrap: train bundles, optional S3 upload, register models.
# Usage:
#   ./scripts/ml_operational_bootstrap.sh --synthetic --register
#   ./scripts/ml_operational_bootstrap.sh --sport ncaab_womens --upload-s3
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.

OUT="${MODEL_BUNDLE_ROOT:-models/bundles}"
SYNTH=""
UPLOAD=""
REGISTER=""
SPORT=""
TEAMS=""
BRANDS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --synthetic) SYNTH="--synthetic" ;;
    --upload-s3) UPLOAD="--upload-s3" ;;
    --register) REGISTER="--register" ;;
    --include-teams) TEAMS="--include-teams" ;;
    --include-brands) BRANDS="--include-brands" ;;
    --sport) SPORT="--sport $2"; shift ;;
    --out) OUT="$2"; shift ;;
  esac
  shift
done

echo "== Step 1: Ingest training labels (if PG_DSN set) =="
if [[ -n "${PG_DSN:-}" ]]; then
  python3 -m gravity_api.jobs.ingest_training_labels || true
fi

echo "== Step 2: Train model bundles → $OUT =="
python3 -m gravity_api.jobs.ml_bootstrap --out "$OUT" $SYNTH $UPLOAD $REGISTER $TEAMS $BRANDS $SPORT

echo "== Step 3: Sync from S3 (if configured) =="
if [[ -n "${MODEL_S3_BUCKET:-}" && -n "${AWS_ACCESS_KEY_ID:-}" ]]; then
  python3 -c "
from pathlib import Path
from gravity_ml.artifacts.s3 import sync_bundles_from_s3
sync_bundles_from_s3(Path('$OUT'))
" || true
fi

echo "Done. Set MODEL_BUNDLE_ROOT=$OUT on gravity-ml Railway service."
echo "Health: curl -H \"Authorization: Bearer \$ML_API_KEY\" http://localhost:8080/health/ready"
