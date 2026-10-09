"""Scenario pack toolkit for authors and for Codex in the sandbox.

  python scripts/scenario_kit.py format
  python scripts/scenario_kit.py new <key> --title "Title" [--style voxel]
  python scripts/scenario_kit.py validate <file.yaml>
  python scripts/scenario_kit.py test <file.yaml>
  python scripts/scenario_kit.py simulate <file.yaml>
  python scripts/scenario_kit.py submit <file.yaml> [--note "..."]    # draft for admin approval
  python scripts/scenario_kit.py install <file.yaml>                  # developer route: scenario_packs/
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import mcp_server, packs  # noqa: E402

DRAFTS = ROOT / "codex_sandbox" / "drafts"
TEMPLATE = """- key: {key}
  title: {title}
  category: Agentic Simulation Lab
  environment_style: {style}
  summary: Describe the operation, what fails and what learners must protect.
  unit: work items
  impact: impact units
  budget: 6000
  nodes:
    - [intake, Intake, investigator, 5, log, Intake system]
    - [processing, Processing, operations, 5, sensor, Processing line]
    - [delivery, Delivery, operations, 5, map, Delivery tracker]
    - [customers, Customer outcome, finance, 6, kpi, Customer dashboard]
  edges: [[intake, processing], [processing, delivery], [delivery, customers]]
  incident: {{node: intake, cause: Describe the hidden root cause in one sentence., signal: what learners first notice}}
  actions:
    - [restore_intake, Restore intake, intake, repair, 2000, 4, Fix the root cause.]
    - [inspect_intake, Inspect intake signals, intake, inspect, 200, 0, Gather evidence.]
    - [bypass_processing, Open a manual processing lane, processing, reroute, 1400, 2, Reduced-capacity workaround.]
  decoys: [A scheduled maintenance window, An unrelated demand spike]
"""


def load(path):
    return Path(path).read_text(encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="SimForge scenario pack toolkit")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("format")
    new = sub.add_parser("new")
    new.add_argument("key")
    new.add_argument("--title", default="New simulation world")
    new.add_argument("--style", choices=["workflow", "voxel", "service_app"], default="workflow")
    for name in ("validate", "test", "simulate", "install"):
        sub.add_parser(name).add_argument("file")
    submit = sub.add_parser("submit")
    submit.add_argument("file")
    submit.add_argument("--note", default="")
    args = parser.parse_args(argv)

    if args.cmd == "format":
        print(mcp_server.get_pack_format())
    elif args.cmd == "new":
        DRAFTS.mkdir(parents=True, exist_ok=True)
        target = DRAFTS / f"{args.key}.yaml"
        target.write_text(TEMPLATE.format(key=args.key, title=args.title, style=args.style), encoding="utf-8")
        print(f"Created {target}")
    elif args.cmd == "validate":
        result = mcp_server.validate_scenario(load(args.file))
        print(json.dumps(result, indent=2))
        return 1 if any(r["problems"] for r in result) else 0
    elif args.cmd == "test":
        result = mcp_server.run_scenario_tests(load(args.file))
        for r in result:
            print(f"{r['key']}: {r['passed']}/{r['total']} checks passed")
            for f in r["failures"]:
                print(f"  FAIL [{f['category']}] {f['name']}: {f['detail']}")
        return 1 if any(r["failures"] for r in result) else 0
    elif args.cmd == "simulate":
        print(json.dumps(mcp_server.generate_simulator(load(args.file)), indent=2))
    elif args.cmd == "submit":
        print(json.dumps(mcp_server.submit_for_approval(load(args.file), args.note), indent=2))
    elif args.cmd == "install":
        result = mcp_server.run_scenario_tests(load(args.file))
        if any(r["failures"] for r in result):
            print("Refusing to install: tests are failing. Run `test` first.")
            return 1
        packs.USER_DIR.mkdir(parents=True, exist_ok=True)
        target = packs.USER_DIR / Path(args.file).name
        shutil.copyfile(args.file, target)
        print(f"Installed {target}. Restart SimForge or open the catalog; file packs load automatically.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
