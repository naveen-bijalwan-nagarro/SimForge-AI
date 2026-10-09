#!/usr/bin/env bash
# Start SimForge AI: React UI + API on http://127.0.0.1:${PORT:-8000}. The UI is rebuilt first when it
# is missing or older than frontend/src. DEV=1 runs the API with auto-reload plus the Vite hot-reload
# UI on http://127.0.0.1:${UI_PORT:-5173}. Ctrl+C stops everything.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${PORT:-8000}"; UI_PORT="${UI_PORT:-5173}"
if ! .venv/bin/python -c 'import sys, fastapi, uvicorn, simpy; sys.exit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1; then
  echo "The Python environment (.venv) is missing, broken or incomplete. Run: bash scripts/setup.sh" >&2
  exit 1
fi
install_frontend() {
  [ -d frontend/node_modules/vite ] || (cd frontend && npm ci)
}
# Only local development auto-enables Codex; production requires explicit opt-in.
if [ "${SIMFORGE_ENV:-development}" != production ] && [ -z "${SIMFORGE_CODEX_ENABLED:-}" ] && command -v codex >/dev/null; then export SIMFORGE_CODEX_ENABLED=1; fi
LOGINS="Sign in as admin/admin123 (Admin / Trainer) or learner/learner123. Ctrl+C stops it."
if [ "${DEV:-}" = 1 ]; then
  install_frontend
  # Vite proxies /api to this API port (see frontend/vite.config.js).
  (cd frontend && SIMFORGE_API_URL="http://127.0.0.1:$PORT" exec node node_modules/vite/bin/vite.js --host 127.0.0.1 --port "$UI_PORT" --strictPort) &
  VITE_PID=$!
  trap 'kill "$VITE_PID" 2>/dev/null || true' EXIT INT TERM
  echo "SimForge AI (development): UI with hot reload http://127.0.0.1:$UI_PORT   API http://127.0.0.1:$PORT/docs"
  echo "$LOGINS"
  .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port "$PORT" --reload --reload-dir backend
else
  if [ ! -f frontend/dist/index.html ] || [ -n "$(find frontend/src frontend/index.html frontend/vite.config.js frontend/package-lock.json -newer frontend/dist/index.html 2>/dev/null | head -1)" ]; then
    echo "Building the React UI (it changed since the last build)..."
    install_frontend
    (cd frontend && npm run build)
  fi
  echo "SimForge AI: http://127.0.0.1:$PORT   (UI and API on one server; API docs at /docs)"
  echo "$LOGINS"
  exec .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port "$PORT"
fi
