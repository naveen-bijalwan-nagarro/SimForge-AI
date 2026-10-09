#!/usr/bin/env bash
# Start an interactive Codex session in codex_sandbox/ with the SimForge MCP server attached.
# Usage: bash scripts/codex-sandbox.sh ["optional first prompt"]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="$ROOT/.venv/Scripts/python.exe"
command -v codex >/dev/null || { echo "Install Codex: npm install -g @openai/codex && codex login"; exit 1; }
codex login status 2>&1 | grep -q "Logged in" || codex login
mkdir -p "$ROOT/codex_sandbox/drafts"
exec codex -C "$ROOT/codex_sandbox" --sandbox workspace-write \
  -c "mcp_servers.simforge.command='$PY'" \
  -c "mcp_servers.simforge.args=['$ROOT/scripts/mcp_simforge.py']" \
  -c "mcp_servers.simforge.env={SIMFORGE_DATA_DIR='$ROOT/data'}" \
  "$@"
