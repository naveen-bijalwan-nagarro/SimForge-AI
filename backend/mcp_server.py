"""SimForge MCP server: a controlled tool set that Codex (or any MCP client) can operate.

Run:  python scripts/mcp_simforge.py        (stdio transport)
Codex: see scripts/codex-sandbox.ps1 / codex-sandbox.sh, which attach this server with -c flags.

Tools read and validate data and can *submit* drafts for administrator approval. They never
publish scenarios, execute generated code or reach production systems.
"""

import json

import yaml
from mcp.server import MCPServer

from . import catalog, datasets, packs, store
from .engine import simulate
from .factory import checks, compiler, knowledge

server = MCPServer(
    "simforge",
    instructions=(
        "SimForge simulation tools. Draft scenario packs as YAML, validate and test them until every check passes, "
        "then submit_for_approval. Publishing is always done by a human administrator in the SimForge UI."
    ),
)

PACK_FORMAT = """\
A scenario pack is a YAML list of worlds. Required per world:
  key (lowercase_snake), title, category, summary, unit (what flows, e.g. orders), impact (label for losses)
  nodes: [[id, label, role, capacity 1-30, evidence modality, source system], ...]   (3-16 systems)
     roles: investigator, operations, finance, security, safety, engineering, medical, legal, emergency, executive
     modalities: log, email, sensor, image, video, map, ticket, document, transaction, graph, chat, kpi
  edges: [[from_id, to_id], ...]   acyclic, every system connected
  incident: {node: first_system, cause: hidden root cause (>=10 chars), signal: what learners first observe}
  actions: [[id, label, target, effect, cost, duration_minutes, description], ...]
     effects: repair (fixes root cause), contain (isolate), reroute (bypass), boost (temporary capacity), inspect (evidence)
     include a 'repair' on the incident node and at least one 'inspect'
Optional: extra_incidents [{node, tick, severity, cause, signal}], secondary (cascade system),
  rules [{name, at minute, when: ["node.intrinsic<60", "!node.isolated"], target, health 0-100, message}],
  decoys [wrong-but-plausible causes], agents {role: display name}, entity {field: SharedKind | [min,max] | [choices] | 'seq:PREFIX'},
  emits [{signal, node, below}], consumes [signal], visual (surface|tower|turbine|traffic|thermal|aerial|cells),
  visuals {node: kind}, environment_style (workflow|voxel|service_app), budget, objectives, building_blocks.
Shared kinds: Customer, Account, Product, Supplier, Machine, Employee, Vehicle, Location, Order, Sensor, Asset.
"""


def _load(yaml_text):
    items = yaml.safe_load(yaml_text)
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list) or not items:
        raise ValueError("YAML must contain one world (mapping) or a list of worlds")
    return items


@server.tool()
def get_pack_format() -> str:
    """Return the scenario pack format reference and an example world."""
    example = next(s for s in catalog.world_specs() if s["key"] == "wind_turbine")
    return PACK_FORMAT + "\nEXAMPLE:\n" + packs.to_yaml(example)


@server.tool()
def list_scenarios(category: str = "") -> list[dict]:
    """List published scenario keys, titles and categories (optionally filtered by category text)."""
    items = catalog.all_scenarios([r["payload"] for r in store.list_resources("scenario")])
    return [dict(key=s["key"], title=s["title"], category=s.get("category"), kind=s["kind"]) for s in items if category.lower() in str(s.get("category", "")).lower()]


@server.tool()
def get_scenario_pack(key: str) -> str:
    """Return an existing world as editable pack YAML (a good starting point for variants)."""
    spec = next((s for s in catalog.world_specs() if s["key"] == key), None)
    if not spec:
        raise ValueError("Unknown world key; use list_scenarios")
    return packs.to_yaml(spec)


@server.tool()
def search_sop(query: str, sop_id: str = "") -> list[dict]:
    """Search sanitized SOP chunks in the knowledge base (hybrid lexical + vector)."""
    return knowledge.search(query, sop_id or None, 5)


@server.tool()
def extract_business_rules(sop_id: str) -> dict:
    """Extract steps, roles, systems, thresholds and untrusted lines from an uploaded (sanitized) SOP."""
    row = store.get(sop_id, "sop")
    if not row:
        raise ValueError("Unknown SOP id")
    a = compiler.analyze(row["payload"]["text"])
    return {k: a[k] for k in ("title", "purpose", "roles", "steps", "thresholds", "systems", "injections", "prohibited")}


@server.tool()
def create_scenario_from_sop(sop_id: str, objective: str = "") -> str:
    """Draft a scenario pack (YAML) from an uploaded SOP using the built-in engineer, already repaired."""
    row = store.get(sop_id, "sop")
    if not row:
        raise ValueError("Unknown SOP id")
    a = compiler.analyze(row["payload"]["text"])
    pack = compiler.draft(a, objective)
    for _ in range(3):
        report = checks.run_all(pack, a)
        if not report["failures"]:
            break
        pack, _changes = compiler.repair(pack, a, report["failures"])
    return yaml.safe_dump([pack], sort_keys=False, allow_unicode=True, width=110)


@server.tool()
def validate_scenario(yaml_text: str) -> list[dict]:
    """Structural validation of every world in the YAML. Empty problem lists mean valid."""
    out = []
    for item in _load(yaml_text):
        out.append(dict(key=item.get("key"), problems=packs.validate_world(packs.expand(item, "mcp"))))
    return out


@server.tool()
def run_scenario_tests(yaml_text: str) -> list[dict]:
    """Run behavioural tests and red-team checks (prompt injection, PII, agency, tool misuse) per world."""
    out = []
    empty = dict(steps=[], roles=[], thresholds=[], injections=[], prohibited=[], notes=[], title="", purpose="", systems=[], entities=[])
    for item in _load(yaml_text):
        spec = packs.expand(item, "mcp")
        results = packs.scenario_tests(spec)
        if not packs.validate_world(spec):
            results += [c for c in checks.redteam(item, spec, empty) if c["category"] != "hallucination"]
        out.append(dict(key=item.get("key"), passed=sum(c["passed"] for c in results), total=len(results), failures=[c for c in results if not c["passed"]]))
    return out


@server.tool()
def generate_simulator(yaml_text: str) -> dict:
    """Expand a world and simulate it without responses; returns timeline highlights and ground truth."""
    spec = packs.expand(_load(yaml_text)[0], "mcp")
    problems = packs.validate_world(spec)
    if problems:
        return dict(problems=problems)
    result = simulate(spec, 101, 80, 40, [])
    return dict(
        events=[dict(tick=e["tick"], kind=e["kind"], node=e["node"], message=e["message"]) for e in result["events"][:25]],
        final_service=result["metrics"]["service"],
        loss=result["metrics"]["loss"],
        ground_truth=result["ground_truth"],
    )


@server.tool()
def generate_dataset(scenario_key: str = "", yaml_text: str = "", rows: int = 5) -> dict:
    """Recommend a linked multi-table dataset schema for a world and return a few preview rows per table."""
    if yaml_text:
        spec = packs.expand(_load(yaml_text)[0], "mcp")
    else:
        spec = next((s for s in catalog.world_specs() if s["key"] == scenario_key), None)
        if not spec:
            raise ValueError("Provide a known scenario_key or yaml_text")
    schema = datasets.recommend(spec)
    tables, truth = datasets.generate(schema, preview_rows=max(1, min(rows, 20)))
    return dict(schema={k: v for k, v in schema.items() if k != "guide"}, preview={k: datasets.public_rows(v[:rows]) for k, v in tables.items()}, anomalies=[dict(type=a["type"], table=a["table"], count=a["count"]) for a in truth["anomalies"]])


@server.tool()
def validate_dataset(schema_json: str) -> list[str]:
    """Validate a Dataset Studio schema (JSON). Returns problems with exact table/column paths."""
    return datasets.validate(json.loads(schema_json))


@server.tool()
def score_learner(scenario_key: str, decisions: list[dict], seed: int = 2026, population: int = 200, horizon: int = 45) -> dict:
    """Score a decision log ([{action_id, tick}]) against the identical no-action baseline."""
    spec = next((s for s in catalog.world_specs() if s["key"] == scenario_key), None)
    if not spec:
        raise ValueError("Unknown scenario key")
    run = simulate(spec, seed, population, horizon, decisions)
    base = simulate(spec, seed, population, horizon, [])
    return dict(score=run["metrics"]["score"], baseline_score=base["metrics"]["score"], loss_avoided=round(base["metrics"]["loss"] - run["metrics"]["loss"], 2), scorecard=run["scorecard"])


@server.tool()
def submit_for_approval(yaml_text: str, note: str = "") -> dict:
    """Submit a tested pack as a draft for administrator review. This never publishes."""
    from .studio import pack_draft

    store.initialize()
    results = []
    with store.connection() as db:
        admin = db.execute("SELECT id FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
        admins = [r[0] for r in db.execute("SELECT id FROM users WHERE role='admin'")]
    if not admin:
        raise ValueError("No administrator account exists")
    for item in _load(yaml_text):
        problems = packs.validate_world(packs.expand(item, "codex-mcp"))
        if problems:
            results.append(dict(key=item.get("key"), submitted=False, problems=problems))
            continue
        draft = pack_draft(item, admin[0], "codex-mcp", dict(note=note[:500]))
        store.notify(admins, f"draft:{draft['id']}", "Codex submitted a scenario draft", f"{draft['definition']['title']}: {sum(c['passed'] for c in draft['checks'])}/{len(draft['checks'])} checks passed. Review and publish in Scenario studio.")
        results.append(dict(key=item.get("key"), submitted=True, draft_id=draft["id"], checks_passed=all(c["passed"] for c in draft["checks"])))
    return dict(results=results, next_step="An administrator reviews and publishes the draft in Scenario studio; learners are then notified.")


def main():
    store.initialize()
    server.run()


if __name__ == "__main__":
    main()
