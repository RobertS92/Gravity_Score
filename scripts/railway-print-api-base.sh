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

echo "=== Service summary (from railway status --json) ==="
_json=$(railway status --json 2>/dev/null) || _json=""
if [ -n "$_json" ] && command -v python3 >/dev/null 2>&1; then
  printf '%s\n' "$_json" | python3 <<'PY'
import json, sys

def main():
    raw = sys.stdin.read()
    if not raw.strip():
        print("(empty status JSON)")
        return
    try:
        d = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"(invalid JSON: {e})")
        return
    edges = (((d.get("environments") or {}).get("edges")) or [])
    rows = []
    for ee in edges:
        node = (ee or {}).get("node") or {}
        env_name = node.get("name") or "?"
        for se in ((node.get("serviceInstances") or {}).get("edges") or []):
            n = (se or {}).get("node") or {}
            name = n.get("serviceName") or "?"
            ld = n.get("latestDeployment") or {}
            st = ld.get("status") or "?"
            doms = (n.get("domains") or {}).get("serviceDomains") or []
            urls = []
            for x in doms:
                if isinstance(x, dict) and x.get("domain"):
                    urls.append(x["domain"])
                elif isinstance(x, str):
                    urls.append(x)
            rows.append((env_name, name, st, urls))
    if not rows:
        print("(no service instances in JSON)")
        return
    for env_name, name, st, urls in rows:
        u = ", ".join(urls) if urls else "(generate public URL in Railway → Networking)"
        print(f"  [{env_name}] {name}")
        print(f"      latestDeployment.status: {st}")
        print(f"      public URL(s): {u}")
    print()
    names = [r[1] for r in rows]
    api_guess = None
    for cand in ("Gravity_Score", "gravity_api", "Gravity API"):
        if cand in names:
            api_guess = cand
            break
    if api_guess:
        print("Suggested reference for the FRONTEND service Variables (if that API serves /v1):")
        print("  VITE_API_URL=https://${{" + api_guess + ".RAILWAY_PUBLIC_DOMAIN}}/v1")
    else:
        print("Set VITE_API_URL on your frontend service to your real API HTTPS base + /v1 (see dashboard Networking).")

main()
PY
else
  echo "(Install python3 for a short summary; dumping raw JSON.)"
  printf '%s\n' "$_json"
fi
echo ""

echo "=== Next steps ==="
echo "1. If latestDeployment.status is FAILED for the frontend: open that service → Deployments → failed build logs (often missing VITE_API_URL)."
echo "2. API URL: Dashboard → API service (e.g. Gravity_Score) → Networking → copy HTTPS URL, or use reference variable on the frontend service."
echo "3. List variables:  railway variable list -s 'Gravity_Score' -k"
echo "4. Dashboard:        railway open -p"
