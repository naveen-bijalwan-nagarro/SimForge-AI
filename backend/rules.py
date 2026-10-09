"""A tiny, safe condition language for data-defined consequence rules.

Scenario packs (including ones drafted by Codex) describe consequences as data, never code:

    {"name": "exfiltration", "at": 14, "when": ["cloud.intrinsic<60", "!host.isolated"],
     "target": "data", "health": 35, "message": "..."}

Each atom is ``[!]node.attribute [op number]``; all atoms must hold (logical AND).
"""

import re

ATTRIBUTES = {"health", "intrinsic", "isolated", "bypass", "boosted"}
BOOLEAN = {"isolated", "bypass", "boosted"}
ATOM = re.compile(
    r"^\s*(?P<neg>!)?\s*(?P<node>[a-z][a-z0-9_]*)\.(?P<attr>[a-z_]+)"
    r"\s*(?:(?P<op><=|>=|==|<|>)\s*(?P<value>-?\d+(?:\.\d+)?))?\s*$"
)


def parse_atom(text):
    match = ATOM.match(str(text))
    if not match:
        raise ValueError(f"Invalid rule condition '{text}'. Use node.attribute<number or !node.flag")
    atom = match.groupdict()
    if atom["attr"] not in ATTRIBUTES:
        raise ValueError(f"Unknown attribute '{atom['attr']}' in condition '{text}'")
    if atom["attr"] in BOOLEAN and atom["op"]:
        raise ValueError(f"Flag '{atom['attr']}' takes no comparison in '{text}'")
    if atom["attr"] not in BOOLEAN and not atom["op"]:
        raise ValueError(f"Numeric attribute '{atom['attr']}' needs a comparison in '{text}'")
    if atom["neg"] and atom["op"]:
        raise ValueError(f"Negate flags only, not comparisons, in '{text}'")
    return atom


def validate(rules, node_ids):
    """Return human-readable problems; an empty list means the rules are usable."""
    problems = []
    names = set()
    for i, rule in enumerate(rules or []):
        label = rule.get("name") or f"rule {i + 1}"
        if label in names:
            problems.append(f"Duplicate rule name '{label}'")
        names.add(label)
        if rule.get("target") not in node_ids:
            problems.append(f"Rule '{label}' targets unknown node '{rule.get('target')}'")
        if not isinstance(rule.get("at"), (int, float)) or rule["at"] < 0:
            problems.append(f"Rule '{label}' needs a non-negative 'at' minute")
        if not 0 <= float(rule.get("health", -1)) <= 100:
            problems.append(f"Rule '{label}' needs health between 0 and 100")
        if not str(rule.get("message", "")).strip():
            problems.append(f"Rule '{label}' needs a message")
        for condition in rule.get("when", []):
            try:
                atom = parse_atom(condition)
            except ValueError as e:
                problems.append(str(e))
                continue
            if atom["node"] not in node_ids:
                problems.append(f"Rule '{label}' references unknown node '{atom['node']}'")
    return problems


def holds(atom, nodes, tick):
    node = nodes[atom["node"]]
    attr = atom["attr"]
    if attr in BOOLEAN:
        value = node["boost_until"] >= tick if attr == "boosted" else bool(node[attr])
        return not value if atom["neg"] else value
    left, right = float(node[attr]), float(atom["value"])
    return {
        "<": left < right,
        "<=": left <= right,
        ">": left > right,
        ">=": left >= right,
        "==": left == right,
    }[atom["op"]]


def apply(rules, tick, nodes, emit, fired):
    """Evaluate each rule once at its minute; effects depend on earlier decisions."""
    for rule in rules or []:
        name = "rule:" + rule["name"]
        if tick < rule["at"] or name in fired:
            continue
        fired.add(name)
        if all(holds(parse_atom(c), nodes, tick) for c in rule.get("when", [])):
            target = nodes[rule["target"]]
            target["intrinsic"] = min(target["intrinsic"], float(rule["health"]))
            emit("domain_event", rule["target"], rule["message"], target["role"], "warning")
