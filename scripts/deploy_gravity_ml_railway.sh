#!/usr/bin/env bash
# Deploy gravity-ml inference from monorepo to Railway gravity-ml project.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v railway >/dev/null 2>&1; then
  echo "railway CLI required" >&2
  exit 1
fi

STAGE="/tmp/gravity_ml_deploy_stage"
bash scripts/stage_ml_deploy_bundle.sh "$STAGE"

railway link -p gravity-ml -e production -s fdb7752c-cf01-4064-849c-94050093444a

echo "Deploying gravity-ml staged bundle ($(du -sh "$STAGE" | cut -f1))..."
(
  cd "$STAGE"
  railway link -p gravity-ml -e production -s fdb7752c-cf01-4064-849c-94050093444a
  railway up -d -c --no-gitignore -m "Deploy gravity_ml sport value bundles with model weights"
)

echo "Done. Verify: curl https://gravity-ml-production.up.railway.app/health/ready"
