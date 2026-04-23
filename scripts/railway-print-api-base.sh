#!/usr/bin/env bash
# Print hints / Railway status so you can set VITE_API_URL on the terminal service.
# Requires: https://docs.railway.com/develop/cli
#   railway login
#   If the browser flow fails (SSH, IDE terminal, headless):  railway login --browserless
#     (CLI prints a URL + code; open the URL on any device and paste the code.)
#   cd /path/to/Gravity_Score && railway link   # pick your Gravity project + default service (any)
#
# Usage:
#   bash scripts/railway-print-api-base.sh
#   bash scripts/railway-print-api-base.sh my-api-service-name

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v railway >/dev/null 2>&1; then
  echo "Install Railway CLI: https://docs.railway.com/develop/cli" >&2
  exit 1
fi

if ! railway whoami >/dev/null 2>&1; then
  echo "Not logged in. Run one of:" >&2
  echo "  railway login" >&2
  echo "  railway login --browserless   # if browser login errors (e.g. Cursor/SSH)" >&2
  echo "Then:  railway link   (from this repo root)" >&2
  exit 1
fi

echo "=== Railway whoami ==="
railway whoami
echo ""

# Detect missing `railway link` (common when pasting multi-line instructions).
_link_check=$(railway status 2>&1) || true
if echo "$_link_check" | grep -qi 'No linked project'; then
  echo "=== Not linked to a project ===" >&2
  echo "From this repo root, run **only** this (interactive; complete the prompts):" >&2
  echo "  railway link" >&2
  echo "Then run this script again." >&2
  exit 2
fi

API_SERVICE="${1:-}"
if [ -n "$API_SERVICE" ]; then
  echo "=== Variables for service: ${API_SERVICE} (look for RAILWAY_PUBLIC_DOMAIN if listed) ==="
  railway variable list -s "$API_SERVICE" -k 2>/dev/null || railway variable list -s "$API_SERVICE" || true
  echo ""
fi

echo "=== Project status (JSON may include domains / services) ==="
if railway status --json 2>/dev/null | head -c 12000; then
  echo ""
else
  railway status || true
  echo ""
fi

echo "=== Next steps ==="
echo "1. In Railway dashboard: open your API service → Settings → Networking → copy the HTTPS URL (e.g. https://….up.railway.app)."
echo "2. On your TERMINAL service (root gravity-terminal): Variables → VITE_API_URL = that URL with optional /v1 suffix."
echo "3. Optional CLI for a specific service name:  bash scripts/railway-print-api-base.sh YOUR_API_SERVICE_NAME"
echo "4. Dashboard:  railway open -p"
