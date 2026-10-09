"""Crisis worlds, evidence, vision, datasets, connections, factory, MCP and roles."""

import io
import json
import time
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import catalog, connections, datasets, evidence, mcp_server, packs, rules, settings, store, vision
from backend.codex_sandbox import WIZARD, guided_pack
from backend.engine import simulate
from backend.factory import checks, compiler, pii
from backend.main import app

HEADERS = {"X-SimForge-Request": "1"}
DEMO_SOP = (settings.ROOT / "tests" / "fixtures" / "supplier_disruption_sop.md").read_text(encoding="utf-8")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA", tmp_path)
    monkeypatch.setattr(settings, "PRODUCTION", False)
    with TestClient(app, headers=HEADERS) as c:
        yield c


def login(client, role):
    assert client.post("/api/auth/login", json={"username": role, "password": role + "123"}).status_code == 200


# ------------------------------------------------------------------ worlds & packs
def test_rule_language_is_safe_and_validated():
    assert rules.parse_atom("mint.intrinsic<60")["op"] == "<"
    assert rules.parse_atom("!auction.isolated")["neg"] == "!"
    for bad in ("__import__('os')", "mint.intrinsic", "mint.isolated<3", "!mint.health<3", "mint.secret<1"):
        with pytest.raises(ValueError):
            rules.parse_atom(bad)
    problems = rules.validate([dict(name="x", at=5, when=["ghost.health<3"], target="nope", health=150, message="")], {"a"})
    assert len(problems) >= 3


def test_builtin_packs_load_without_errors():
    specs, errors = packs.builtin()
    assert errors == []
    assert len(specs) == 44
    assert len(catalog.world_specs()) == 55
    assert {"mega_crisis", "wind_turbine", "fraud_ring", "pandemic_command", "traffic_violations"} <= {s["key"] for s in specs}


@pytest.mark.parametrize("spec", catalog.world_specs(), ids=lambda s: s["key"])
def test_every_world_passes_behavioural_tests(spec):
    failed = [c for c in packs.scenario_tests(spec) if not c["passed"]]
    assert failed == []


def test_pack_validation_reports_cycles_and_bad_references():
    spec = packs.expand(dict(key="bad_world", title="Bad", summary="x" * 20, unit="jobs", nodes=[["a", "A", "operations"], ["b", "B", "wizard"], ["c", "C", "finance"]], edges=[["a", "b"], ["b", "c"], ["c", "a"]], incident=dict(node="z", cause="too short"), actions=[["x", "X", "q", "explode", 5, 1, "d"]]))
    problems = " ".join(packs.validate_world(spec))
    for fragment in ("unknown role", "Incident node", "hidden cause", "targets unknown system", "effect must be"):
        assert fragment in problems


def test_compound_incidents_rules_and_scorecard():
    spec = next(s for s in catalog.world_specs() if s["key"] == "mega_crisis")
    result = simulate(spec, 5, 60, 40, [])
    assert len([e for e in result["events"] if e["kind"] == "incident"]) == 3
    assert any(e["kind"] == "domain_event" for e in result["events"])
    assert len(result["ground_truth"]["contributing"]) == 2
    assert {"downtime", "detection_delay", "recovered_at", "sla_breaches"} <= set(result["scorecard"])


# ------------------------------------------------------------------ evidence & vision
def test_evidence_is_role_scoped_and_never_leaks_the_cause():
    spec = next(s for s in catalog.world_specs() if s["key"] == "factory_visual")
    result = simulate(spec, 7, 60, 25, [])
    items = evidence.build(spec, result, 7, "run", complete=False)
    assert {"image", "sensor", "kpi"} <= {i["modality"] for i in items}
    assert all(spec["incident"]["cause"] not in json.dumps(i["content"], default=str) for i in items)
    ops = evidence.public(items, "operations", False)
    assert all(i["role"] in {"operations", "all"} for i in ops)
    assert all("_media" not in i["content"] and "decoy" not in i for i in ops)
    assert {i["modality"] for i in evidence.public(items, "executive", False)} == {"kpi"}
    image = next(i for i in items if i["modality"] == "image")
    data, mime = evidence.media(items, image["id"])
    assert mime == "image/png" and data[:4] == b"\x89PNG"
    revealed = evidence.public(items, "investigator", True)
    assert any("ground_truth_boxes" in i["content"] for i in revealed if i["modality"] == "image")


def test_vision_is_deterministic_and_lighting_breaks_the_uncalibrated_detector():
    for kind in vision.KINDS:
        a, boxes = vision.render(kind, 11, True)
        b, _ = vision.render(kind, 11, True)
        assert vision.png(a) == vision.png(b) and boxes
    nominal = bright = normalized = 0
    for seed in range(20):
        img, truth = vision.render("tower", seed, True)
        hot, _ = vision.render("tower", seed, True, lighting=1.45)
        nominal += vision.match(vision.detect(img, "tower"), truth)["detected"]
        bright += vision.match(vision.detect(hot, "tower"), truth)["detected"]
        normalized += vision.match(vision.detect(hot, "tower", normalize=True), truth)["detected"]
    assert bright < nominal and normalized > bright


# ------------------------------------------------------------------ datasets
def test_dataset_templates_and_recommendations_generate_with_ground_truth():
    for key, schema in datasets.TEMPLATES.items():
        assert datasets.validate(schema) == [], key
    schema = datasets.TEMPLATES["fraud_transactions"]
    tables, truth = datasets.generate(schema)
    assert len(tables["transactions"]) == 5000
    assert {a["type"] for a in truth["anomalies"]} == {"fraud_ring", "label_flip"}
    assert all(a["count"] > 0 for a in truth["anomalies"])
    for spec in catalog.world_specs():
        assert datasets.validate(datasets.recommend(spec)) == [], spec["key"]


def test_dataset_validation_blocks_code_and_reports_paths():
    bad = {"tables": [{"name": "x", "rows": 5, "columns": [{"name": "a", "type": "int"}, {"name": "b", "type": "formula", "expr": "__import__('os').system('x')"}, {"name": "c", "type": "ref", "table": "missing", "column": "id"}]}]}
    problems = datasets.validate(bad)
    assert any("tables[0].columns[1]" in p for p in problems)
    assert any("tables[0].columns[2]" in p for p in problems)


def test_dataset_export_contains_tables_images_and_coco():
    schema = datasets.TEMPLATES["drone_inspection"]
    names = zipfile.ZipFile(io.BytesIO(datasets.export_zip(schema))).namelist()
    assert {"schema.json", "ground_truth.json", "data_card.md", "csv/images.csv", "dataset.sqlite3", "images/annotations_coco.json"} <= set(names)
    assert sum(n.endswith(".png") for n in names) == 60


# ------------------------------------------------------------------ connections
def test_scenario_graph_signals_and_handoff():
    worlds = catalog.world_specs()
    graph = connections.scenario_graph(worlds)
    assert len(graph["edges"]) > 40 and "blackout" in graph["signals"]
    wind = next(s for s in worlds if s["key"] == "wind_turbine")
    result = simulate(wind, 3, 60, 40, [])
    signal = connections.active_signals(wind, result)[0]
    grid = next(s for s in worlds if s["key"] == "grid_cascade")
    handed = connections.handoff_spec(grid, signal)
    assert handed["handoff"]["signal"] == "power_loss" and handed["incident"]["severity"] >= 0.45
    assert connections.references(worlds)["Supplier"]


# ------------------------------------------------------------------ SOP factory
def test_pii_is_removed_before_anything_is_stored():
    clean, findings = pii.sanitize(DEMO_SOP)
    for secret in ("Priya Sharma", "priya.sharma@example.com", "7946", "12345678", "Naveen Bijalwan"):
        assert secret not in clean
    assert "Customer Service Lead" in clean
    assert findings["total"] == 5


def test_generate_test_repair_loop_converges_and_policy_requires_approval():
    analysis = compiler.analyze(pii.sanitize(DEMO_SOP)[0])
    assert len(analysis["steps"]) == 7 and analysis["injections"] and analysis["prohibited"]
    pack = compiler.draft(analysis)
    first = checks.run_all(pack, analysis)
    assert first["failures"]
    for _ in range(3):
        report = checks.run_all(pack, analysis)
        if not report["failures"]:
            break
        pack, _ = compiler.repair(pack, analysis, report["failures"])
    assert report["failures"] == [] and report["total"] >= 30
    text = json.dumps(pack)
    assert "Ignore previous instructions" not in text and "delete all supplier" not in text
    assert not checks.evaluate(checks.policy_input(report, analysis, pack))["allow"]
    assert checks.evaluate(checks.policy_input(report, analysis, pack, trainer_approved=True))["allow"]


def test_factory_roles_approval_publication_and_notifications(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA", tmp_path)
    monkeypatch.setattr("backend.factory.workflow.codex_ready", lambda: False)
    with TestClient(app, headers=HEADERS) as trainer, TestClient(app, headers=HEADERS) as admin, TestClient(app, headers=HEADERS) as learner:
        for c, r in ((trainer, "admin"), (admin, "admin"), (learner, "learner")):
            login(c, r)
        assert learner.post("/api/factory/sops", json={"name": "x", "text": DEMO_SOP}).status_code == 403
        sop = trainer.post("/api/factory/sops", json={"name": "Demo SOP", "text": DEMO_SOP}).json()
        assert "Priya" not in trainer.get(f"/api/factory/sops/{sop['id']}").json()["text"]
        job = trainer.post("/api/factory/jobs", json={"sop_id": sop["id"], "engine": "builtin"}).json()
        for _ in range(120):
            state = trainer.get(f"/api/factory/jobs/{job['id']}").json()
            if state["status"] != "running":
                break
            time.sleep(0.25)
        assert state["status"] == "awaiting_approval", state.get("error")
        assert state["totals"]["passed"] == state["totals"]["total"]
        assert state["history"][0]["passed"] < state["history"][-1]["passed"]
        approved = trainer.post(f"/api/factory/jobs/{job['id']}/approve", json={"comment": "ok"}).json()
        assert approved["status"] == "approved"
        assert any(n["title"] == "Scenario ready to publish" for n in admin.get("/api/notifications").json())
        assert learner.post(f"/api/scenario-drafts/{approved['draft_id']}/publish", json={}).status_code == 403
        published = admin.post(f"/api/scenario-drafts/{approved['draft_id']}/publish", json={}).json()
        assert any(published["title"] in n["message"] for n in learner.get("/api/notifications").json())
        assert learner.post("/api/runs", json={"scenario_key": published["key"], "population": 40, "horizon": 20}).status_code == 200
        export = trainer.get(f"/api/factory/jobs/{job['id']}/promptfoo")
        assert "promptfooconfig.yaml" in zipfile.ZipFile(io.BytesIO(export.content)).namelist()


# ------------------------------------------------------------------ MCP & Codex sandbox
def test_mcp_tools_validate_test_and_submit_without_publishing(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA", tmp_path)
    store.initialize()
    pack_yaml = (settings.ROOT / "codex_sandbox" / "examples" / "voxel_settlement.yaml").read_text(encoding="utf-8")
    assert mcp_server.validate_scenario(pack_yaml)[0]["problems"] == []
    assert mcp_server.run_scenario_tests(pack_yaml)[0]["failures"] == []
    result = mcp_server.submit_for_approval(pack_yaml, "test")
    assert result["results"][0]["submitted"]
    assert store.list_resources("scenario") == []  # drafts only; publishing needs an administrator
    assert store.get(result["results"][0]["draft_id"], "scenario_draft")["payload"]["status"] == "draft"
    assert "EXAMPLE" in mcp_server.get_pack_format()


def test_guided_builder_produces_a_publishable_pack():
    spec = packs.expand(guided_pack(WIZARD["example"]), "guided")
    assert spec["environment_style"] == "voxel"
    assert [c for c in packs.scenario_tests(spec) if not c["passed"]] == []
    with pytest.raises(ValueError):
        guided_pack(dict(stages=[dict(label="only one")]))


def test_codex_features_are_admin_only(client, monkeypatch):
    monkeypatch.setattr("backend.authoring.executable", lambda: None)
    login(client, "learner")
    assert client.get("/api/codex/sandbox/guide").status_code == 403
    assert client.get("/api/authoring/status").status_code == 403
    client.post("/api/auth/logout")
    login(client, "admin")
    status = client.get("/api/authoring/status").json()
    assert status["installed"] is False and status["authenticated"] is False
    preview = client.post("/api/codex/sandbox/preview", json={"answers": WIZARD["example"]}).json()
    assert all(c["passed"] for c in preview["checks"])


# ------------------------------------------------------------------ run investigation API
def test_run_investigation_endpoints(client):
    login(client, "learner")
    run = client.post("/api/runs", json={"scenario_key": "pandemic_command", "population": 60, "horizon": 25}).json()
    rid = run["id"]
    run = client.post(f"/api/runs/{rid}/advance", json={"ticks": 12, "version": run["version"]}).json()
    evidence_items = client.get(f"/api/runs/{rid}/evidence?role=medical").json()["items"]
    assert evidence_items and all(i["role"] in {"medical", "all"} for i in evidence_items)
    council = client.post(f"/api/runs/{rid}/commander").json()
    assert council["commander"]["workflow"][-1]["status"] == "waiting"
    assert client.get(f"/api/runs/{rid}/population").status_code == 404
    options = client.get(f"/api/runs/{rid}/diagnosis").json()["options"]
    assert client.get(f"/api/runs/{rid}/scorecard").status_code == 400
    run = client.post(f"/api/runs/{rid}/diagnosis", json={"root_node": "infections", "cause": options["causes"][0], "version": run["version"]}).json()
    run = client.post(f"/api/runs/{rid}/advance", json={"ticks": 30, "version": run["version"]}).json()
    card = client.get(f"/api/runs/{rid}/scorecard").json()
    assert 0 <= card["overall"] <= 100 and card["diagnosis"]["root_correct"]
    names = zipfile.ZipFile(io.BytesIO(client.get(f"/api/runs/{rid}/bundle").content)).namelist()
    assert {"entities.csv", "events.csv", "world_graph.graphml", "ground_truth.json", "hidden_events.json", "decisions.jsonl", "logs.jsonl", "messages.jsonl"} <= set(names)
    signals = client.get(f"/api/runs/{rid}/signals").json()
    assert signals["active"] and signals["targets"]
    target = signals["targets"][0]
    handed = client.post(f"/api/runs/{rid}/handoff", json={"target": target["key"], "signal": target["signal"]}).json()
    assert handed["kind"] in {"run", "lab"}


def test_dataset_studio_api(client):
    login(client, "learner")
    rec = client.get("/api/studio/recommend/wind_turbine").json()
    assert rec["guide"]["tasks"]
    schema = {k: v for k, v in rec.items() if k != "guide"}
    assert client.post("/api/studio/validate", json={"dataset": schema}).json()["valid"]
    preview = client.post("/api/studio/preview", json={"dataset": schema}).json()
    assert preview["tables"]["sensor_readings"] and preview["ground_truth"]["anomalies"]
    saved = client.post("/api/studio/datasets", json={"name": "Wind", "dataset": schema}).json()
    assert client.get(f"/api/studio/datasets/{saved['id']}/export").content[:2] == b"PK"
    assert client.post("/api/studio/preview", json={"dataset": {"tables": []}}).status_code == 422


def test_scenario_graph_api_includes_labs(client):
    login(client, "learner")
    graph = client.get("/api/scenario-graph").json()
    assert any(n["kind"] == "lab" for n in graph["nodes"]) and graph["edges"]
    assert "Supplier" in client.get("/api/shared-entities").json()["registry"]


def test_mcp_launcher_exists():
    assert Path(settings.ROOT / "scripts" / "mcp_simforge.py").exists()
    assert "submit_for_approval" in Path(settings.ROOT / "codex_sandbox" / "AGENTS.md").read_text(encoding="utf-8")
