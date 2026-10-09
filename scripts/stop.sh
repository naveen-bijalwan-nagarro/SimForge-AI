#!/usr/bin/env bash
# Stop SimForge AI completely: every API server (uvicorn) and Vite dev server started from this
# project, with their child processes. LIST=1 only shows them. Works from any directory.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
pids=()
for pid in $(pgrep -f 'uvicorn backend\.main:app|vite' 2>/dev/null); do
  [ "$pid" = "$$" ] && continue
  cwd="$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p')"
  cmd="$(ps -o command= -p "$pid" 2>/dev/null)"
  case "$cwd/ $cmd" in *"$ROOT"*) pids+=("$pid"); echo "  $pid  $cmd" | cut -c1-140 ;; esac
done
if [ ${#pids[@]} -eq 0 ]; then echo "No SimForge servers are running."; exit 0; fi
[ "${LIST:-}" = 1 ] && exit 0
for pid in "${pids[@]}"; do
  pkill -TERM -P "$pid" 2>/dev/null
  kill -TERM "$pid" 2>/dev/null
done
sleep 2
for pid in "${pids[@]}"; do
  if kill -0 "$pid" 2>/dev/null; then pkill -KILL -P "$pid" 2>/dev/null; kill -KILL "$pid" 2>/dev/null; fi
done
echo "SimForge stopped: ${#pids[@]} process(es)."
