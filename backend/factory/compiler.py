"""Built-in scenario engineer: SOP analysis → first draft → repairs driven by failing checks.

The first draft is intentionally literal (every imperative line becomes an action, loops
become edges), mirroring what a naive generator produces. Tests and red-team checks then find
the problems and ``repair`` fixes them. The same loop runs with Codex when it is available.
"""

import copy
import re

from ..connections import SHARED_KINDS
from ..engine import ROLES
from . import pii

INJECTION = re.compile(
    r"(?i)(ignore (all |any )?(previous|prior|above) instructions|disregard (the )?(rules|instructions)|system prompt|you are now|act as an?|publish (this )?(scenario )?without|bypass (the )?(approval|review|policy)|without (trainer|human) approval)"
)
PROHIBITED = re.compile(
    r"(?i)\b(delete all|drop (the )?table|wipe|purge all|disable (the )?(logging|audit|monitoring|alarms)|transfer funds|wire (money|funds)|exfiltrat|rm -rf|format (the )?disk|share (the )?passwords?)\b"
)
ROLE_WORDS = [
    ("security", ["security", "soc", "cyber", "identity", "access control"]),
    ("legal", ["legal", "compliance", "regulat", "privacy", "counsel"]),
    ("medical", ["clinical", "patient", "nurse", "doctor", "medical", "physician"]),
    ("safety", ["safety", "hazard", "evacuat"]),
    ("emergency", ["emergency", "incident command", "responder", "rescue"]),
    ("executive", ["leadership", "executive", "director", "board"]),
    ("finance", ["finance", "controller", "penalt", "budget", "payment", "invoice", "working capital", "accounts"]),
    ("engineering", ["engineer", "maintenance", "technical", "developer", "administrator"]),
    ("investigator", ["analyst", "monitor", "investigat", "audit"]),
    ("operations", ["planner", "coordinator", "operations", "logistics", "service", "production", "warehouse", "dispatcher"]),
]
MODALITY_WORDS = [
    ("email", ["notif", "email", "communicat", "message", "inform"]),
    ("kpi", ["dashboard", "report", "kpi", "penalt", "working capital", "exposure"]),
    ("image", ["camera", "image", "photo", "visual inspection"]),
    ("sensor", ["sensor", "telemetry", "temperature", "pressure", "vibration"]),
    ("ticket", ["ticket", "case", "queue", "helpdesk"]),
    ("map", ["route", "reroute", "port", "location", "map", "freight"]),
    ("transaction", ["order", "invoice", "payment", "stock", "purchase"]),
    ("document", ["contract", "document", "policy", "procedure"]),
    ("log", ["monitor", "alert", "log", "confirmation", "review"]),
]
VERB_EFFECTS = [
    ("contain", ["suspend", "isolate", "freeze", "block", "hold", "quarantine", "delete", "wipe", "purge", "disable"]),
    ("reroute", ["reroute", "expedite", "redirect", "divert", "resequence", "bridging", "alternate"]),
    ("repair", ["restore", "repair", "replace", "fix", "qualify", "resolve", "reset", "places"]),
    ("boost", ["activate", "escalate", "increase", "overtime", "surge", "deploy", "allocate", "notif", "offer", "publish", "approve"]),
    ("inspect", ["review", "check", "investigate", "verify", "monitor", "assess", "audit", "trace", "confirm", "raise"]),
]
COSTS = dict(repair=(2000, 4), contain=(600, 1), reroute=(1400, 2), boost=(1100, 1), inspect=(200, 0))
SYSTEM = re.compile(r"\b(ERP|MES|TMS|WMS|CRM|SIEM|SOAR|EHR|LIS|SCADA|CMMS|[A-Za-z]+ (?:[Pp]ortal|[Dd]ashboard|[Ss]ystem|[Pp]latform|[Cc]onsole|[Rr]egistry|[Tt]racker))\b")
THRESHOLD = re.compile(r"(?i)\b(more than|less than|over|under|exceeds?|below|above|within|at least)\s+(\d+(?:\.\d+)?)\s*(hours?|days?|minutes?|%|percent)")
LOOP = re.compile(r"(?i)\b(?:return|go back|loop back|repeat)\s+(?:to\s+)?step\s+(\d+)")
STEP = re.compile(r"^\s*(?:#+\s*)?(?:step\s*)?(\d{1,2})[.):]\s*(.+)$", re.I)
ENTITY_WORDS = {
    "Supplier": ["supplier", "vendor"],
    "Order": ["order", "purchase"],
    "Customer": ["customer", "client"],
    "Product": ["product", "component", "part"],
    "Employee": ["employee", "staff", "analyst", "planner"],
    "Machine": ["machine", "equipment", "turbine", "pump"],
    "Vehicle": ["vehicle", "truck", "freight", "drone", "aircraft"],
    "Location": ["port", "site", "warehouse", "location", "plant"],
    "Account": ["account"],
    "Asset": ["server", "asset", "host", "device"],
    "Sensor": ["sensor"],
}


def slug(text, taken=()):
    base = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:24].strip("_") or "step"
    if not base[0].isalpha():
        base = "s_" + base
    key, n = base, 2
    while key in taken:
        key, n = f"{base[:21]}_{n}", n + 1
    return key


def role_for(text, default="operations"):
    low = text.lower()
    for role, words in ROLE_WORDS:
        if any(w in low for w in words):
            return role
    return default


def modality_for(text):
    low = text.lower()
    for modality, words in MODALITY_WORDS:
        if any(w in low for w in words):
            return modality
    return "log"


def effect_for(sentence):
    low = sentence.lower()
    for effect, verbs in VERB_EFFECTS:
        if any(re.search(rf"\b{v}", low) for v in verbs):
            return effect
    return None


def analyze(text):
    lines = [line.rstrip() for line in text.splitlines()]
    title = next((re.sub(r"^#+\s*", "", line).strip() for line in lines if line.strip().startswith("#")), None) or next((line.strip() for line in lines if line.strip()), "SOP")
    sections, current = {}, "preamble"
    for line in lines:
        if re.match(r"^#{2,}\s", line):
            current = re.sub(r"^#+\s*", "", line).strip().lower()
            sections[current] = []
        else:
            sections.setdefault(current, []).append(line)
    purpose = " ".join(" ".join(v) for k, v in sections.items() if "purpose" in k or "scope" in k)
    purpose = " ".join(purpose.split())
    roles = []
    for k, v in sections.items():
        if "role" in k or "responsib" in k:
            for line in v:
                m = re.match(r"^\s*[-*]\s*([^(:\-]+?)\s*(?:\((.*?)\)|:(.*))?$", line)
                if m and m.group(1).strip():
                    name = m.group(1).strip()
                    roles.append(dict(name=name, role=role_for(name + " " + (m.group(2) or m.group(3) or ""))))
    steps = []
    for line in lines:
        m = STEP.match(line)
        if m:
            body = m.group(2).strip()
            head, _, rest = body.partition(":")
            if not rest or len(head) > 60:
                head, rest = " ".join(body.split()[:5]), body
            steps.append(dict(n=int(m.group(1)), title=head.strip(), body=rest.strip()))
    notes = [line.strip() for k, v in sections.items() if k != "preamble" and not any(s in k for s in ("procedure", "role", "purpose", "scope")) for line in v if line.strip() and not STEP.match(line)]
    for step in steps:
        who = next((r for r in roles if r["name"].lower() in step["body"].lower()), None)
        step["performer"] = who["name"] if who else None
        step["role"] = who["role"] if who else role_for(step["title"] + " " + step["body"])
        step["systems"] = sorted(set(SYSTEM.findall(step["body"])))
        step["thresholds"] = [" ".join(t) for t in THRESHOLD.findall(step["body"])]
        step["loop_to"] = [int(x) for x in LOOP.findall(step["body"])]
        sentences = [s.strip() for s in re.split(r"(?<=[.;])\s+", step["body"]) if s.strip()]
        step["actions"] = [dict(text=s.rstrip("."), effect=effect_for(s)) for s in sentences if effect_for(s)]
    text_all = "\n".join(lines)
    return dict(
        title=title,
        purpose=purpose,
        roles=roles,
        steps=steps,
        notes=notes,
        injections=[line for line in lines if INJECTION.search(line)],
        prohibited=[line for line in lines if PROHIBITED.search(line)],
        thresholds=[t for s in steps for t in s["thresholds"]],
        systems=sorted({x for s in steps for x in s["systems"]}),
        entities=[k for k, words in ENTITY_WORDS.items() if any(w in text_all.lower() for w in words)],
    )


def _cause(analysis):
    m = re.search(r"(?i)\bwhen (?:an? |the )?(.+?)(?:\.|,|;)", analysis["purpose"])
    core = m.group(1) if m else f"the triggering condition of '{analysis['title']}' occurs"
    return core[0].upper() + core[1:] + ", without early warning to the teams involved."


def _action(step_node, sentence, effect, taken):
    cost, duration = COSTS[effect]
    clause = sentence
    if re.match(r"(?i)^(if|when|where|once)\s", clause) and "," in clause:
        clause = clause.split(",", 1)[1].strip()  # "If X, do Y" -> "do Y"
    label = clause[0].upper() + clause[1:]
    label = re.sub(r"^(The|A|An) [A-Z][\w ]+? (?=[a-z])", "", label)
    label = label[0].upper() + label[1:] if label else sentence
    if len(label) > 60:
        label = label[:60].rsplit(" ", 1)[0] + "…"
    return dict(id=slug(f"{effect}_{step_node}", taken), label=label, target=step_node, effect=effect, cost=cost, duration=duration, description=sentence[:200])


def draft(analysis, objective=""):
    """Literal first draft. Expect tests and red-team checks to find issues."""
    steps = analysis["steps"][:12] or [dict(n=1, title=analysis["title"], body=analysis["purpose"], role="operations", systems=[], thresholds=[], loop_to=[], actions=[])]
    ids, nodes = {}, []
    for step in steps:
        nid = slug(step["title"], set(ids.values()))
        ids[step["n"]] = nid
        text = step["title"] + " " + step["body"]
        nodes.append([nid, step["title"][:40], step["role"], 3 if "manual" in text.lower() else 5, modality_for(text), (step["systems"] or [step["title"]])[0]])
    order = [s["n"] for s in steps]
    edges = [[ids[a], ids[b]] for a, b in zip(order, order[1:])]
    for step in steps:
        for target in step["loop_to"]:
            if target in ids:
                edges.append([ids[step["n"]], ids[target]])  # rework loop (creates a cycle)
    actions, taken = [], set()
    for step in steps:
        for a in step["actions"]:
            act = _action(ids[step["n"]], a["text"], a["effect"], taken)
            taken.add(act["id"])
            actions.append(act)
    # Literal generators also turn free-text notes into actions.
    for note in analysis["notes"]:
        effect = effect_for(note)
        if effect:
            act = _action(nodes[-1][0], note, effect, taken)
            taken.add(act["id"])
            actions.append(act)
    rules = []
    for i, step in enumerate(steps):
        for j, t in enumerate(step["thresholds"]):
            target = ids[step["n"]] if step["n"] != steps[0]["n"] else nodes[min(1, len(nodes) - 1)][0]
            rules.append(dict(name=f"threshold_{i}_{j}", at=8 + 4 * len(rules), when=[f"{nodes[0][0]}.intrinsic<60"], target=target, health=45, message=f"SOP threshold breached at {step['title']}: {t}."))
    kinds = [k for k in analysis["entities"] if k in SHARED_KINDS][:3]
    entity = {k.lower(): k for k in kinds}
    entity["value"] = [100, 5000]
    agents = {}
    for r in analysis["roles"]:
        agents.setdefault(r["role"], r["name"])
    title = re.sub(r"(?i)\s*\b(sop|standard operating procedure)\b", "", analysis["title"]).strip() or analysis["title"]
    unit = "orders" if "Order" in analysis["entities"] else "cases"
    return dict(
        key=slug("sop_" + title),
        title=f"{title} Simulation",
        category="SOP Simulations",
        summary=(analysis["purpose"] or f"Simulation generated from {analysis['title']}.")[:780],
        objective=objective or "Follow the procedure: detect the disruption early, act within thresholds and protect the business outcome.",
        unit=unit,
        impact="impact units",
        nodes=nodes,
        edges=edges,
        incident=dict(node=nodes[0][0], cause=_cause(analysis), signal=(steps[0]["thresholds"][0] if steps[0]["thresholds"] else "unexpected behaviour reported"), tick=5, severity=0.78),
        secondary=nodes[min(2, len(nodes) - 1)][0] if len(nodes) > 2 else None,
        actions=actions,
        rules=rules,
        decoys=[],
        agents=agents,
        entity=entity,
        emits=[dict(signal="supplier_failure" if "Supplier" in analysis["entities"] else "sop_disruption", node=nodes[-1][0], below=55)],
        building_blocks=["SimForge SOP Factory", "SimPy", "NetworkX"],
        objectives=["Follow the SOP thresholds", "Protect customers", "Control cost"],
        learning=dict(role=(analysis["roles"][0]["name"] if analysis["roles"] else "Incident coordinator"), mission=objective or analysis["purpose"][:300], success="Recover within budget and justify each decision with evidence."),
        environment_style="workflow",
    )


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


def _clean_strings(obj):
    if isinstance(obj, str):
        return pii.sanitize(obj)[0]
    if isinstance(obj, dict):
        return {k: _clean_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_strings(v) for v in obj]
    return obj


def repair(pack, analysis, failures):
    """Deterministic repair engineer. Returns (pack, list of human-readable changes)."""
    pack = copy.deepcopy(pack)
    changes = []
    names = {f["name"] for f in failures}
    node_ids = [n[0] for n in pack["nodes"]]
    position = {nid: i for i, nid in enumerate(node_ids)}
    backward = [e for e in pack["edges"] if position[e[1]] <= position[e[0]]]
    if backward:
        pack["edges"] = [e for e in pack["edges"] if e not in backward]
        for e in backward:
            changes.append(f"Removed rework loop {e[0]} → {e[1]} (cycles are not allowed); modelled as a delay rule instead.")
            pack["rules"].append(dict(name=f"rework_{e[0]}", at=16, when=[f"{e[0]}.intrinsic<60"], target=e[0], health=50, message=f"Rework loop: {e[0]} work returns for re-assessment."))
    quarantined = []
    kept = []
    for a in pack["actions"]:
        text = f"{a['label']} {a['description']}"
        if INJECTION.search(text) or PROHIBITED.search(text):
            quarantined.append(a["description"])
        else:
            kept.append(a)
    if quarantined:
        pack["actions"] = kept
        for q in quarantined:
            changes.append(f"Quarantined untrusted/destructive instruction: '{q[:80]}'")
    loops = [a for a in pack["actions"] if LOOP.search(a["label"])]
    if loops:
        pack["actions"] = [a for a in pack["actions"] if a not in loops]
        changes.append(f"Removed {len(loops)} control-flow instruction(s) exposed as decisions ('{loops[0]['label']}').")
    root = pack["incident"]["node"]
    if not any(a["effect"] == "repair" and a["target"] == root for a in pack["actions"]):
        label = next((n[1] for n in pack["nodes"] if n[0] == root), root)
        pack["actions"].insert(0, dict(id=slug("restore_" + root, {a["id"] for a in pack["actions"]}), label=f"Restore {label.lower()} per SOP recovery step", target=root, effect="repair", cost=2000, duration=4, description="Resolve the triggering condition at its source."))
        changes.append(f"Added root-cause recovery action for '{label}'.")
    if not any(a["effect"] == "inspect" for a in pack["actions"]):
        pack["actions"].append(dict(id=slug("inspect_" + root, {a["id"] for a in pack["actions"]}), label="Investigate the first SOP signal", target=root, effect="inspect", cost=200, duration=0, description="Gather evidence before acting."))
        changes.append("Added an investigation action.")
    if len(pack.get("decoys", [])) < 2 or "Distractor explanations provided" in names:
        pack["decoys"] = [
            "A planned system maintenance window caused the delay",
            "A seasonal demand spike is overloading the team",
            "A reporting error makes the situation look worse than it is",
        ]
        changes.append("Added three plausible distractor explanations for the diagnosis step.")
    phrases = " ".join(r["message"] for r in pack["rules"])
    for t in analysis["thresholds"]:
        if t not in phrases:
            pack["rules"].append(dict(name=slug("threshold_" + t, {r["name"] for r in pack["rules"]}), at=10 + 3 * len(pack["rules"]), when=[f"{root}.intrinsic<60"], target=node_ids[min(1, len(node_ids) - 1)], health=45, message=f"SOP threshold breached: {t}."))
            changes.append(f"Modelled SOP threshold '{t}' as a consequence rule.")
    grounded_text = " ".join(s["title"] + " " + s["body"] for s in analysis["steps"]).lower()
    for n in pack["nodes"]:
        if n[5].lower() not in grounded_text and n[1].lower() not in grounded_text:
            changes.append(f"Grounded system '{n[1]}' to its SOP step (was '{n[5]}').")
            n[5] = n[1]
    residual = [s for s in _strings(pack) if pii.residual(s)]
    if residual:
        pack = _clean_strings(pack)
        changes.append(f"Removed personal data from {len(residual)} generated text fields.")
    if "Correct response reduces impact" in names:
        pack["incident"]["severity"] = 0.85
        changes.append("Raised incident severity so the correct response measurably changes the outcome.")
    return pack, changes


def roles_catalogue():
    return list(ROLES)
