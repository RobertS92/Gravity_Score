#!/usr/bin/env bash
# Pretty-print GET /jobs/progress from gravity-scrapers (ETA, %, current team).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -f .env ]]; then
  echo "Missing $ROOT/.env — set SCRAPERS_SERVICE_URL and SCRAPERS_SERVICE_API_KEY" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
source ./.env
set +a
BASE="${SCRAPERS_SERVICE_URL:-}"
KEY="${SCRAPERS_SERVICE_API_KEY:-}"
if [[ -z "$BASE" || -z "$KEY" ]]; then
  echo "Set SCRAPERS_SERVICE_URL and SCRAPERS_SERVICE_API_KEY" >&2
  exit 1
fi
BASE="${BASE%/}"
curl -sS -H "Authorization: Bearer ${KEY}" "${BASE}/jobs/progress" | python3 -m json.tool
