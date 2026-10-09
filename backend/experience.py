"""Guided, relational training environments backed by the actual simulation workload.

Definitions and datasets are data, never executable uploads. Each prepared environment
freezes its scenario and workload; learner decisions change processing, not the seed.
"""

import copy
import random
from collections import Counter

from .engine import simulate

# Every original exercise has its own operational journey and business record labels.
TRAINING_JOURNEYS = {
    "sales_decline": (
        "Sales analyst",
        "customers",
        "orders",
        [
            "Campaign intake",
            "Lead qualification",
            "Pricing review",
            "Order capture",
            "Fulfilment",
            "Revenue review",
        ],
    ),
    "customer_churn": (
        "Customer success analyst",
        "customers",
        "tickets",
        [
            "Customer signals",
            "Support triage",
            "Service delivery",
            "Renewal review",
            "Retention offer",
            "Account outcome",
        ],
    ),
    "payment_fraud": (
        "Payments investigator",
        "customers",
        "invoices",
        [
            "Payment intake",
            "Identity review",
            "Transaction screening",
            "Manual investigation",
            "Settlement",
            "Customer remediation",
        ],
    ),
    "supplier_risk": (
        "Supply planner",
        "suppliers",
        "orders",
        [
            "Supplier commitments",
            "Inbound shipping",
            "Receiving inspection",
            "Inventory allocation",
            "Order fulfilment",
            "Customer delivery",
        ],
    ),
    "budget_overrun": (
        "Finance controller",
        "employees",
        "invoices",
        [
            "Budget allocation",
            "Purchase requests",
            "Approval review",
            "Invoice matching",
            "Payment release",
            "Variance analysis",
        ],
    ),
    "service_sla": (
        "Service desk lead",
        "customers",
        "tickets",
        [
            "Case intake",
            "Priority triage",
            "Specialist assignment",
            "Resolution",
            "Customer validation",
            "SLA review",
        ],
    ),
    "workforce_attrition": (
        "Workforce analyst",
        "employees",
        "tickets",
        [
            "Staffing signals",
            "Workload allocation",
            "Manager review",
            "Retention planning",
            "Coverage scheduling",
            "Workforce outcome",
        ],
    ),
    "quality_defect": (
        "Quality engineer",
        "products",
        "quality_inspections",
        [
            "Material intake",
            "Production batch",
            "Quality inspection",
            "Defect investigation",
            "Rework",
            "Release approval",
        ],
    ),
    "cyber_incident": (
        "SOC investigator",
        "employees",
        "alerts",
        [
            "Identity events",
            "Endpoint monitoring",
            "Alert correlation",
            "Incident triage",
            "Containment",
            "Service recovery",
        ],
    ),
    "claims_leakage": (
        "Claims investigator",
        "customers",
        "claims",
        [
            "Claim intake",
            "Coverage check",
            "Evidence review",
            "Fraud investigation",
            "Settlement approval",
            "Claims audit",
        ],
    ),
    "retail_demand": (
        "Demand planner",
        "products",
        "orders",
        [
            "Sales signals",
            "Demand forecast",
            "Replenishment",
            "Warehouse picking",
            "Store allocation",
            "Shelf availability",
        ],
    ),
    "data_quality": (
        "Data reliability analyst",
        "products",
        "orders",
        [
            "Source ingestion",
            "Schema validation",
            "Entity matching",
            "Quality checks",
            "Reporting pipeline",
            "Business dashboard",
        ],
    ),
    "aml_monitoring": (
        "AML investigator",
        "customers",
        "invoices",
        [
            "Account onboarding",
            "Transfer monitoring",
            "Network screening",
            "Case investigation",
            "Control decision",
            "Compliance review",
        ],
    ),
    "healthcare_billing": (
        "Billing analyst",
        "customers",
        "claims",
        [
            "Encounter intake",
            "Coding review",
            "Billing validation",
            "Duplicate screening",
            "Claim submission",
            "Reconciliation",
        ],
    ),
    "telecom_churn": (
        "Telecom service analyst",
        "customers",
        "tickets",
        [
            "Network signals",
            "Customer complaints",
            "Fault triage",
            "Service restoration",
            "Retention review",
            "Subscriber outcome",
        ],
    ),
    "logistics_disruption": (
        "Logistics controller",
        "suppliers",
        "orders",
        [
            "Shipment booking",
            "Route planning",
            "Hub processing",
            "Exception handling",
            "Last mile dispatch",
            "Delivery confirmation",
        ],
    ),
    "public_service_case_backlog": (
        "Public service coordinator",
        "customers",
        "tickets",
        [
            "Application intake",
            "Eligibility review",
            "Case assignment",
            "Evidence verification",
            "Decision approval",
            "Citizen notification",
        ],
    ),
    "esg_supplier_resilience": (
        "Supplier resilience analyst",
        "suppliers",
        "orders",
        [
            "Supplier disclosure",
            "Risk screening",
            "Continuity review",
            "Sourcing decision",
            "Delivery assurance",
            "Compliance reporting",
        ],
    ),
    "learning_compliance": (
        "Learning coordinator",
        "employees",
        "tickets",
        [
            "Training assignment",
            "Enrolment",
            "Learning activity",
            "Assessment",
            "Remediation",
            "Compliance review",
        ],
    ),
    "ecommerce_stockout": (
        "Commerce operations lead",
        "products",
        "orders",
        [
            "Demand intake",
            "Stock reservation",
            "Supplier replenishment",
            "Warehouse fulfilment",
            "Delivery promise",
            "Customer recovery",
        ],
    ),
}


def executable(spec):
    if spec["kind"] == "world":
        return copy.deepcopy(spec)
    from .catalog import world

    _, _, _, stages = TRAINING_JOURNEYS[spec["key"]]
    nodes = [
        (f"stage_{i}", title, ["investigator", "operations", "finance"][i % 3], 4 + i % 3)
        for i, title in enumerate(stages)
    ]
    edges = [(nodes[i][0], nodes[i + 1][0]) for i in range(len(nodes) - 1)]
    # A branch exposes the tradeoff between expedited handling and normal controls.
    edges.append((nodes[1][0], nodes[4][0]))
    result = world(
        spec["key"],
        spec["title"],
        spec["category"],
        spec["summary"],
        nodes,
        edges,
        nodes[0][0],
        spec["root_cause"],
        "cases",
        [
            (
                "investigate",
                "Inspect source records",
                nodes[0][0],
                "inspect",
                200,
                0,
                "Correlate the source records with the affected cases before selecting a response.",
            ),
            (
                "resolve",
                "Correct the source process",
                nodes[0][0],
                "repair",
                2400,
                4,
                "Restore the source after validation; normal processing resumes after four simulated minutes.",
            ),
            (
                "expedite",
                "Activate exception handling",
                nodes[4][0],
                "reroute",
                1500,
                2,
                "Protect downstream cases using an alternate route; the original cause remains.",
            ),
            (
                "capacity",
                "Add a temporary review team",
                nodes[2][0],
                "boost",
                900,
                1,
                "Temporarily increase effective processing; it does not fix the source.",
            ),
        ],
        nodes[3][0],
    )
    result["training_source"] = spec["key"]
    result["environment_style"] = "service_app"
    return result


def briefing(spec):
    world = executable(spec)
    labels = [n["label"] for n in world["nodes"]]
    own = spec.get("learning") or {}
    role = TRAINING_JOURNEYS.get(
        spec["key"], ((spec.get("agents") or {}).get("operations", "Incident coordinator"),)
    )[0]
    mission = (
        f"Keep {labels[-1]} operating while investigating disruption across {labels[0]}, "
        f"{labels[1]} and their dependent systems. Trace individual {world['unit']}, choose "
        "interventions and explain the downstream impact."
    )
    return {
        "role": own.get("role", role),
        "mission": own.get("mission", mission),
        "context": spec["summary"],
        "journey": labels,
        "steps": [
            {
                "title": "Prepare the environment",
                "detail": f"Generate linked people, assets, {world['unit']}, workflow steps and source-system records. All records are synthetic.",
            },
            {
                "title": "Inspect your starting data",
                "detail": f"Follow one work_id from {labels[0]} to {labels[-1]}. Check assignments, planned routes and service deadlines.",
            },
            {
                "title": "Observe live operations",
                "detail": "Start the exercise clock. Watch individual records arrive, queue, process and finish. Compare new signals with the system that produced them.",
            },
            {
                "title": "Investigate and intervene",
                "detail": "Trace a degraded system to its upstream dependencies. Pause to inspect evidence, consult specialists and choose a budgeted response.",
            },
            {
                "title": "Explain the outcome",
                "detail": "Complete the exercise and compare your decisions with the identical no-action baseline. Explain the cause and any unintended consequences.",
            },
        ],
        "success": own.get(
            "success",
            "Restore service, complete more work before deadlines and explain your decision using linked records, while staying within the response budget.",
        ),
        "clock_explanation": "The clock is exercise time, not a countdown or server runtime. At 1× playback, one real second advances one simulated minute. Pause freezes the exercise for investigation.",
        "scope": "A synthetic operational model for practice, not a certified physical, clinical or financial digital twin.",
    }


def decorate(spec):
    spec = copy.deepcopy(spec)
    if spec.get("category") == "Agentic Games":
        spec["category"] = "Agentic Simulation Lab"
    spec["briefing"] = briefing(spec)
    spec["live_supported"] = True
    spec["environment_style"] = spec.get(
        "environment_style", "service_app" if spec["kind"] == "training" else "workflow"
    )
    spec["dataset_count"] = 8 + len(executable(spec)["nodes"])
    return spec


def prepare(spec, seed, population, horizon):
    world = executable(spec)
    initial = simulate(world, seed, population, 0)
    rng = random.Random(seed + 831)
    systems = [
        {
            "system_id": n["id"],
            "label": n["label"],
            "capacity": n["capacity"],
            "specialist": n["role"],
            "source": n.get("source", n["label"]),
            "modality": n.get("modality", "log"),
        }
        for n in world["nodes"]
    ]
    people = [
        {
            "person_id": f"PERSON-{i:04d}",
            "name": f"Synthetic participant {i}",
            "region": ["North", "South", "East", "West"][i % 4],
            "team_id": f"TEAM-{i % len(systems):03d}",
        }
        for i in range(max(12, population // 5))
    ]
    teams = [
        {
            "team_id": f"TEAM-{i:03d}",
            "system_id": n["system_id"],
            "role": n["specialist"],
            "staffing_slots": n["capacity"],
        }
        for i, n in enumerate(systems)
    ]
    assets = [
        {
            "asset_id": f"ASSET-{i:03d}",
            "system_id": n["system_id"],
            "asset_type": n["source"],
            "baseline_health": 100,
        }
        for i, n in enumerate(systems)
    ]
    work = []
    steps = []
    evidence = {f"records_{n['system_id']}": [] for n in systems}
    for i, entity in enumerate(initial["entities"]):
        record = dict(
            entity,
            work_id=entity["id"],
            person_id=people[i % len(people)]["person_id"],
            priority=rng.choice(["normal", "normal", "urgent", "critical"]),
            value_units=rng.randint(100, 8000),
            due_minute=round(entity["arrival"] + 12, 2),
        )
        for key in ("state", "current_node", "finished"):
            record.pop(key, None)
        work.append(record)
        for j, system_id in enumerate(record["planned_path"]):
            index = next(k for k, n in enumerate(systems) if n["system_id"] == system_id)
            step_id = f"{record['work_id']}-S{j:02d}"
            steps.append(
                {
                    "step_id": step_id,
                    "work_id": record["work_id"],
                    "sequence": j,
                    "system_id": system_id,
                    "asset_id": assets[index]["asset_id"],
                    "team_id": teams[index]["team_id"],
                    "expected_minutes": record["service_minutes"],
                }
            )
            evidence[f"records_{system_id}"].append(
                {
                    "record_id": f"REC-{step_id}",
                    "work_id": record["work_id"],
                    "step_id": step_id,
                    "system_id": system_id,
                    "person_id": record["person_id"],
                    "asset_id": assets[index]["asset_id"],
                    "source": systems[index]["source"],
                    "record_type": systems[index]["modality"],
                    "planned_value_units": record["value_units"],
                    "control_status": "awaiting processing",
                    "scheduled_arrival": record["arrival"],
                }
            )
    tables = dict(
        people=people,
        teams=teams,
        assets=assets,
        systems=systems,
        work_items=work,
        workflow_steps=steps,
        dependencies=[dict(link_id=f"LINK-{i:03d}", **e) for i, e in enumerate(world["edges"])],
        response_options=world["actions"],
        **evidence,
    )
    # Existing domain injectors are retained as supporting case-study datasets. These are
    # fixed historical snapshots, not future telemetry or a replacement for the live engine.
    if spec["kind"] == "training":
        from .catalog import legacy_generator

        # Its Faker implementation has class-level seeding; serialize callers in the API.
        bundle = legacy_generator().generate_bundle(spec, seed, 1)
        tables.update(
            {f"case_{key}": rows for key, rows in bundle.items() if isinstance(rows, list)}
        )
    relationships = [
        ["work_items", "person_id", "people", "person_id"],
        ["people", "team_id", "teams", "team_id"],
        ["teams", "system_id", "systems", "system_id"],
        ["assets", "system_id", "systems", "system_id"],
        ["workflow_steps", "work_id", "work_items", "work_id"],
        ["workflow_steps", "system_id", "systems", "system_id"],
        ["workflow_steps", "asset_id", "assets", "asset_id"],
        ["workflow_steps", "team_id", "teams", "team_id"],
        ["dependencies", "source", "systems", "system_id"],
        ["dependencies", "target", "systems", "system_id"],
        ["response_options", "target", "systems", "system_id"],
    ]
    # Normalize the domain-specific dimensions already produced by each scenario's
    # entity template (guilds, aircraft, suppliers, devices, accounts, sensors, etc.).
    # Keep meaningful columns and joins instead of producing disconnected random CSVs.
    from .connections import registry

    master_records = {r["id"]: r for rows in registry().values() for r in rows}
    excluded = {
        "id",
        "work_id",
        "person_id",
        "region",
        "priority",
        "planned_path",
        "arrival",
        "service_minutes",
        "value_units",
        "due_minute",
    }
    for field in sorted(set(work[0]) - excluded):
        values = [r.get(field) for r in work]
        if not all(isinstance(v, str) for v in values) or not any("-" in v for v in values):
            continue
        table = f"dimension_{field}"
        tables[table] = [
            dict(
                master_records.get(v, {}),
                dimension_id=v,
                label=master_records.get(v, {}).get("name", f"Synthetic {field} {v}"),
            )
            for v in sorted(set(values))
        ]
        relationships.append(["work_items", field, table, "dimension_id"])
    for table in evidence:
        relationships.extend(
            [
                [table, "work_id", "work_items", "work_id"],
                [table, "step_id", "workflow_steps", "step_id"],
            ]
        )
    errors = []
    for table, col, target, target_col in relationships:
        known = {r[target_col] for r in tables[target]}
        if any(r[col] not in known for r in tables[table]):
            errors.append(f"Broken relationship: {table}.{col}")
    if errors:
        raise ValueError("; ".join(errors))
    return dict(
        spec=world,
        original=spec,
        seed=seed,
        population=population,
        horizon=horizon,
        tables=tables,
        relationships=relationships,
        validation={
            "passed": True,
            "foreign_key_checks": len(relationships),
            "work_items": len(work),
            "workflow_steps": len(steps),
            "errors": errors,
        },
    )


def prepared_view(row):
    p = row["payload"]
    return dict(
        id=row["id"],
        owner=row["owner"],
        title=p["spec"]["title"],
        scenario_key=p["original"]["key"],
        seed=p["seed"],
        population=p["population"],
        horizon=p["horizon"],
        briefing=briefing(p["original"]),
        validation=p["validation"],
        tables={
            k: {
                "rows": len(v),
                "columns": list(v[0]) if v else [],
                "description": table_description(k),
            }
            for k, v in p["tables"].items()
        },
        relationships=p["relationships"],
        status="ready",
    )


def table_description(name):
    if name.startswith("dimension_"):
        return "Domain-specific master records joined directly to the generated work items."
    if name.startswith("case_"):
        return "Historical synthetic case-study snapshot; not live exercise telemetry."
    if name.startswith("records_"):
        return "Source-system records linked to work items and workflow steps; status updates during playback."
    return {
        "people": "Synthetic participants joined to operating teams.",
        "teams": "Specialists and capacity assigned to each system.",
        "assets": "Operational assets supporting workflow systems.",
        "systems": "The processing systems visible in the live scene.",
        "work_items": "The actual generated workload consumed by the engine, including routes, arrival times and deadlines.",
        "workflow_steps": "One row per planned work-item step, joined to its system, asset and team.",
        "dependencies": "Directed dependencies through which failures propagate.",
        "response_options": "Available interventions, budgets, targets and time to effect.",
        "live_telemetry": "Measured engine state at each elapsed simulated minute; no future observations.",
        "activity_log": "Actual record arrivals, queues, processing and completions from the simulation.",
    }.get(name, "Synthetic training records.")


def live_summary(result):
    counts = Counter((e["current_node"], e["state"]) for e in result["entities"])
    states = Counter(e["state"] for e in result["entities"])
    return {
        "states": dict(states),
        "systems": [
            {
                "system_id": n["id"],
                "label": n["label"],
                "health": n["health"],
                "queued": counts[n["id"], "queued"],
                "processing": counts[n["id"], "processing"],
                "records": [e["id"] for e in result["entities"] if e["current_node"] == n["id"]][
                    :5
                ],
            }
            for n in result["nodes"]
        ],
        "activity": result.get("activity", [])[-35:][::-1],
        "explanation": (
            "Work is waiting for the exercise clock to start."
            if result["tick"] == 0
            else f"{states['processing']} records are processing, {states['queued']} are waiting for capacity, "
            f"and {states['completed']} have finished. Follow a work_id across the data and activity log."
        ),
    }
