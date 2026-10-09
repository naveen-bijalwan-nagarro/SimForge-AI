"""Optional links between otherwise independent scenarios.

Scenarios stay self-contained. A world may *emit* a named signal when one of its systems
falls below a threshold (``Scenario A -> event/output``); any scenario that *consumes* that
signal can be launched from the run (``-> Scenario B trigger``). Shared master data lets
different scenarios reference the same synthetic Supplier, Machine or Customer without
merging their workflows.
"""

import copy
import random
from functools import lru_cache

# Synthetic master-data universe shared by every scenario. IDs are stable across scenarios.
SHARED_KINDS = {
    "Customer": ("CUS", 40, ["Retail", "SMB", "Enterprise", "Public sector"]),
    "Account": ("ACC", 40, ["Checking", "Savings", "Merchant", "Wallet"]),
    "Product": ("PRD", 30, ["Component", "Finished good", "Spare part", "Service plan"]),
    "Supplier": ("SUP", 12, ["Tier 1", "Tier 2", "Logistics", "Contract manufacturer"]),
    "Machine": ("MCH", 24, ["Turbine", "Press", "Pump", "Conveyor", "Compressor"]),
    "Employee": ("EMP", 60, ["Operator", "Engineer", "Analyst", "Manager", "Responder"]),
    "Vehicle": ("VEH", 30, ["Truck", "Drone", "Ambulance", "Service van", "Aircraft"]),
    "Location": ("LOC", 16, ["Plant", "Warehouse", "Substation", "Hospital", "Port", "District"]),
    "Order": ("ORD", 80, ["Standard", "Priority", "Contract"]),
    "Sensor": ("SEN", 48, ["Vibration", "Temperature", "Pressure", "Current", "Flow"]),
    "Asset": ("AST", 36, ["Server", "Tower", "Line segment", "Pipe", "Camera", "Gateway"]),
}
PLACES = ["North", "South", "East", "West", "Central", "Harbour", "Ridge", "Valley"]
SURNAMES = ["Rao", "Chen", "Okafor", "Silva", "Novak", "Haddad", "Kim", "Moreau", "Singh", "Diaz"]


@lru_cache
def registry():
    """Deterministic shared entities. Fixed seed so every scenario sees the same universe."""
    rng = random.Random(7)
    universe = {}
    for kind, (prefix, size, types) in SHARED_KINDS.items():
        rows = []
        for i in range(size):
            place = PLACES[i % len(PLACES)]
            name = (
                f"{rng.choice(['A.', 'J.', 'M.', 'R.', 'S.'])} {rng.choice(SURNAMES)}"
                if kind == "Employee"
                else f"{place} {types[i % len(types)]} {i + 1}"
            )
            rows.append(
                dict(
                    id=f"{prefix}-{i + 1:03d}",
                    kind=kind,
                    name=name,
                    type=types[i % len(types)],
                    location=f"LOC-{(i % SHARED_KINDS['Location'][1]) + 1:03d}",
                    risk=rng.choice(["low", "low", "medium", "high"]),
                )
            )
        universe[kind] = rows
    return universe


def shared_id(kind, rng):
    prefix, size, _ = SHARED_KINDS[kind]
    return f"{prefix}-{rng.randrange(size) + 1:03d}"


def is_range(spec):
    return (
        isinstance(spec, list)
        and len(spec) == 2
        and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in spec)
    )


def template_fields(template, index, rng):
    """Entity columns from a pack template: shared kind, numeric range, choices or sequence."""
    fields = {}
    for name, spec in template.items():
        if isinstance(spec, str) and spec in SHARED_KINDS:
            fields[name] = shared_id(spec, rng)
        elif isinstance(spec, str) and spec.startswith("seq:"):
            fields[name] = f"{spec[4:]}-{index + 1:05d}"
        elif is_range(spec):
            low, high = spec
            if isinstance(low, int) and isinstance(high, int):
                fields[name] = rng.randint(low, high)
            else:
                fields[name] = round(rng.uniform(low, high), 2)
        elif isinstance(spec, list) and spec:
            fields[name] = rng.choice(spec)
        else:
            fields[name] = spec
    return fields


def validate_template(template):
    problems = []
    if template is not None and not isinstance(template, dict):
        return ["'entity' must map field names to generators"]
    for name, spec in (template or {}).items():
        ok = (
            (isinstance(spec, str) and (spec in SHARED_KINDS or spec.startswith("seq:")))
            or (isinstance(spec, list) and spec)
            or (isinstance(spec, (int, float)) and not isinstance(spec, bool))
        )
        if not ok:
            problems.append(
                f"Entity field '{name}' must be a shared kind "
                f"({', '.join(SHARED_KINDS)}), 'seq:PREFIX', [min, max] or a list of choices"
            )
    return problems


def references(scenarios):
    """Which scenarios reference each shared entity kind."""
    used = {kind: [] for kind in SHARED_KINDS}
    for s in scenarios:
        for spec in (s.get("entity") or {}).values():
            if isinstance(spec, str) and spec in used and s["key"] not in used[spec]:
                used[spec].append(s["key"])
    return used


def scenario_graph(scenarios):
    """Lightweight scenario dependency graph: A emits a signal that B consumes."""
    nodes = [
        dict(
            id=s["key"],
            label=s["title"],
            kind=s["kind"],
            category=s.get("category", ""),
            emits=[e["signal"] for e in s.get("emits", [])],
            consumes=list(s.get("consumes", [])),
        )
        for s in scenarios
        if s.get("emits") or s.get("consumes")
    ]
    edges = []
    for a in nodes:
        for signal in a["emits"]:
            for b in nodes:
                if b["id"] != a["id"] and signal in b["consumes"]:
                    edges.append(dict(source=a["id"], target=b["id"], signal=signal))
    signals = sorted({e["signal"] for e in edges})
    return dict(nodes=nodes, edges=edges, signals=signals)


def active_signals(spec, result):
    """Signals emitted by a run: a watched system fell below its threshold at any minute."""
    active = []
    for emit in spec.get("emits", []):
        lowest = min(
            (h["health"].get(emit["node"], 100.0) for h in result["history"]), default=100.0
        )
        if lowest < emit.get("below", 60):
            active.append(
                dict(
                    signal=emit["signal"],
                    node=emit["node"],
                    lowest_health=round(lowest, 1),
                    intensity=round(min(1.0, (100 - lowest) / 100), 2),
                )
            )
    return active


def handoff_spec(target, signal):
    """Launch a consuming world with an incident scaled by the upstream outcome."""
    spec = copy.deepcopy(target)
    severity = round(min(0.92, 0.45 + 0.5 * signal["intensity"]), 2)
    spec["incident"]["severity"] = severity
    spec["incident"]["cause"] = (
        f"{spec['incident']['cause']} Triggered upstream by '{signal['signal']}' "
        f"(lowest upstream health {signal['lowest_health']}%)."
    )
    spec["handoff"] = dict(signal=signal["signal"], intensity=signal["intensity"])
    return spec
