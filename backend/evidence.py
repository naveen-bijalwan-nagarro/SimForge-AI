"""Multimodal evidence derived deterministically from a simulation run.

Each observable event becomes evidence in the modality of the system that produced it:
logs, emails, sensor series, images, short video clips, maps, tickets, documents,
transactions, relationship graphs, chat or KPIs. Participants see only their role's evidence
(executives see KPIs only) and benign decoys are mixed in. The hidden cause never appears.
"""

import hashlib
import random
from datetime import datetime, timedelta

from . import vision

START = datetime(2026, 9, 28, 9, 0, 0)
SENSOR_PROFILES = [
    (("vibration", "bearing", "spindle", "gearbox", "rotor", "cms"), "vibration", "mm/s", 2.2, 0.09),
    (("thermal", "temperature", "heat", "hvac", "icu", "cooling"), "temperature", "°C", 61.0, 0.34),
    (("pressure", "pump", "water", "flow"), "pressure", "bar", 5.4, -0.035),
    (("latency", "api", "database", "server", "cache", "pods", "backend"), "p95 latency", "ms", 48.0, 14.0),
    (("queue", "backlog", "dlq"), "queue depth", "items", 20.0, 7.0),
    (("power", "bus", "battery", "charging", "voltage"), "voltage", "V", 28.0, -0.09),
    (("frequency", "generation", "grid", "substation", "feeder"), "frequency", "Hz", 50.0, -0.012),
    (("infection", "positivity", "testing", "surveillance"), "test positivity", "%", 4.0, 0.22),
    (("link", "comms", "network", "mesh", "packet", "backhaul"), "packet loss", "%", 0.2, 0.09),
    (("gnss", "position", "localization", "navigation"), "position error", "m", 1.5, 0.35),
    (("crash", "error"), "crash rate", "%", 0.4, 0.2),
]
DEFAULT_SENSOR = ("anomaly score", "score", 0.08, 0.009)
BENIGN = [
    "Planned maintenance window acknowledged; no customer impact expected.",
    "Load spike matches the weekly seasonal pattern.",
    "Monitoring agent restarted after a routine upgrade.",
    "Certificate renewal completed; brief reconnects observed.",
    "Training exercise traffic tagged by the red team.",
]


def _rng(*parts):
    digest = hashlib.sha256(":".join(map(str, parts)).encode()).hexdigest()
    return random.Random(int(digest[:12], 16))


def _stamp(tick, jitter=0.0):
    return (START + timedelta(minutes=tick + jitter)).strftime("%Y-%m-%dT%H:%M:%SZ")


def sensor_profile(node):
    text = f"{node.get('label', '')} {node.get('source', '')} {node['id']}".lower()
    for words, name, unit, base, slope in SENSOR_PROFILES:
        if any(w in text for w in words):
            return name, unit, base, slope
    return DEFAULT_SENSOR


def position(node_id, key):
    r = _rng("pos", key, node_id)
    return dict(x=round(r.uniform(8, 92), 1), y=round(r.uniform(10, 90), 1))


def visual_kind(spec, node):
    return (spec.get("visuals") or {}).get(node["id"]) or spec.get("visual") or "aerial"


def _history_until(result, tick):
    return [h for h in result["history"] if h["tick"] <= tick]


def _health_at(result, node_id, tick):
    rows = _history_until(result, tick)
    return rows[-1]["health"].get(node_id, 100.0) if rows else 100.0


def _series(spec, node, result, until, seed):
    name, unit, base, slope = sensor_profile(node)
    r = _rng("series", spec["key"], node["id"], seed)
    points = []
    for h in _history_until(result, until):
        noise = r.gauss(0, abs(slope) * 2.5 + abs(base) * 0.01)
        value = base + slope * (100 - h["health"].get(node["id"], 100.0)) + noise
        points.append(dict(t=h["tick"], v=round(value, 3)))
    threshold = base + slope * 30
    return dict(metric=name, unit=unit, baseline=base, threshold=round(threshold, 3), points=points)


def _content(spec, node, event, result, seed, labels, entities, complete, run_id, eid):
    modality = node.get("modality", "log")
    r = _rng("content", spec["key"], eid, seed)
    tick = event["tick"]
    health = _health_at(result, node["id"], tick)
    source = node.get("source") or node["label"]
    message = event["message"]
    if modality == "log":
        level = "ERROR" if event["severity"] == "critical" else "WARN"
        lines = []
        for k in range(4):
            lines.append(
                f"{_stamp(tick, k * 0.3 - 0.9)} {source} {level if k else 'INFO'} system={node['id']} "
                f"health={max(0, health + r.uniform(-4, 4)):.0f}% errors={int((100 - health) * r.uniform(0.3, 1.2))} "
                f"latency_ms={int(40 + (100 - health) * r.uniform(5, 14))}"
            )
        lines.append(f'{_stamp(tick)} {source} {level} system={node["id"]} msg="{message}"')
        return dict(lines=lines)
    if modality == "email":
        return dict(
            sender=f"{node['role']}-desk@simforge.example",
            to="incident-bridge@simforge.example",
            subject=f"{'URGENT: ' if event['severity'] == 'critical' else ''}{node['label']} - {event['kind'].replace('_', ' ')}",
            body=(
                f"Team,\n\n{message}\nCurrent health estimate for {node['label']} is {health:.0f}%. "
                f"Upstream dependencies: {', '.join(labels[p] for p in node.get('_parents', [])) or 'none'}.\n\n"
                "Please advise on next steps.\n"
            ),
        )
    if modality == "sensor":
        return _series(spec, node, result, tick + 3, seed)
    if modality in {"image", "video"}:
        defect = event["kind"] in {"incident", "cascade", "domain_event", "degradation"} and health < 80
        lighting = 1.0
        for target, factor in (spec.get("visual_lighting") or {}).items():
            onset = [e["tick"] for e in result["events"] if e["node"] == target and e["kind"] in {"incident", "degradation"}]
            if onset and tick >= onset[0]:
                lighting = factor
        media = dict(
            kind=visual_kind(spec, node),
            seed=int(_rng("img", spec["key"], eid, seed).random() * 1e6),
            defect=defect,
            severity=round(min(1.0, max(0.3, (100 - health) / 80)), 2),
            lighting=lighting,
        )
        item = dict(
            url=f"/api/runs/{run_id}/evidence/{eid}/{'clip.gif' if modality == 'video' else 'image.png'}",
            kind=media["kind"],
            caption=f"{source} capture at minute {tick:.0f}",
            lighting=lighting,
            _media=media,
        )
        if modality == "image":
            img, truth = vision.render(media["kind"], media["seed"], defect, media["severity"], lighting)
            item["detections"] = vision.detect(img, media["kind"])
            item["_truth"] = truth
        return item
    if modality == "map":
        center = position(node["id"], spec["key"])
        here = [e for e in entities if e.get("current_node") == node["id"]][:30]
        points = [
            dict(
                id=e["id"],
                x=round(min(99, max(1, center["x"] + r.gauss(0, 6))), 1),
                y=round(min(99, max(1, center["y"] + r.gauss(0, 6))), 1),
                status=e["state"],
            )
            for e in here
        ]
        return dict(center=center, radius=round(4 + (100 - health) / 6, 1), points=points, label=node["label"])
    if modality == "ticket":
        return dict(
            ticket=f"INC-{r.randint(10000, 99999)}",
            priority="P1" if event["severity"] == "critical" else "P2",
            status="Open",
            queue=source,
            text=f"{message} Reported by {source}. Affected items: {int((100 - health) * r.uniform(1, 4))}.",
        )
    if modality == "document":
        return dict(
            title=f"{source} - situation extract",
            paragraphs=[
                f"Observation at minute {tick:.0f}: {message}",
                f"{node['label']} is operating at an estimated {health:.0f}% of normal capacity.",
                "This extract is a synthetic training document; no real records are included.",
            ],
        )
    if modality == "transaction":
        rows = []
        numeric = [k for k, v in (entities[0] if entities else {}).items() if isinstance(v, (int, float)) and k not in {"arrival", "finished"}]
        for e in r.sample(entities, min(10, len(entities))):
            flagged = health < 70 and r.random() < 0.45
            row = dict(id=e["id"], region=e.get("region"), state=e.get("state"))
            if numeric:
                value = e[numeric[0]]
                row[numeric[0]] = round(value * (r.uniform(2.5, 6) if flagged else 1), 2)
            row["flag"] = "review" if flagged else ""
            rows.append(row)
        return dict(rows=rows)
    if modality == "graph":
        ids = [e["id"] for e in entities[:24]]
        hubs = [f"HUB-{k}" for k in range(1, 4)]
        edges, nodes = [], [dict(id=i, type="entity") for i in ids] + [dict(id=h, type="hub") for h in hubs]
        for i in ids:
            edges.append(dict(source=i, target=r.choice(hubs), type="shares"))
        if health < 70:
            ring = r.sample(ids, min(6, len(ids)))
            for a, b in zip(ring, ring[1:] + ring[:1]):
                edges.append(dict(source=a, target=b, type="transfer"))
        return dict(nodes=nodes, edges=edges)
    if modality == "chat":
        people = list((spec.get("agents") or {}).values()) or ["Operator", "Analyst"]
        return dict(
            messages=[
                dict(sender=people[0], text=message, tick=tick),
                dict(sender=people[min(1, len(people) - 1)], text=f"Seeing {node['label']} at ~{health:.0f}%. Anyone else?", tick=tick + 0.4),
            ]
        )
    rows = _history_until(result, tick)
    last = rows[-1] if rows else dict(service=100, completed=0, queued=0)
    return dict(
        metrics=[
            dict(name="Service health", value=last["service"], target=90, unit="%"),
            dict(name=f"{node['label']} health", value=health, target=85, unit="%"),
            dict(name="Completed work", value=last["completed"], target=None, unit=spec["unit"]),
            dict(name="Queued work", value=last["queued"], target=None, unit=spec["unit"]),
        ]
    )


def build(spec, result, seed, run_id, complete=False):
    """All evidence for a run up to its current minute (private fields included)."""
    labels = {n["id"]: n["label"] for n in spec["nodes"]}
    parents = {n["id"]: [] for n in spec["nodes"]}
    for e in spec["edges"]:
        parents[e["target"]].append(e["source"])
    nodes = {n["id"]: dict(n, _parents=parents[n["id"]]) for n in spec["nodes"]}
    items = []
    observable = [
        e for e in result["events"] if e["kind"] in {"incident", "cascade", "degradation", "domain_event", "evidence"}
    ]
    images = 0
    for event in observable:
        node = nodes[event["node"]]
        if node.get("modality", "log") in {"image", "video"}:
            images += 1
            if images > 10:
                continue
        eid = f"ev-{event['id'][4:]}"
        items.append(
            dict(
                id=eid,
                tick=event["tick"],
                node=node["id"],
                node_label=node["label"],
                source=node.get("source") or node["label"],
                modality=node.get("modality", "log"),
                role=node["role"],
                severity=event["severity"],
                title=event["message"],
                event_id=event["id"],
                decoy=False,
                content=_content(spec, node, event, result, seed, labels, result["entities"], complete, run_id, eid),
            )
        )
    # Routine baselines so anomalies can be compared with normal behaviour.
    for node in nodes.values():
        if node.get("modality") == "sensor":
            items.append(
                dict(
                    id=f"ev-base-{node['id']}",
                    tick=float(result["tick"]),
                    node=node["id"],
                    node_label=node["label"],
                    source=node.get("source") or node["label"],
                    modality="sensor",
                    role=node["role"],
                    severity="info",
                    title=f"{node['label']} telemetry",
                    event_id=None,
                    decoy=False,
                    content=_series(spec, node, result, result["tick"], seed),
                )
            )
    # Benign decoys on healthy systems: plausible, but unrelated to the hidden cause.
    r = _rng("decoy", spec["key"], seed)
    healthy = [n for n in nodes.values() if min((h["health"].get(n["id"], 100) for h in result["history"]), default=100) >= 80]
    for k, node in enumerate(r.sample(healthy, min(2, len(healthy)))):
        tick = round(r.uniform(1, max(2, result["tick"])), 1)
        if tick > result["tick"]:
            continue
        items.append(
            dict(
                id=f"ev-decoy-{k}",
                tick=tick,
                node=node["id"],
                node_label=node["label"],
                source=node.get("source") or node["label"],
                modality="ticket",
                role=node["role"],
                severity="info",
                title=r.choice(BENIGN),
                event_id=None,
                decoy=True,
                content=dict(ticket=f"CHG-{r.randint(1000, 9999)}", priority="P4", status="Closed", queue=node.get("source", ""), text="Routine change record."),
            )
        )
    kpi_rows = result["history"]
    items.append(
        dict(
            id="ev-kpi",
            tick=float(result["tick"]),
            node=None,
            node_label="Executive dashboard",
            source="KPI dashboard",
            modality="kpi",
            role="all",
            severity="info",
            title="Service health, backlog and impact",
            event_id=None,
            decoy=False,
            content=dict(
                series=[dict(t=h["tick"], service=h["service"], queued=h["queued"], loss=h["loss"]) for h in kpi_rows],
                impact_label=spec.get("impact", "impact units"),
            ),
        )
    )
    return sorted(items, key=lambda i: (i["tick"], i["id"]))


def public(items, role, complete):
    """Role-scoped view; private media parameters and ground truth stay server-side."""
    out = []
    for item in items:
        if not complete:
            if role == "executive" and item["modality"] != "kpi":
                continue
            if item["role"] not in {role, "all"} and role != "executive":
                continue
        clean = dict(item)
        content = {k: v for k, v in item["content"].items() if not k.startswith("_")}
        if complete and "_truth" in item["content"]:
            content["ground_truth_boxes"] = item["content"]["_truth"]
        clean["content"] = content
        if not complete:
            clean.pop("decoy", None)
        out.append(clean)
    return out


def media(items, eid):
    """Render the image or GIF clip for one evidence item."""
    item = next((i for i in items if i["id"] == eid), None)
    if not item or "_media" not in item["content"]:
        return None
    m = item["content"]["_media"]
    if item["modality"] == "video":
        data, _ = vision.clip(m["kind"], m["seed"], m["defect"], m["severity"])
        return data, "image/gif"
    img, _ = vision.render(m["kind"], m["seed"], m["defect"], m["severity"], m["lighting"])
    return vision.png(img), "image/png"
