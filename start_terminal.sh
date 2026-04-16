#!/usr/bin/env bash
# ============================================================
# Gravity Terminal — Production-grade local startup
# Starts both the FastAPI backend and Vite dev server
# Usage: ./start_terminal.sh
# ============================================================
set -e

REPO="$(cd "$(dirname "$0")" && pwd)"
VENV="$REPO/venv/bin/python"
UVICORN="$REPO/venv/bin/python -m uvicorn"
TERMINAL_DIR="$REPO/gravity-terminal"

# ── Colours ─────────────────────────────────────────────────
G="\033[0;32m"; B="\033[0;34m"; Y="\033[0;33m"; R="\033[0;31m"; NC="\033[0m"
info()    { echo -e "${B}[GRAVITY]${NC} $*"; }
success() { echo -e "${G}[GRAVITY]${NC} $*"; }
warn()    { echo -e "${Y}[GRAVITY]${NC} $*"; }
error()   { echo -e "${R}[GRAVITY]${NC} $*"; }

# ── Kill old processes ──────────────────────────────────────
kill_port() {
  local port=$1
  local pid
  pid=$(lsof -ti:"$port" 2>/dev/null || true)
  if [ -n "$pid" ]; then
    warn "Killing existing process on port $port (pid $pid)"
    kill "$pid" 2>/dev/null || true
    sleep 1
  fi
}

kill_port 8000
kill_port 5173

# ── Verify virtual environment ──────────────────────────────
if [ ! -f "$VENV" ]; then
  error "Python venv not found at $VENV"
  error "Run: python3 -m venv venv && venv/bin/pip install -r requirements-gravity-api.txt"
  exit 1
fi

# ── Start FastAPI backend ───────────────────────────────────
info "Starting Gravity API on port 8000..."
cd "$REPO"
PYTHONPATH="$REPO" $UVICORN gravity_api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --log-level warning \
  --reload \
  > /tmp/gravity_api.log 2>&1 &
API_PID=$!
info "API PID: $API_PID → logs: /tmp/gravity_api.log"

# Wait for API to be healthy
MAX=20
for i in $(seq 1 $MAX); do
  if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    success "API healthy at http://localhost:8000"
    break
  fi
  if [ "$i" -eq "$MAX" ]; then
    error "API failed to start after ${MAX}s. Check /tmp/gravity_api.log"
    exit 1
  fi
  sleep 1
done

# ── Start Vite dev server ────────────────────────────────────
info "Starting Gravity Terminal (Vite) on port 5173..."
cd "$TERMINAL_DIR"
npm run dev -- --port 5173 > /tmp/gravity_terminal.log 2>&1 &
VITE_PID=$!
info "Vite PID: $VITE_PID → logs: /tmp/gravity_terminal.log"

# Wait for Vite
for i in $(seq 1 10); do
  if curl -sf http://localhost:5173 > /dev/null 2>&1; then
    success "Terminal ready at http://localhost:5173"
    break
  fi
  sleep 1
done

echo ""
success "══════════════════════════════════════════"
success " Gravity Terminal is running"
success "  Frontend:  http://localhost:5173"
success "  API:       http://localhost:8000"
success "  API Docs:  http://localhost:8000/docs"
success ""
success "  Login:     demo@gravity.local  (no password)"
success "  Auth:      JWT auto-loaded from VITE_API_BEARER_TOKEN"
success "══════════════════════════════════════════"
echo ""
info "To stop: kill $API_PID $VITE_PID"
info "API logs:      tail -f /tmp/gravity_api.log"
info "Terminal logs: tail -f /tmp/gravity_terminal.log"

# Trap to kill children on Ctrl+C
trap "info 'Stopping...'; kill $API_PID $VITE_PID 2>/dev/null; exit 0" INT TERM

wait $API_PID $VITE_PID
