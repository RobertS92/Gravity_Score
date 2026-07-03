#!/usr/bin/env bash
# Stage a minimal gravity-ml deploy context (includes gitignored model.pkl files).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGE="${1:-/tmp/gravity_ml_deploy_stage}"

rm -rf "$STAGE"
mkdir -p "$STAGE"

cp "$ROOT/Dockerfile.gravity-ml" "$STAGE/Dockerfile"
# Bust Railway build cache so model.pkl COPY layer rebuilds.
sed -i '' "s/^ARG CACHEBUST=.*/ARG CACHEBUST=$(date +%s)/" "$STAGE/Dockerfile" 2>/dev/null || \
  sed -i "s/^ARG CACHEBUST=.*/ARG CACHEBUST=$(date +%s)/" "$STAGE/Dockerfile"
cp "$ROOT/railway.gravity-ml.toml" "$STAGE/railway.toml"
cp -R "$ROOT/gravity_ml" "$ROOT/gravity_composite" "$ROOT/config" "$STAGE/"
mkdir -p "$STAGE/models/bundles"
cp "$ROOT/models/bundles/index.json" "$STAGE/models/bundles/"

while IFS= read -r key; do
  ver=$(python3 -c "import json; print(json.load(open('$ROOT/models/bundles/index.json'))['champions']['$key'])")
  src="$ROOT/models/bundles/$key/$ver"
  dst="$STAGE/models/bundles/$key/$ver"
  mkdir -p "$dst"
  cp "$src"/* "$dst/"
  if [[ ! -f "$dst/model.pkl" ]]; then
    echo "missing model.pkl for $key/$ver" >&2
    exit 1
  fi
done < <(python3 -c "import json; print('\n'.join(json.load(open('$ROOT/models/bundles/index.json'))['champions']))")

echo "Staged ML deploy at $STAGE ($(du -sh "$STAGE" | cut -f1))"
