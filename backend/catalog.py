"""Scenario definitions are data, never executable user-supplied Python."""

import copy
import importlib.util
from functools import lru_cache

import yaml
from .settings import ROOT

LEGACY = ROOT / "legacy" / "safesim_studio"
BUILTIN = ROOT / "backend" / "builtin"


@lru_cache
def legacy_catalog():
    return yaml.safe_load((BUILTIN / "training_catalog.yaml").read_text(encoding="utf-8"))


@lru_cache
def legacy_generator():
    spec = importlib.util.spec_from_file_location(
        "simforge_legacy_generator", BUILTIN / "training_generator.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def world(
    key, title, category, summary, nodes, edges, incident, cause, unit, actions, secondary=None
):
    return {
        "key": key,
        "title": title,
        "category": category,
        "kind": "world",
        "difficulty": "Expert",
        "summary": summary,
        "objective": "Investigate the disruption, coordinate specialists, and recover service within the response budget.",
        "nodes": [{"id": n[0], "label": n[1], "role": n[2], "capacity": n[3]} for n in nodes],
        "edges": [{"source": a, "target": b} for a, b in edges],
        "incident": {"node": incident, "tick": 5, "severity": 0.78, "cause": cause},
        "secondary": secondary,
        "unit": unit,
        "budget": 10000,
        "actions": [
            dict(
                id=a[0],
                label=a[1],
                target=a[2],
                effect=a[3],
                cost=a[4],
                duration=a[5],
                description=a[6],
            )
            for a in actions
        ],
        "modalities": ["relational", "event_log", "time_series", "graph"],
        "source": "Locally generated synthetic records",
        "license": "No external dataset required",
    }


WORLDS = [
    world(
        "mmorpg_economy",
        "MMORPG Economy Crisis",
        "Agentic Games",
        "A currency exploit spreads through guild trades, auction prices and player trust. Stabilize the economy without closing the whole game.",
        [
            ("mint", "Currency mint", "investigator", 8),
            ("guilds", "Guild trading", "investigator", 6),
            ("auction", "Auction house", "operations", 5),
            ("craft", "Crafting market", "operations", 6),
            ("players", "Player experience", "finance", 8),
            ("revenue", "Game revenue", "finance", 6),
        ],
        [
            ("mint", "guilds"),
            ("guilds", "auction"),
            ("auction", "craft"),
            ("craft", "players"),
            ("players", "revenue"),
        ],
        "mint",
        "A duplicated quest-reward transaction creates unbacked currency.",
        "trades",
        [
            (
                "patch_rewards",
                "Patch reward idempotency",
                "mint",
                "repair",
                2200,
                4,
                "Repair the source; requires four simulated minutes.",
            ),
            (
                "freeze_auction",
                "Suspend auction settlement",
                "auction",
                "contain",
                600,
                1,
                "Break contagion but lose auction availability.",
            ),
            (
                "audit_guilds",
                "Trace suspicious guild transfers",
                "guilds",
                "inspect",
                250,
                0,
                "Reveal observed guild evidence to investigators.",
            ),
            (
                "market_maker",
                "Provide crafting liquidity",
                "craft",
                "boost",
                1500,
                1,
                "Restore capacity temporarily; does not repair the mint.",
            ),
        ],
        "auction",
    ),
    world(
        "airline_crisis",
        "Airline Operations Command",
        "Complex Operations",
        "An aircraft defect cascades through crew duty windows, gate occupancy and passenger connections.",
        [
            ("aircraft", "Aircraft readiness", "investigator", 5),
            ("crew", "Crew duty roster", "operations", 4),
            ("gates", "Gate turnaround", "operations", 4),
            ("flights", "Flight departures", "operations", 6),
            ("connections", "Passenger connections", "finance", 5),
            ("baggage", "Baggage transfer", "investigator", 6),
        ],
        [
            ("aircraft", "crew"),
            ("crew", "gates"),
            ("gates", "flights"),
            ("flights", "connections"),
            ("flights", "baggage"),
        ],
        "aircraft",
        "A recurring hydraulic fault grounds the assigned rotation aircraft.",
        "rotations",
        [
            (
                "swap_aircraft",
                "Assign spare aircraft",
                "aircraft",
                "repair",
                2800,
                5,
                "Replace the grounded aircraft after engineering clearance.",
            ),
            (
                "reserve_crew",
                "Activate reserve crew",
                "crew",
                "boost",
                1400,
                1,
                "Add roster capacity for the disruption window.",
            ),
            (
                "protect_connections",
                "Protect connection banks",
                "connections",
                "reroute",
                1100,
                2,
                "Decouple connections using rebooking capacity.",
            ),
            (
                "inspect_tail",
                "Inspect aircraft history",
                "aircraft",
                "inspect",
                200,
                0,
                "Review synthetic engineering evidence.",
            ),
        ],
        "crew",
    ),
    world(
        "cyber_business",
        "Cyber + Business War Room",
        "Security & Governance",
        "An identity compromise interrupts warehouse systems, shipments, customer support and cash flow.",
        [
            ("identity", "Identity service", "investigator", 6),
            ("warehouse", "Warehouse control", "operations", 5),
            ("shipping", "Shipment release", "operations", 4),
            ("support", "Customer support", "operations", 6),
            ("payments", "Payment settlement", "finance", 4),
            ("cash", "Cash position", "finance", 8),
        ],
        [
            ("identity", "warehouse"),
            ("warehouse", "shipping"),
            ("shipping", "support"),
            ("shipping", "payments"),
            ("payments", "cash"),
        ],
        "identity",
        "An overprivileged synthetic service identity is used outside its normal workflow.",
        "orders",
        [
            (
                "rotate_identity",
                "Revoke and rotate identity",
                "identity",
                "repair",
                2000,
                4,
                "Restore a constrained identity after rotating credentials.",
            ),
            (
                "isolate_warehouse",
                "Isolate warehouse integration",
                "warehouse",
                "contain",
                500,
                1,
                "Interrupt propagation while suspending warehouse service.",
            ),
            (
                "manual_dispatch",
                "Enable manual dispatch",
                "shipping",
                "reroute",
                1700,
                2,
                "Use an isolated manual path for shipments.",
            ),
            (
                "trace_identity",
                "Trace identity events",
                "identity",
                "inspect",
                200,
                0,
                "Review synthetic identity telemetry.",
            ),
        ],
        "payments",
    ),
    world(
        "supply_chain",
        "Global Supply-Chain Crisis",
        "Complex Operations",
        "Supplier insolvency creates port congestion, inventory shortages and missed customer commitments.",
        [
            ("supplier", "Supplier production", "investigator", 5),
            ("port", "Port clearance", "operations", 4),
            ("warehouse", "Warehouse inventory", "operations", 6),
            ("factory", "Factory assembly", "operations", 5),
            ("orders", "Customer orders", "finance", 6),
            ("cash", "Working capital", "finance", 8),
        ],
        [
            ("supplier", "port"),
            ("port", "warehouse"),
            ("warehouse", "factory"),
            ("factory", "orders"),
            ("orders", "cash"),
        ],
        "supplier",
        "The single-source component supplier stops dispatch after a liquidity failure.",
        "shipments",
        [
            (
                "alternate_supplier",
                "Qualify alternate supplier",
                "supplier",
                "repair",
                2600,
                5,
                "Restore upstream component supply.",
            ),
            (
                "reroute_port",
                "Reroute inbound freight",
                "port",
                "reroute",
                1800,
                2,
                "Avoid port dependency using a limited alternate route.",
            ),
            (
                "release_buffer",
                "Release safety inventory",
                "warehouse",
                "boost",
                1200,
                1,
                "Improve downstream capacity for six minutes.",
            ),
            (
                "trace_supplier",
                "Inspect supplier commitments",
                "supplier",
                "inspect",
                200,
                0,
                "Expose supplier dispatch evidence.",
            ),
        ],
        "port",
    ),
    world(
        "city_disaster",
        "Smart-City Emergency",
        "Agentic Games",
        "Flooding closes roads, delays ambulances and constrains hospitals, shelters and food distribution.",
        [
            ("roads", "Road access", "investigator", 6),
            ("ambulance", "Emergency transport", "operations", 4),
            ("hospital", "Hospital intake", "operations", 4),
            ("shelter", "Shelter capacity", "operations", 5),
            ("food", "Food distribution", "finance", 5),
            ("citizens", "Citizen wellbeing", "finance", 8),
        ],
        [
            ("roads", "ambulance"),
            ("ambulance", "hospital"),
            ("roads", "shelter"),
            ("shelter", "food"),
            ("hospital", "citizens"),
            ("food", "citizens"),
        ],
        "roads",
        "A flooded road junction cuts access to two critical service districts.",
        "missions",
        [
            (
                "clear_roads",
                "Deploy road-clearance crews",
                "roads",
                "repair",
                2300,
                5,
                "Restore district access with a finite crew allocation.",
            ),
            (
                "airlift",
                "Open emergency transport route",
                "ambulance",
                "reroute",
                2000,
                2,
                "Provide transport independent of the damaged roads.",
            ),
            (
                "field_hospital",
                "Activate field intake unit",
                "hospital",
                "boost",
                1500,
                1,
                "Increase temporary treatment capacity.",
            ),
            (
                "survey_roads",
                "Survey affected junctions",
                "roads",
                "inspect",
                200,
                0,
                "Reveal road observations without prescribing medical decisions.",
            ),
        ],
        "shelter",
    ),
]

# Branching, merging dependencies make the flagship worlds richer than linear pipelines.
BRANCHES = {
    "mmorpg_economy": (
        [
            ("fraud", "Fraud review", "investigator", 4),
            ("chargebacks", "Refund queue", "finance", 4),
            ("retention", "Player retention", "finance", 6),
            ("treasury", "Treasury reserve", "finance", 5),
        ],
        [
            ("guilds", "fraud"),
            ("fraud", "chargebacks"),
            ("players", "retention"),
            ("chargebacks", "treasury"),
            ("revenue", "treasury"),
        ],
    ),
    "airline_crisis": (
        [
            ("maintenance", "Maintenance planning", "investigator", 3),
            ("slots", "Airport slots", "operations", 4),
            ("hotel", "Passenger care", "finance", 5),
            ("recovery", "Network recovery", "operations", 6),
        ],
        [
            ("aircraft", "maintenance"),
            ("maintenance", "slots"),
            ("flights", "slots"),
            ("connections", "hotel"),
            ("slots", "recovery"),
            ("baggage", "recovery"),
        ],
    ),
    "cyber_business": (
        [
            ("erp", "ERP integration", "investigator", 5),
            ("reconciliation", "Reconciliation", "finance", 4),
            ("communications", "Crisis communications", "operations", 5),
            ("recovery", "Business continuity", "operations", 6),
        ],
        [
            ("identity", "erp"),
            ("erp", "payments"),
            ("payments", "reconciliation"),
            ("support", "communications"),
            ("reconciliation", "recovery"),
            ("communications", "recovery"),
        ],
    ),
    "supply_chain": (
        [
            ("customs", "Customs documentation", "investigator", 3),
            ("contracts", "Contract commitments", "finance", 5),
            ("planning", "Production planning", "operations", 4),
            ("recovery", "Delivery recovery", "operations", 6),
        ],
        [
            ("port", "customs"),
            ("customs", "planning"),
            ("factory", "planning"),
            ("orders", "contracts"),
            ("contracts", "recovery"),
            ("planning", "recovery"),
        ],
    ),
    "city_disaster": (
        [
            ("water", "Water distribution", "operations", 4),
            ("dispatch", "Volunteer dispatch", "operations", 4),
            ("communications", "District communications", "investigator", 5),
            ("recovery", "District recovery", "finance", 6),
        ],
        [
            ("food", "water"),
            ("roads", "dispatch"),
            ("dispatch", "shelter"),
            ("roads", "communications"),
            ("citizens", "recovery"),
            ("water", "recovery"),
            ("communications", "recovery"),
        ],
    ),
}
for spec in WORLDS:
    extra_nodes, extra_edges = BRANCHES[spec["key"]]
    spec["nodes"].extend(
        dict(id=node_id, label=label, role=role, capacity=capacity)
        for node_id, label, role, capacity in extra_nodes
    )
    spec["edges"].extend(dict(source=a, target=b) for a, b in extra_edges)
    spec["flagship"] = True
    spec["actions"].append(
        dict(
            id="recovery_team",
            label="Deploy cross-functional recovery team",
            target=extra_nodes[-1][0],
            effect="reroute",
            cost=1800,
            duration=3,
            description="Protect the final business outcome through an independent recovery path.",
        )
    )

# Additional worlds use a shared five-stage workflow template with domain-specific incidents.
EXTENSIONS = [
    (
        "game_launch",
        "Global Game Launch",
        "Agentic Games",
        "CDN",
        "Matchmaking",
        "Game servers",
        "Player queues",
        "Store payments",
        "sessions",
        "A regional content version mismatch amplifies retries at launch.",
    ),
    (
        "esports",
        "Esports Tournament Control",
        "Agentic Games",
        "Match servers",
        "Referee review",
        "Bracket schedule",
        "Broadcast",
        "Tournament completion",
        "matches",
        "A server clock drift invalidates match telemetry and delays the bracket.",
    ),
    (
        "space_mission",
        "Space Mission Control",
        "Agentic Games",
        "Power bus",
        "Thermal control",
        "Communications",
        "Science payload",
        "Mission objectives",
        "tasks",
        "A failed power regulator reduces available spacecraft power.",
    ),
    (
        "hospital_capacity",
        "Hospital Capacity Operations",
        "Complex Operations",
        "Discharge coordination",
        "Bed turnover",
        "Ward capacity",
        "ED admission",
        "Service access",
        "arrivals",
        "Delayed discharge transport blocks bed turnover during an arrival surge.",
    ),
    (
        "smart_grid",
        "Smart Grid Restoration",
        "Complex Operations",
        "Substation",
        "Distribution feeders",
        "Repair dispatch",
        "Local supply",
        "Customer restoration",
        "restorations",
        "A synthetic transformer failure disconnects a high-load feeder.",
    ),
    (
        "ap_fraud",
        "Accounts Payable Investigation",
        "Security & Governance",
        "Vendor master",
        "Purchase orders",
        "Invoice matching",
        "Payment approval",
        "Treasury",
        "invoices",
        "A vendor bank-detail change bypasses independent verification.",
    ),
    (
        "aml_network",
        "AML Network Investigation",
        "Security & Governance",
        "Account onboarding",
        "Device cluster",
        "Transfer network",
        "Case investigation",
        "Review capacity",
        "transfers",
        "Linked synthetic accounts recycle funds through a shared device cluster.",
    ),
    (
        "cloud_incident",
        "Cloud Service Incident",
        "Complex Operations",
        "Deployment",
        "API tier",
        "Request queue",
        "Order service",
        "SLA delivery",
        "requests",
        "A deployment introduces connection leakage in the API tier.",
    ),
    (
        "data_pipeline",
        "Data Pipeline Recovery",
        "Complex Operations",
        "Source schema",
        "ETL ingestion",
        "Warehouse model",
        "Dashboard refresh",
        "Business reporting",
        "batches",
        "A source schema change drops a required downstream join key.",
    ),
    (
        "rag_quality",
        "RAG Quality War Room",
        "Security & Governance",
        "Knowledge index",
        "Retriever",
        "Context assembly",
        "Answer validation",
        "User resolution",
        "queries",
        "A stale retrieval index ranks superseded policies above current guidance.",
    ),
]
for key, title, category, n0, n1, n2, n3, n4, unit, cause in EXTENSIONS:
    WORLDS.append(
        world(
            key,
            title,
            category,
            f"Investigate {n0.lower()} failures and their consequences across {n1.lower()}, {n2.lower()} and {n4.lower()}.",
            [
                ("source", n0, "investigator", 5),
                ("process", n1, "operations", 4),
                ("queue", n2, "operations", 5),
                ("review", n3, "investigator", 4),
                ("outcome", n4, "finance", 6),
            ],
            [
                ("source", "process"),
                ("process", "queue"),
                ("queue", "review"),
                ("review", "outcome"),
                ("source", "review"),
            ],
            "source",
            cause,
            unit,
            [
                (
                    "repair_source",
                    f"Restore {n0.lower()}",
                    "source",
                    "repair",
                    2300,
                    4,
                    "Resolve the upstream failure after validation.",
                ),
                (
                    "alternate_path",
                    f"Bypass {n1.lower()}",
                    "process",
                    "reroute",
                    1600,
                    2,
                    "Open an independent path with reduced capacity.",
                ),
                (
                    "add_capacity",
                    f"Reinforce {n2.lower()}",
                    "queue",
                    "boost",
                    1200,
                    1,
                    "Add temporary processing capacity.",
                ),
                (
                    "investigate",
                    f"Inspect {n0.lower()}",
                    "source",
                    "inspect",
                    200,
                    0,
                    "Collect observed incident evidence.",
                ),
            ],
            "queue",
        )
    )


# Scenario-specific agent names, diagnosis distractors, links and building blocks.
FLAGSHIP_EXTRAS = {
    "mmorpg_economy": dict(
        agents=dict(
            investigator="Fraud investigator",
            operations="LiveOps manager",
            finance="Economy analyst",
        ),
        decoys=[
            "Seasonal event rewards inflate currency supply",
            "An auction-house UI bug hides listings",
            "Bot farms are gold-farming in one zone",
        ],
        emits=[dict(signal="fraud_wave", node="fraud", below=75)],
        consumes=["compromised_credentials"],
        building_blocks=["SimPy", "NetworkX", "Mesa"],
        objectives=["Stable prices", "Player trust", "Revenue"],
    ),
    "airline_crisis": dict(
        agents=dict(
            investigator="Maintenance controller", operations="Ops control", finance="Customer recovery"
        ),
        decoys=["Air-traffic-control slot restrictions", "A crew sickness wave", "Fog at the hub"],
        consumes=["blackout", "network_outage"],
        building_blocks=["SimPy", "NetworkX"],
        objectives=["On-time performance", "Passenger care", "Crew legality"],
    ),
    "cyber_business": dict(
        agents=dict(investigator="SOC analyst", operations="COO office", finance="CFO office"),
        decoys=["A warehouse network switch failure", "A payment-provider outage", "A DDoS on the storefront"],
        emits=[dict(signal="stockouts", node="shipping", below=75)],
        consumes=["compromised_credentials", "data_breach"],
        building_blocks=["MITRE CALDERA", "NetworkX", "SimPy"],
        objectives=["Containment", "Business continuity", "Cash protection"],
    ),
    "supply_chain": dict(
        agents=dict(investigator="Supplier risk analyst", operations="Supply planner", finance="Commercial finance"),
        decoys=["Port labour strike", "A demand spike from promotions", "Customs system outage"],
        emits=[
            dict(signal="stockouts", node="orders", below=55),
            dict(signal="supplier_failure", node="supplier", below=50),
        ],
        consumes=["delayed_shipments", "supplier_failure"],
        building_blocks=["SimPy", "NetworkX", "SDV"],
        objectives=["Service level", "Working capital", "Supplier resilience"],
    ),
    "city_disaster": dict(
        agents=dict(investigator="Situation analyst", operations="Emergency operations", finance="Relief finance"),
        decoys=["A dam-failure rumour", "A power outage in the hospital district", "Road works"],
        emits=[
            dict(signal="hospital_surge", node="hospital", below=75),
            dict(signal="road_closures", node="roads", below=55),
        ],
        consumes=["weather_extreme"],
        building_blocks=["SimPy", "NetworkX", "Mesa"],
        objectives=["Life safety", "Shelter capacity", "Supply continuity"],
    ),
}
ROLE_MODALITY = {"investigator": "log", "operations": "sensor", "finance": "kpi"}
for spec in WORLDS:
    spec.update(copy.deepcopy(FLAGSHIP_EXTRAS.get(spec["key"], {})))
    for node in spec["nodes"]:
        node.setdefault("modality", ROLE_MODALITY.get(node["role"], "log"))
        node.setdefault("source", node["label"])
    spec.setdefault(
        "decoys",
        [
            "A scheduled maintenance window",
            "An unrelated demand spike",
            "A monitoring false positive",
        ],
    )
    spec.setdefault("building_blocks", ["SimPy", "NetworkX"])


def world_specs():
    """Python-defined worlds overlaid by built-in packs (richer versions win) and user packs."""
    from . import packs

    by_key = {s["key"]: s for s in copy.deepcopy(WORLDS)}
    builtin, _ = packs.builtin()
    for spec in builtin:
        by_key[spec["key"]] = spec
    user, _ = packs.user_packs()
    for spec in user:
        if spec["key"] not in by_key:
            by_key[spec["key"]] = spec
    return list(by_key.values())


def all_scenarios(custom=()):
    from .experience import decorate
    old = [
        dict(
            x,
            kind="training",
            category=x["domain"],
            modalities=["relational"],
            source="Synthetic SafeSim generator",
            license="No external dataset required",
        )
        for x in legacy_catalog()
    ]
    return [decorate(s) for s in world_specs() + old + list(custom)]


def public_scenario(scenario):
    return {
        k: v
        for k, v in scenario.items()
        if k
        not in {
            "incident",
            "secondary",
            "root_cause",
            "evidence",
            "recommendation_keywords",
            "inject",
            "incidents_extra",
            "rules",
            "decoys",
        }
    }
