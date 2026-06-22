#!/usr/bin/env bash
# Copy monorepo packages into gravity_api/docker-bundle for Railway builds
# when the service Root Directory is gravity_api/ (not repo root).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/gravity_api/docker-bundle"
rm -rf "$DEST"
mkdir -p "$DEST"
cp -R "$ROOT/gravity_composite" "$ROOT/gravity_ml" "$ROOT/config" "$DEST/"
echo "Synced docker-bundle → gravity_api/docker-bundle/"
