#!/usr/bin/env bash
#
# ---------------------------------------------------------------------------
# HOW TO RUN (do not paste this script into zsh/bash by hand)
#
#   cd /path/to/Gravity_Score
#   Copy the URI from Supabase → Connect (URI). Replace only [YOUR-PASSWORD].
#   Do not use placeholder hostnames like db.REF — the middle part is your real ~20-char project ref.
#   export PG_DSN='postgresql://postgres:.....@db.abcdefghijklmnop.supabase.co:5432/postgres'
#   bash migrations/apply_all.sh
#
# Pasting the file into an interactive zsh can error with:
#   zsh: event not found: /usr/bin/env
# because zsh treats "!" as history expansion on the shebang line.
#
# Also: do NOT paste this file into the Supabase SQL Editor (SQL only).
# In Supabase: run each 001_*.sql and 002_*.sql file contents in order.
# ---------------------------------------------------------------------------
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
if [[ -z "${PG_DSN:-}" ]]; then
  echo "Set PG_DSN before running." >&2
  echo "  Supabase: Dashboard → your project → Connect → copy the Postgres URI, substitute your password." >&2
  echo "  Host must look like db.<your-ref>.supabase.co (not db.REF or db.YOUR_PROJECT_REF — those are not real)." >&2
  echo "  Encode special chars in the password (* as %2A, @ as %40)." >&2
  exit 1
fi
export PGOPTIONS="${PGOPTIONS:-}"
psql "$PG_DSN" -v ON_ERROR_STOP=1 -f "$ROOT/001_gravity_nil_terminal.sql"
psql "$PG_DSN" -v ON_ERROR_STOP=1 -f "$ROOT/002_athlete_gravity_money_company_brand.sql"
psql "$PG_DSN" -v ON_ERROR_STOP=1 -f "$ROOT/003_roster_builds.sql"
psql "$PG_DSN" -v ON_ERROR_STOP=1 -f "$ROOT/004_athlete_events.sql"
echo "Applied 001 + 002 + 003 + 004."
