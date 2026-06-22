#!/usr/bin/env bash
# POST roster-sync to gravity_api (in-process; no sibling scrapers service required).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -f .env ]]; then
  echo "Missing $ROOT/.env — copy .env.example and set PG_DSN + GRAVITY_INTERNAL_API_KEY" >&2
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
  echo "Set GRAVITY_INTERNAL_API_KEY in .env (X-Internal-Key for ops routes)" >&2
  exit 1
fi
BODY="${1:-{}}"
exec curl -sS -X POST "${API_URL}/v1/scraper/jobs/roster-sync" \
  -H "X-Internal-Key: ${KEY}" \
  -H "Content-Type: application/json" \
  -d "${BODY}"
