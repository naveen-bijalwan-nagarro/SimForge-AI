#!/usr/bin/env bash
# One-time setup; safe to re-run. Reuses a working Python 3.12+ .venv and rebuilds a broken or
# older one. RECREATE=1 forces a clean rebuild; PYTHON_BIN chooses the interpreter.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-python3}"
ok() { "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1; }
if [ -d .venv ]; then
  if [ "${RECREATE:-}" = 1 ] || ! ok .venv/bin/python; then
    echo ".venv is missing a working Python 3.12+; rebuilding it"
    rm -rf .venv
  else
    echo "Reusing the existing .venv"
  fi
fi
if [ ! -x .venv/bin/python ]; then
  ok "$PYTHON_BIN" || { echo "Python 3.12+ required; run: PYTHON_BIN=/path/to/python3.12 bash scripts/setup.sh" >&2; exit 1; }
  "$PYTHON_BIN" -m venv .venv
fi
.venv/bin/python -c 'import pip' >/dev/null 2>&1 || .venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install -r requirements-lock.txt
(cd frontend && npm ci && npm run build)
printf 'Ready. Run bash scripts/start.sh and open http://127.0.0.1:8000\n'
