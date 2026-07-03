#!/usr/bin/env bash
# Deploy gravity-ml inference from monorepo to Railway gravity-ml project.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v railway >/dev/null 2>&1; then
  echo "railway CLI required" >&2
  exit 1
fi

railway link -p gravity-ml -e production -s fdb7752c-cf01-4064-849c-94050093444a

backup=""
if [[ -f railway.toml ]]; then
  backup="$(mktemp)"
  cp railway.toml "$backup"
fi
cp railway.gravity-ml.toml railway.toml

cleanup() {
  if [[ -n "$backup" && -f "$backup" ]]; then
    mv "$backup" railway.toml
  fi
}
trap cleanup EXIT

echo "Deploying gravity-ml from monorepo (Dockerfile.gravity-ml)..."
railway up -d -c -m "Deploy monorepo gravity_ml with CFB bundle and sport routes"

echo "Done. Verify: curl https://gravity-ml-production.up.railway.app/health/ready"
