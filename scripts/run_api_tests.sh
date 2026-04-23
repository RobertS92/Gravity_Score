#!/usr/bin/env bash
# Run gravity_api pytest suite. Prefer project .venv (PEP 668 safe).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=.
if [[ -x "$ROOT/.venv/bin/pytest" ]]; then
  exec "$ROOT/.venv/bin/pytest" gravity_api/tests -q "$@"
fi
exec python3 -m pytest gravity_api/tests -q "$@"
