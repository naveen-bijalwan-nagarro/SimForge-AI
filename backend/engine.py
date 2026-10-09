"""Bounded, deterministic SimPy worlds. Replayed from seed and decision log on resume."""

import random
from collections import deque
import networkx as nx
import simpy
from . import rules as rulebook
from .connections import template_fields
from .domains import consequence, entity_fields

# Specialist perspectives. Worlds use any subset; the council convenes only roles present.
ROLES = {
    "investigator": "Investigator",
    "operations": "Operations lead",
    "finance": "Business analyst",
    "security": "Security lead",
    "safety": "Safety officer",
    "engineering": "Engineering lead",
    "medical": "Medical lead",
    "legal": "Legal & compliance",
    "emergency": "Emergency response",
    "executive": "Executive",
}


def graph_for(spec):
    graph = nx.DiGraph()
    graph.add_nodes_from(n["id"] for n in spec["nodes"])
    graph.add_edges_from((e["source"], e["target"]) for e in spec["edges"])
    if not nx.is_directed_acyclic_graph(graph):
        raise ValueError("Workflow dependencies must be an acyclic graph")
    return graph


def roles_in(spec):
    present = {n["role"] for n in spec["nodes"]}
    return [r for r in ROLES if r in present]


def agent_name(spec, role):
    return (spec.get("agents") or {}).get(role) or ROLES.get(role, role.title())


def simulate(spec, seed, population, until, decisions=(), work_items=None):
    graph = graph_for(spec)
    order = list(nx.topological_sort(graph))
    rng = random.Random(seed)
    env = simpy.Environment()
    nodes = {
        n["id"]: dict(
            n, health=100.0, intrinsic=100.0, isolated=False, bypass=False, boost_until=-1
        )
        for n in spec["nodes"]
    }
    resources = {key: simpy.Resource(env, capacity=nodes[key]["capacity"]) for key in order}
    actions = {a["id"]: a for a in spec["actions"]}
    events, history, entities = [], [], []
    activity = deque(maxlen=4000)
    activity_count = 0
    domain_flags = set()
    ledger = {"spent": 0, "loss": 0.0, "completed": 0, "late": 0, "detected_at": None}
    incident = spec["incident"]

    def emit(kind, node, message, role="all", severity="info", cause_id=None):
        item = dict(
            id=f"evt-{len(events) + 1:05d}",
            tick=round(float(env.now), 2),
            kind=kind,
            node=node,
            message=message,
            role=role,
            severity=severity,
            cause_id=cause_id,
        )
        events.append(item)
        return item["id"]

    def extra_disruption(item):
        # Compound crises: independent hidden causes that start later in the run.
        yield env.timeout(item["tick"])
        target = item["node"]
        nodes[target]["intrinsic"] = min(
            nodes[target]["intrinsic"], 100 * (1 - item.get("severity", 0.6))
        )
        emit(
            "incident",
            target,
            f"{nodes[target]['label']}: {item.get('signal', 'anomalous behaviour detected')}.",
            nodes[target]["role"],
            "critical",
        )

    def disruption():
        yield env.timeout(incident["tick"])
        target = incident["node"]
        nodes[target]["intrinsic"] = 100 * (1 - incident["severity"])
        primary = emit(
            "incident",
            target,
            f"{nodes[target]['label']}: {incident.get('signal', 'abnormal processing failures observed')}.",
            nodes[target]["role"],
            "critical",
        )
        yield env.timeout(13)
        secondary = spec.get("secondary")
        if secondary and nodes[target]["intrinsic"] < 65 and not nodes[secondary]["bypass"]:
            nodes[secondary]["intrinsic"] = min(nodes[secondary]["intrinsic"], 55)
            emit(
                "cascade",
                secondary,
                "Unresolved upstream disruption creates a secondary backlog.",
                nodes[secondary]["role"],
                "warning",
                primary,
            )

    def intervention(item):
        yield env.timeout(item["tick"])
        a = actions[item["action_id"]]
        node = nodes[a["target"]]
        ledger["spent"] += a["cost"]
        eid = emit("decision", a["target"], a["label"], "all")
        if a["effect"] == "inspect":
            if env.now >= incident["tick"]:
                ledger["detected_at"] = (
                    ledger["detected_at"] if ledger["detected_at"] is not None else env.now
                )
                emit(
                    "evidence",
                    a["target"],
                    f"Observed predecessor set: {', '.join(sorted(nx.ancestors(graph, a['target']))) or 'upstream origin'}. Local failure indicator: {100 - node['intrinsic']:.0f}%.",
                    "investigator" if "investigator" in roles_in(spec) else node["role"],
                    "info",
                    eid,
                )
            return
        yield env.timeout(a["duration"])
        if a["effect"] == "repair":
            node["intrinsic"] = 100.0
            node["isolated"] = False
        elif a["effect"] == "contain":
            node["isolated"] = True
        elif a["effect"] == "reroute":
            node["bypass"] = True
            node["intrinsic"] = max(node["intrinsic"], 85.0)
            node["isolated"] = False
        elif a["effect"] == "boost":
            node["boost_until"] = env.now + 6
            node["intrinsic"] = max(node["intrinsic"], 85.0)
        emit("effect", a["target"], f"Completed: {a['label']}", "all", "info", eid)

    def monitor():
        while True:
            consequence(spec["key"], env.now, nodes, emit, domain_flags)
            rulebook.apply(spec.get("rules"), env.now, nodes, emit, domain_flags)
            old = {k: n["health"] for k, n in nodes.items()}
            for key in order:
                n = nodes[key]
                parents = list(graph.predecessors(key))
                factor = (
                    1.0
                    if n["bypass"] or not parents
                    else min(old[p] / 100 if not nodes[p]["isolated"] else 0.65 for p in parents)
                )
                health = n["intrinsic"] * (0.35 + 0.65 * factor)
                if n["boost_until"] > env.now:
                    health = min(100.0, health + 22)
                n["health"] = 0.0 if n["isolated"] else round(health, 2)
                if old[key] >= 70 > n["health"]:
                    emit(
                        "degradation",
                        key,
                        f"{n['label']} degraded; inspect its upstream dependencies.",
                        n["role"],
                        "warning",
                    )
            service = sum(n["health"] for n in nodes.values()) / len(nodes)
            if env.now > 0:
                ledger["loss"] += (100 - service) * population * 0.008
            history.append(
                dict(
                    tick=int(env.now),
                    service=round(service, 1),
                    completed=ledger["completed"],
                    queued=sum(len(r.queue) for r in resources.values()),
                    loss=round(ledger["loss"], 2),
                    spent=ledger["spent"],
                    health={k: n["health"] for k, n in nodes.items()},
                    queues={k: len(r.queue) for k, r in resources.items()},
                    processing={k: len(r.users) for k, r in resources.items()},
                )
            )
            yield env.timeout(1)

    # Synthetic populations have separate arrival times, priorities and resource queues.
    terminal_paths = []
    for source in (k for k in order if graph.in_degree(k) == 0):
        for target in (k for k in order if graph.out_degree(k) == 0):
            terminal_paths.extend(list(nx.all_simple_paths(graph, source, target))[:16])
    if not terminal_paths:
        terminal_paths = [order]
    jobs = [
        (
            i,
            rng.uniform(0, 25),
            rng.choice(terminal_paths),
            rng.uniform(0.2, 0.65),
            rng.choice(["North", "South", "East", "West"]),
        )
        for i in range(population)
    ]
    if work_items is not None:
        jobs = [
            (i, row["arrival"], row["planned_path"], row["service_minutes"], row["region"])
            for i, row in enumerate(work_items)
        ]

    def transition(entity, state, key=None):
        nonlocal activity_count
        entity.update(state=state, current_node=key)
        activity_count += 1
        activity.append(
            dict(
                id=f"activity-{activity_count}",
                tick=round(float(env.now), 2),
                work_id=entity["id"],
                system_id=key,
                state=state,
                message=f"{entity['id']} {state}" + (f" at {nodes[key]['label']}" if key else ""),
            )
        )

    def job(i, arrival, path, duration, region):
        entity = dict(
            id=f"{spec['unit'][:3].upper()}-{i + 1:05d}",
            region=region,
            arrival=round(arrival, 2),
            state="scheduled",
            current_node=None,
            finished=None,
            planned_path=path,
            service_minutes=duration,
        )
        entity_rng = random.Random(seed * 100003 + i)
        if spec.get("entity"):
            entity.update(template_fields(spec["entity"], i, entity_rng))
        else:
            entity.update(entity_fields(spec["key"], i, entity_rng))
        if work_items is not None:
            entity.update(
                {
                    k: v
                    for k, v in work_items[i].items()
                    if k not in {"state", "current_node", "finished"}
                }
            )
        entities.append(entity)
        yield env.timeout(arrival)
        for key in path:
            transition(entity, "queued", key)
            with resources[key].request() as req:
                yield req
                transition(entity, "processing", key)
                remaining = duration
                while remaining > 0:
                    health = nodes[key]["health"] / 100
                    yield env.timeout(0.5)
                    remaining -= 0.5 * max(0.025, health)
        transition(entity, "completed")
        entity.update(finished=round(float(env.now), 2))
        ledger["completed"] += 1
        if env.now - arrival > 12:
            ledger["late"] += 1

    env.process(disruption())
    for item in spec.get("incidents_extra", []):
        env.process(extra_disruption(item))
    for d in decisions:
        env.process(intervention(d))
    env.process(monitor())
    for job_args in jobs:
        env.process(job(*job_args))
    env.run(until=until + 0.00001)
    service = history[-1]["service"]
    loss = round(ledger["loss"], 2)
    budget = spec.get("budget", 10000)
    score = round(
        max(
            0,
            min(
                100,
                0.6 * service
                + 30 * ledger["completed"] / max(1, population)
                + 10 * (1 - ledger["spent"] / budget),
            ),
        ),
        1,
    )
    return dict(
        tick=until,
        nodes=[
            {k: v for k, v in n.items() if k not in {"intrinsic", "boost_until"}}
            for n in nodes.values()
        ],
        edges=spec["edges"],
        events=events,
        history=history,
        entities=entities,
        activity=list(activity),
        activity_total=activity_count,
        metrics=dict(
            service=service,
            completed=ledger["completed"],
            population=population,
            late=ledger["late"],
            loss=loss,
            spent=ledger["spent"],
            budget=budget,
            score=score,
            detected_at=ledger["detected_at"],
        ),
        scorecard=scorecard(history, ledger, incident["tick"], nodes),
        ground_truth=dict(
            root=incident["node"],
            cause=incident["cause"],
            onset=incident["tick"],
            contributing=[
                dict(node=i["node"], cause=i["cause"], onset=i["tick"])
                for i in spec.get("incidents_extra", [])
            ],
        ),
    )


def scorecard(history, ledger, onset, nodes):
    """Operational outcome measures shown alongside the headline score."""
    after = [h for h in history if h["tick"] >= onset]
    low = min(after, key=lambda h: h["service"]) if after else None
    recovered = None
    if low and low["service"] < 85:
        recovered = next(
            (h["tick"] for h in after if h["tick"] > low["tick"] and h["service"] >= 85), None
        )
    detected = ledger["detected_at"]
    return dict(
        downtime=sum(sum(v < 40 for v in h["health"].values()) for h in history),
        min_service=low["service"] if low else 100.0,
        recovered_at=recovered,
        detection_delay=None if detected is None else round(detected - onset, 1),
        sla_breaches=ledger["late"],
        peak_queue=max((h["queued"] for h in history), default=0),
        critical_systems=sum(n["health"] < 40 for n in nodes.values()),
    )


def unnecessary_actions(spec, decisions, baseline):
    """Interventions on systems that never degraded, even without any response."""
    lowest = {
        n["id"]: min(h["health"][n["id"]] for h in baseline["history"]) for n in spec["nodes"]
    }
    actions = {a["id"]: a for a in spec["actions"]}
    return [
        d["action_id"]
        for d in decisions
        if actions[d["action_id"]]["effect"] != "inspect"
        and lowest[actions[d["action_id"]]["target"]] >= 75
    ]


def agent_workflow(spec, result, role):
    """A transparent observe → analyze → propose → review DAG; no LLM or auto-execution."""
    graph = graph_for(spec)
    visible = [e for e in result["events"] if e["role"] in {role, "all"}]
    owned = {n["id"] for n in spec["nodes"] if n["role"] == role}
    impacted = [n for n in result["nodes"] if n["id"] in owned and n["health"] < 75]
    candidates = []
    for n in sorted(impacted, key=lambda n: n["health"]):
        options = [a for a in spec["actions"] if a["target"] == n["id"]]
        options.sort(key=lambda a: a["effect"] != "repair")
        candidates.extend(options[:1])
    if not candidates:
        candidates = [a for a in spec["actions"] if a["effect"] == "inspect"][:1]
    proposals = []
    for a in candidates[:2]:
        affordable = result["metrics"]["spent"] + a["cost"] <= result["metrics"]["budget"]
        proposals.append(
            dict(
                action_id=a["id"],
                label=a["label"],
                cost=a["cost"],
                target=a["target"],
                approved_by_policy=affordable,
                reason=f"{agent_name(spec, role)} observed {len(visible)} role-visible events. Affected downstream systems: {len(nx.descendants(graph, a['target']))}. Human confirmation required.",
            )
        )
    return dict(
        role=role,
        agent=agent_name(spec, role),
        mode="local deterministic rules",
        evidence_ids=[e["id"] for e in visible[-5:]],
        proposals=proposals,
        workflow=[
            dict(step="Observe", status="completed", detail=f"Read {len(visible)} visible events"),
            dict(
                step="Analyze",
                status="completed",
                detail=f"{len(impacted)} degraded systems in this role",
            ),
            dict(step="Propose", status="completed", detail=f"{len(proposals)} bounded actions"),
            dict(
                step="Budget review", status="completed", detail="Checked remaining response budget"
            ),
            dict(
                step="Human decision", status="waiting", detail="Suggestions do not execute actions"
            ),
        ],
    )


def commander_workflow(spec, result, specialists, decisions=()):
    """Planner → Critic → Commander synthesis across specialists. Recommends; never executes."""
    graph = graph_for(spec)
    health = {n["id"]: n["health"] for n in result["nodes"]}
    degraded = {k for k, v in health.items() if v < 75}
    # The most upstream degraded systems are the best root-cause hypotheses.
    roots = sorted(
        (k for k in degraded if not (nx.ancestors(graph, k) & degraded)),
        key=lambda k: health[k],
    )
    committed = {d["action_id"] for d in decisions}
    remaining = result["metrics"]["budget"] - result["metrics"]["spent"]
    labels = {n["id"]: n["label"] for n in spec["nodes"]}
    seen, proposals, critic = set(), [], []
    for agent in specialists:
        for p in agent["proposals"]:
            if p["action_id"] in committed:
                critic.append(f"{p['label']} is already committed; ignored duplicate proposal.")
                continue
            if p["action_id"] in seen:
                critic.append(f"{p['label']} proposed by several specialists; merged.")
                continue
            seen.add(p["action_id"])
            proposals.append(dict(p, proposed_by=agent["agent"]))
    targets = {}
    for p in proposals:
        targets.setdefault(p["target"], []).append(p)
    for target, items in targets.items():
        if len(items) > 1:
            critic.append(
                f"Competing responses for {labels[target]}: "
                + " vs ".join(i["label"] for i in items)
                + ". Choose one to avoid wasted budget."
            )
    for p in proposals:
        if health.get(p["target"], 100) >= 75 and not p["label"].lower().startswith(
            ("inspect", "trace", "survey", "review", "investigate", "audit")
        ):
            critic.append(
                f"{p['label']} targets a currently healthy system; possible over-reaction."
            )
    ranked = sorted(
        proposals,
        key=lambda p: (
            -(p["target"] in roots),
            -((len(nx.descendants(graph, p["target"])) + 1) * (100 - health.get(p["target"], 100)))
            / max(1, p["cost"]),
        ),
    )
    plan, spend = [], 0
    for p in ranked:
        fits = spend + p["cost"] <= remaining
        plan.append(dict(p, within_budget=fits, priority=len(plan) + 1))
        if fits:
            spend += p["cost"]
    if spend > remaining * 0.8:
        critic.append(
            "Plan consumes most of the remaining budget; keep a reserve for later cascades."
        )
    return dict(
        agent=agent_name(spec, "executive")
        if "executive" in (spec.get("agents") or {})
        else "Incident commander",
        mode="local deterministic synthesis",
        hypothesis=[
            dict(
                node=k,
                label=labels[k],
                health=health[k],
                reason="Degraded with no degraded upstream dependency",
            )
            for k in roots[:3]
        ],
        critic=critic or ["No conflicts detected between specialist proposals."],
        plan=plan,
        planned_cost=spend,
        remaining_budget=remaining,
        workflow=[
            dict(step="Plan", status="completed", detail=f"{len(proposals)} unique proposals"),
            dict(step="Critic", status="completed", detail=f"{len(critic)} concerns raised"),
            dict(
                step="Prioritize", status="completed", detail=f"{len(roots)} root-cause candidates"
            ),
            dict(step="Human approval", status="waiting", detail="Commit actions individually"),
        ],
    )
