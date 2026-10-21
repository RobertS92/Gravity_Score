#!/usr/bin/env bash
# Trigger SMU (ESPN 2567) CFB + men's basketball roster sync via gravity_api.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -f .env ]]; then
  echo "Missing $ROOT/.env — copy .env.example and set GRAVITY_INTERNAL_API_KEY" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
source ./.env
set +a

API_URL="${GRAVITY_API_URL:-${VITE_API_URL:-http://localhost:8000}}"
API_URL="${API_URL%/}"
KEY="${GRAVITY_INTERNAL_API_KEY:-}"
if [[ -z "$KEY" ]]; then
  echo "Set GRAVITY_INTERNAL_API_KEY in .env" >&2
  exit 1
fi

post_sync() {
  local sport="$1"
  echo "=== roster-sync sport=${sport} team_ids=[2567] ==="
  curl -sS -X POST "${API_URL}/v1/scraper/jobs/roster-sync" \
    -H "X-Internal-Key: ${KEY}" \
    -H "Content-Type: application/json" \
    -d "{\"sport\":\"${sport}\",\"team_ids\":[\"2567\"],\"rescrape_transfers\":true}"
  echo
}

post_sync cfb
post_sync ncaab_mens
echo "Done. Verify with: python scripts/seed_smu_demo_cohort.py --verify-only"
