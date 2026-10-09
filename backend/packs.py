"""Scenario packs: worlds described as YAML data, validated and tested before use.

Built-in packs live in ``backend/packs``. Your own packs go in ``scenario_packs/`` at the
project root (see docs/ADDING_USE_CASES.md). Packs never contain executable code; consequence
rules use the small condition language in ``rules.py``.
"""

import copy
import re
from pathlib import Path

import networkx as nx
import yaml

from . import rules as rulebook
from .connections import validate_template
from .settings import ROOT

BUILTIN_DIR = ROOT / "backend" / "packs"
USER_DIR = ROOT / "scenario_packs"
EFFECTS = {"repair", "contain", "reroute", "boost", "inspect"}
MODALITIES = {
    "log",
    "email",
    "sensor",
    "image",
    "video",
    "map",
    "ticket",
    "document",
    "transaction",
    "graph",
    "chat",
    "kpi",
}
VISUALS = {"surface", "tower", "turbine", "traffic", "thermal", "aerial", "cells"}
KEY = re.compile(r"^[a-z][a-z0-9_]{2,48}$")
NODE_ID = re.compile(r"^[a-z][a-z0-9_]{0,29}$")
_cache = {}


def roles():
    from .engine import ROLES

    return ROLES


def _node(n):
    if isinstance(n, dict):
        return dict(n)
    keys = ["id", "label", "role", "capacity", "modality", "source"]
    node = dict(zip(keys, n))
    node.setdefault("capacity", 5)
    return node


def _action(a):
    if isinstance(a, dict):
        return dict(a)
    return dict(zip(["id", "label", "target", "effect", "cost", "duration", "description"], a))


def expand(item, source="pack"):
    """Turn the compact authoring format into a full world specification."""
    spec = copy.deepcopy(item)
    spec["kind"] = "world"
    spec.setdefault("category", "Custom Worlds")
    spec.setdefault("difficulty", "Expert")
    spec.setdefault(
        "objective",
        "Investigate the disruption, coordinate specialists, and recover service within the response budget.",
    )
    spec["nodes"] = [_node(n) for n in spec.get("nodes", [])]
    for n in spec["nodes"]:
        n.setdefault("modality", "log")
        n.setdefault("source", n.get("label", ""))
    spec["edges"] = [
        e if isinstance(e, dict) else dict(source=e[0], target=e[1]) for e in spec.get("edges", [])
    ]
    spec["actions"] = [_action(a) for a in spec.get("actions", [])]
    for a in spec["actions"]:
        a.setdefault("duration", 1)
        a.setdefault("description", a.get("label", ""))
    incident = dict(spec.get("incident") or {})
    incident.setdefault("tick", 5)
    incident.setdefault("severity", 0.78)
    spec["incident"] = incident
    spec["incidents_extra"] = [
        dict(dict(tick=12, severity=0.6), **x) for x in spec.pop("extra_incidents", []) or []
    ] or spec.get("incidents_extra", [])
    spec.setdefault("secondary", None)
    spec.setdefault("unit", "tasks")
    spec.setdefault("budget", 10000)
    spec.setdefault("rules", [])
    spec.setdefault("decoys", [])
    spec.setdefault("building_blocks", [])
    spec.setdefault("objectives", [])
    spec["modalities"] = sorted(
        {n["modality"] for n in spec["nodes"]} | {"event_log", "time_series", "graph"}
    )
    spec.setdefault("source", f"Scenario pack: {source}")
    spec.setdefault("license", "Synthetic scenario; no external dataset required")
    spec["pack"] = source
    return spec


def validate_world(spec):
    """Structural validation. Returns a list of problems (empty when valid)."""
    problems = []
    known_roles = roles()
    for field in ("key", "title", "summary", "nodes", "edges", "incident", "actions", "unit"):
        if not spec.get(field):
            problems.append(f"Missing required field '{field}'")
    if problems:
        return problems
    if not KEY.match(str(spec["key"])):
        problems.append("Key must be lowercase letters, digits or underscores (3-49 characters)")
    if not 3 <= len(spec["nodes"]) <= 16:
        problems.append("A world needs between 3 and 16 systems")
    ids = [n.get("id") for n in spec["nodes"]]
    if len(ids) != len(set(ids)):
        problems.append("System ids must be unique")
    for n in spec["nodes"]:
        if not NODE_ID.match(str(n.get("id", ""))):
            problems.append(f"Invalid system id '{n.get('id')}'")
        if n.get("role") not in known_roles:
            problems.append(
                f"System '{n.get('id')}' has unknown role '{n.get('role')}'. Use one of {', '.join(known_roles)}"
            )
        if not isinstance(n.get("capacity"), int) or not 1 <= n["capacity"] <= 30:
            problems.append(f"System '{n.get('id')}' capacity must be an integer 1-30")
        if n.get("modality", "log") not in MODALITIES:
            problems.append(
                f"System '{n.get('id')}' evidence modality must be one of {', '.join(sorted(MODALITIES))}"
            )
    idset = set(ids)
    for e in spec["edges"]:
        if e.get("source") not in idset or e.get("target") not in idset:
            problems.append(f"Edge {e.get('source')} -> {e.get('target')} references unknown systems")
    if not problems:
        graph = nx.DiGraph()
        graph.add_nodes_from(ids)
        graph.add_edges_from((e["source"], e["target"]) for e in spec["edges"])
        if not nx.is_directed_acyclic_graph(graph):
            cycle = nx.find_cycle(graph)
            problems.append(
                "Dependencies contain a cycle: " + " -> ".join(a for a, _ in cycle) + f" -> {cycle[0][0]}"
            )
        if not nx.is_weakly_connected(graph):
            problems.append("Every system must connect to the workflow")
    incident = spec["incident"]
    if incident.get("node") not in idset:
        problems.append("Incident node must be one of the systems")
    if not 0.1 <= float(incident.get("severity", 0)) <= 0.95:
        problems.append("Incident severity must be between 0.1 and 0.95")
    if not 0 <= float(incident.get("tick", -1)) <= 60:
        problems.append("Incident minute must be between 0 and 60")
    if len(str(incident.get("cause", ""))) < 10:
        problems.append("Incident needs a hidden cause of at least 10 characters")
    for x in spec.get("incidents_extra", []):
        if x.get("node") not in idset:
            problems.append(f"Extra incident references unknown system '{x.get('node')}'")
        if len(str(x.get("cause", ""))) < 10:
            problems.append("Each extra incident needs a hidden cause")
    if spec.get("secondary") and spec["secondary"] not in idset:
        problems.append("Secondary cascade system must be one of the systems")
    action_ids = [a.get("id") for a in spec["actions"]]
    if len(action_ids) != len(set(action_ids)):
        problems.append("Action ids must be unique")
    if len(action_ids) < 2:
        problems.append("Provide at least two response actions")
    for a in spec["actions"]:
        if a.get("target") not in idset:
            problems.append(f"Action '{a.get('id')}' targets unknown system '{a.get('target')}'")
        if a.get("effect") not in EFFECTS:
            problems.append(
                f"Action '{a.get('id')}' effect must be one of {', '.join(sorted(EFFECTS))}"
            )
        if not isinstance(a.get("cost"), (int, float)) or a["cost"] < 0:
            problems.append(f"Action '{a.get('id')}' needs a non-negative cost")
        if not isinstance(a.get("duration"), (int, float)) or not 0 <= a["duration"] <= 30:
            problems.append(f"Action '{a.get('id')}' duration must be 0-30 minutes")
    budget = spec.get("budget", 10000)
    if not isinstance(budget, (int, float)) or not 1000 <= budget <= 100000:
        problems.append("Budget must be between 1,000 and 100,000 units")
    problems.extend(rulebook.validate(spec.get("rules"), idset))
    problems.extend(validate_template(spec.get("entity")))
    for emit in spec.get("emits", []):
        if emit.get("node") not in idset or not emit.get("signal"):
            problems.append("Each emitted signal needs a 'signal' name and an existing 'node'")
    if spec.get("visual") and spec["visual"] not in VISUALS:
        problems.append(f"Visual must be one of {', '.join(sorted(VISUALS))}")
    for node_id, kind in (spec.get("visuals") or {}).items():
        if node_id not in idset or kind not in VISUALS:
            problems.append(f"Visual override '{node_id}: {kind}' is invalid")
    if spec["incident"].get("cause") in spec.get("decoys", []):
        problems.append("Decoy explanations must differ from the real cause")
    return problems


def scenario_tests(spec, seed=101, population=60, horizon=35):
    """Behavioural tests a world must pass before it can be published."""
    from .engine import simulate

    checks = []

    def check(name, category, passed, detail=""):
        checks.append(dict(name=name, category=category, passed=bool(passed), detail=detail))

    problems = validate_world(spec)
    check(
        "Schema and graph are valid",
        "structure",
        not problems,
        "; ".join(problems[:6]) or "All structural rules satisfied",
    )
    if problems:
        return checks
    try:
        baseline = simulate(spec, seed, population, horizon, [])
    except Exception as e:  # noqa: BLE001 - report any engine failure as a failed test
        check("Simulation executes", "execution", False, str(e)[:300])
        return checks
    check("Simulation executes", "execution", True, f"{len(baseline['events'])} events")
    check(
        "Incident is injected",
        "causality",
        any(e["kind"] == "incident" for e in baseline["events"]),
        "Hidden cause becomes observable",
    )
    root = spec["incident"]["node"]
    downstream = [
        e for e in baseline["events"] if e["kind"] == "degradation" and e["node"] != root
    ]
    check(
        "Disruption propagates downstream",
        "causality",
        downstream,
        f"{len({e['node'] for e in downstream})} dependent systems degrade",
    )
    repairs = [a for a in spec["actions"] if a["effect"] == "repair" and a["target"] == root]
    check(
        "Root cause has a repair action",
        "solvability",
        repairs,
        repairs[0]["label"] if repairs else "Add an action with effect 'repair' on the incident node",
    )
    inspects = [a for a in spec["actions"] if a["effect"] == "inspect"]
    check(
        "Investigation action exists",
        "solvability",
        inspects,
        "Learners can gather evidence before acting" if inspects else "Add an 'inspect' action",
    )
    if repairs:
        fixed = simulate(
            spec,
            seed,
            population,
            horizon,
            [dict(action_id=repairs[0]["id"], tick=spec["incident"]["tick"] + 1)],
        )
        check(
            "Correct response reduces impact",
            "outcome",
            fixed["metrics"]["loss"] < baseline["metrics"]["loss"]
            and fixed["metrics"]["service"] > baseline["metrics"]["service"],
            f"Impact {baseline['metrics']['loss']:.0f} -> {fixed['metrics']['loss']:.0f}",
        )
        check(
            "Budget allows the root-cause repair",
            "outcome",
            repairs[0]["cost"] <= spec.get("budget", 10000),
            f"Repair costs {repairs[0]['cost']} of {spec.get('budget', 10000)}",
        )
    again = simulate(spec, seed, population, horizon, [])
    check(
        "Replay is deterministic",
        "reproducibility",
        again["history"] == baseline["history"],
        "Same seed and decisions produce the same world",
    )
    check(
        "Hidden cause is not shown to learners",
        "integrity",
        all(spec["incident"]["cause"] not in e["message"] for e in baseline["events"]),
        "Ground truth stays in the debrief",
    )
    check(
        "Distractor explanations provided",
        "assessment",
        len(spec.get("decoys", [])) >= 2,
        f"{len(spec.get('decoys', []))} decoys for the diagnosis step",
    )
    return checks


def _load_file(path):
    items = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if isinstance(items, dict):
        items = items.get("scenarios", [items])
    return items


def load(directory):
    """Load and validate every pack in a directory. Cached by file modification time."""
    directory = Path(directory)
    if not directory.exists():
        return [], []
    files = sorted(p for p in directory.glob("*.y*ml") if p.is_file())
    stamp = tuple((p.name, p.stat().st_mtime_ns) for p in files)
    if _cache.get(str(directory), (None,))[0] == stamp:
        return copy.deepcopy(_cache[str(directory)][1])
    specs, errors = [], []
    for path in files:
        try:
            items = _load_file(path)
        except yaml.YAMLError as e:
            errors.append(dict(file=path.name, key=None, problems=[f"YAML error: {e}"]))
            continue
        for item in items:
            spec = expand(item, path.name)
            problems = validate_world(spec)
            if problems:
                errors.append(dict(file=path.name, key=item.get("key"), problems=problems))
            else:
                specs.append(spec)
    _cache[str(directory)] = (stamp, (specs, errors))
    return copy.deepcopy(specs), copy.deepcopy(errors)


def builtin():
    return load(BUILTIN_DIR)


def user_packs():
    return load(USER_DIR)


def to_yaml(spec):
    """Serialize a world back to the authoring format for export or editing."""
    keep = {
        k: v
        for k, v in spec.items()
        if k not in {"kind", "modalities", "source", "license", "pack", "flagship"}
    }
    keep["nodes"] = [
        [n["id"], n["label"], n["role"], n["capacity"], n.get("modality", "log"), n.get("source", "")]
        for n in spec["nodes"]
    ]
    keep["edges"] = [[e["source"], e["target"]] for e in spec["edges"]]
    keep["actions"] = [
        [a["id"], a["label"], a["target"], a["effect"], a["cost"], a["duration"], a["description"]]
        for a in spec["actions"]
    ]
    if keep.get("incidents_extra"):
        keep["extra_incidents"] = keep.pop("incidents_extra")
    else:
        keep.pop("incidents_extra", None)
    return yaml.safe_dump([keep], sort_keys=False, allow_unicode=True, width=100)
