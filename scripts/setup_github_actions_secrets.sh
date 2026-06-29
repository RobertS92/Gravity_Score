#!/usr/bin/env bash
# Sync required GitHub Actions secrets from local .env (run once after clone / key rotation).
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "Missing .env — copy .env.example and fill in values first." >&2
  exit 1
fi

get_env() {
  python3 - "$1" <<'PY'
import sys
from pathlib import Path
from dotenv import dotenv_values
key = sys.argv[1]
val = (dotenv_values(Path(".env")).get(key) or "").strip()
print(val, end="")
PY
}

set_secret() {
  local name="$1"
  local value
  value="$(get_env "$name")"
  if [[ -z "${value// }" ]]; then
    echo "skip $name (empty)"
    return 0
  fi
  gh secret set "$name" --body "$value"
  echo "set $name"
}

for name in GRAVITY_INTERNAL_API_KEY GRAVITY_API_URL ML_SERVICE_URL ML_SERVICE_API_KEY FIRECRAWL_API_KEY CFBD_API_KEY PG_DSN; do
  set_secret "$name"
done

echo "Done. Re-run: gh workflow run nightly-pipeline.yml"
