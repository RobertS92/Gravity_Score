#!/usr/bin/env bash
# POST roster-sync to gravity-scrapers with Bearer auth from repo .env
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -f .env ]]; then
  echo "Missing $ROOT/.env — copy .env.example and set SCRAPERS_SERVICE_URL + SCRAPERS_SERVICE_API_KEY" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
source ./.env
set +a
BASE="${SCRAPERS_SERVICE_URL:-}"
KEY="${SCRAPERS_SERVICE_API_KEY:-}"
if [[ -z "$BASE" || -z "$KEY" ]]; then
  echo "Set SCRAPERS_SERVICE_URL and SCRAPERS_SERVICE_API_KEY in .env" >&2
  exit 1
fi
BASE="${BASE%/}"
BODY="${1:-{}}"
exec curl -sS -X POST "${BASE}/jobs/roster-sync" \
  -H "Authorization: Bearer ${KEY}" \
  -H "Content-Type: application/json" \
  -d "${BODY}"
