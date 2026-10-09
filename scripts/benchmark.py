"""Reproducible local CPU benchmark; no claims about cloud concurrency."""

import argparse
import json
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.catalog import WORLDS
from backend.engine import simulate

parser = argparse.ArgumentParser()
parser.add_argument("--population", type=int, default=1000)
parser.add_argument("--horizon", type=int, default=45)
parser.add_argument("--output", type=Path)
args = parser.parse_args()
if not 20 <= args.population <= 5000 or not 20 <= args.horizon <= 120:
    parser.error("Population must be 20–5000 and horizon 20–120")
results = []
for spec in WORLDS[:5]:
    started = time.perf_counter()
    result = simulate(spec, 2026, args.population, args.horizon, [])
    results.append(
        dict(
            world=spec["key"],
            seconds=round(time.perf_counter() - started, 4),
            nodes=len(result["nodes"]),
            events=len(result["events"]),
            completed=result["metrics"]["completed"],
        )
    )
report = dict(
    python=platform.python_version(),
    platform=platform.platform(),
    population=args.population,
    horizon=args.horizon,
    runs=results,
    note="Single-process wall-clock time for full replay. Not a load/concurrency or cloud benchmark.",
)
if args.output:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
