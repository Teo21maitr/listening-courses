#!/usr/bin/env bash
# Start PDF to Audio locally (backend + frontend) and print the URL to open.
#
#   ./start.sh            dev mode: Vite with hot reload on :5173, API on :8000
#   ./start.sh --prod     single server: builds the frontend, FastAPI serves it on :8000
#   ./start.sh --yes      download missing voice models without asking
#
# Ports can be changed with BACKEND_PORT / FRONTEND_PORT environment variables.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
VENV="$BACKEND/.venv"
PYTHON="$VENV/bin/python"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
MODE="dev"
ASSUME_YES=0

for arg in "$@"; do
  case "$arg" in
    --prod) MODE="prod" ;;
    --yes|-y) ASSUME_YES=1 ;;
    -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg (see --help)"; exit 1 ;;
  esac
done

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
info() { printf '\033[34m›\033[0m %s\n' "$*"; }
fail() { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# --- Prerequisites -----------------------------------------------------------
command -v ffmpeg >/dev/null || fail "ffmpeg is missing. Install it with: brew install ffmpeg"
command -v npm >/dev/null || fail "npm is missing. Install Node.js 20+ (https://nodejs.org)"

if [ ! -x "$PYTHON" ]; then
  info "Creating the Python virtual environment in backend/.venv ..."
  PY=$(command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3) || fail "python3 not found"
  "$PY" -m venv "$VENV"
  "$PYTHON" -m pip install --quiet --upgrade pip
fi
if ! "$PYTHON" -c "import fastapi, pymupdf, kokoro_onnx, piper" 2>/dev/null; then
  info "Installing backend dependencies ..."
  "$PYTHON" -m pip install --quiet -r "$BACKEND/requirements-dev.txt"
fi
if [ ! -d "$FRONTEND/node_modules" ]; then
  info "Installing frontend dependencies ..."
  (cd "$FRONTEND" && npm install --silent)
fi

missing_models=$(cd "$BACKEND" && "$PYTHON" - <<'PY'
from app.config import get_settings
from app.services.tts_service import engine_ready
settings = get_settings()
print(" ".join(lang for lang in settings.engines if not engine_ready(lang, settings)))
PY
)
if [ -n "$missing_models" ]; then
  echo "Voice models are missing for: $missing_models"
  if [ "$ASSUME_YES" -eq 1 ]; then
    reply=y
  else
    read -r -p "Download them now (a few hundred MB)? [Y/n] " reply
  fi
  case "${reply:-y}" in
    [Yy]*) (cd "$BACKEND" && "$PYTHON" scripts/download_voices.py) ;;
    *) fail "Cannot start without voice models. Run: cd backend && .venv/bin/python scripts/download_voices.py" ;;
  esac
fi

port_in_use() {
  local holder
  holder=$(lsof -nP -iTCP:"$1" -sTCP:LISTEN 2>/dev/null | awk 'NR==2 {print $1" (pid "$2")"}' || true)
  if [ -n "$holder" ]; then
    fail "Port $1 is already in use by $holder. Stop it or set ${2}=<other port>."
  fi
}
port_in_use "$BACKEND_PORT" BACKEND_PORT
if [ "$MODE" = "dev" ]; then port_in_use "$FRONTEND_PORT" FRONTEND_PORT; fi

# --- Start -------------------------------------------------------------------
pids=()
cleanup() {
  trap - INT TERM EXIT
  echo
  info "Stopping ..."
  for pid in "${pids[@]:-}"; do [ -n "$pid" ] && kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

if [ "$MODE" = "prod" ]; then
  info "Building the frontend ..."
  (cd "$FRONTEND" && npm run build --silent)
  export FRONTEND_DIST_DIR="$FRONTEND/dist"
  APP_URL="http://localhost:$BACKEND_PORT"
else
  export CORS_ORIGINS="http://localhost:$FRONTEND_PORT,http://127.0.0.1:$FRONTEND_PORT"
  export VITE_API_BASE_URL="http://localhost:$BACKEND_PORT"
  APP_URL="http://localhost:$FRONTEND_PORT"
fi

info "Starting the backend on :$BACKEND_PORT ..."
(cd "$BACKEND" && exec "$VENV/bin/uvicorn" app.main:app --port "$BACKEND_PORT" $([ "$MODE" = "dev" ] && echo --reload) --log-level warning) &
pids+=($!)

if [ "$MODE" = "dev" ]; then
  info "Starting the frontend on :$FRONTEND_PORT ..."
  (cd "$FRONTEND" && exec npm run dev --silent -- --port "$FRONTEND_PORT" --strictPort --clearScreen false --logLevel warn) &
  pids+=($!)
fi

wait_for() {  # wait_for <url> <what>
  for _ in $(seq 1 60); do
    curl -sf "$1" >/dev/null 2>&1 && return 0
    sleep 0.5
  done
  fail "The $2 did not start. Check the output above."
}
wait_for "http://localhost:$BACKEND_PORT/api/health" backend
wait_for "$APP_URL" frontend

echo
bold "PDF to Audio is running:  $APP_URL"
echo "  API: http://localhost:$BACKEND_PORT/api/health   (docs: http://localhost:$BACKEND_PORT/docs)"
echo "  Press Ctrl+C to stop."
echo

wait
