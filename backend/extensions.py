"""Investigation, data and ML-lab endpoints layered on the core studio API.

Installed from main.py with the same role dependencies: learners play and investigate,
administrators additionally configure custom labs and publish new scenarios.
"""

import csv
import io
import json
import random
import threading
import time
import zipfile
from typing import Literal

import networkx as nx
from fastapi import Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import catalog, codex_sandbox, connections, datasets, evidence, experience, learning_paths, packs, store, vision
from .engine import agent_workflow, commander_workflow, roles_in, unnecessary_actions
from .mllab import catalog as ml_catalog
from .mllab import lab as ml


def _csv(rows):
    out = io.StringIO(newline="")
    if not rows:
        return ""
    fields = list(dict.fromkeys(k for r in rows for k in r))
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for r in rows:
        writer.writerow({k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in r.items()})
    return out.getvalue()


class Diagnosis(BaseModel):
    root_node: str = Field(min_length=1, max_length=40)
    cause: str = Field(min_length=3, max_length=600)
    version: int


class Handoff(BaseModel):
    target: str = Field(min_length=3, max_length=80)
    signal: str = Field(min_length=2, max_length=60)


class Schema(BaseModel):
    dataset: dict


class SaveDataset(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    dataset: dict
    scenario_key: str | None = None


class NewLab(BaseModel):
    scenario_key: str | None = None
    profile: str | None = None
    failures: list[str] | None = Field(default=None, max_length=5)
    count: int | None = Field(default=None, ge=1, le=5)
    seed: int = Field(default=2026, ge=0, le=2147483647)


class LabFix(BaseModel):
    fix: str = Field(min_length=3, max_length=40)
    feature: str | None = Field(default=None, max_length=60)


class SandboxRequest(BaseModel):
    answers: dict
    mode: Literal["auto", "codex", "guided"] = "auto"


class LabSubmission(BaseModel):
    failures: list[str] = Field(default_factory=list, max_length=8)
    fixes: list[LabFix] = Field(default_factory=list, max_length=10)
    ring: list[str] = Field(default_factory=list, max_length=20)
    notes: str = Field(default="", max_length=2000)


LAB_LOCK = threading.RLock()


def install(app, user, admin, resource, scenario):
    from . import main

    # ------------------------------------------------------------------ run investigation
    def run_state(rid, current):
        row = main.sync_clock(resource(rid, "run", current))
        p = row["payload"]
        return row, p, main.simulation(p), p["tick"] >= p["horizon"]

    @app.get("/api/runs/{rid}/evidence")
    def run_evidence(rid: str, role: str = "operations", current=Depends(user)):
        row, p, result, complete = run_state(rid, current)
        items = evidence.build(p["spec"], result, p["seed"], rid, complete)
        return dict(items=evidence.public(items, role, complete), complete=complete, role=role)

    @app.get("/api/runs/{rid}/evidence/{eid}/{name}")
    def evidence_media(rid: str, eid: str, name: Literal["image.png", "clip.gif"], current=Depends(user)):
        row, p, result, complete = run_state(rid, current)
        media = evidence.media(evidence.build(p["spec"], result, p["seed"], rid, complete), eid)
        if not media:
            raise HTTPException(404, "No media for this evidence item")
        return Response(media[0], media_type=media[1], headers={"Cache-Control": "private, max-age=600"})

    @app.post("/api/runs/{rid}/commander")
    def council(rid: str, current=Depends(user)):
        row, p, result, _ = run_state(rid, current)
        specialists = [agent_workflow(p["spec"], result, r) for r in roles_in(p["spec"])]
        store.audit(current["id"], "commander.propose", rid)
        return dict(specialists=specialists, commander=commander_workflow(p["spec"], result, specialists, p["decisions"]))

    def diagnosis_options(rid, p):
        causes = [p["spec"]["incident"]["cause"]] + list(p["spec"].get("decoys", []))[:4]
        random.Random(rid).shuffle(causes)
        return dict(nodes=[dict(id=n["id"], label=n["label"]) for n in p["spec"]["nodes"]], causes=causes)

    @app.get("/api/runs/{rid}/diagnosis")
    def get_diagnosis(rid: str, current=Depends(user)):
        row, p, result, complete = run_state(rid, current)
        return dict(options=diagnosis_options(rid, p), submitted=p.get("diagnosis"))

    @app.post("/api/runs/{rid}/diagnosis")
    def submit_diagnosis(rid: str, body: Diagnosis, current=Depends(user)):
        row = main.writable_run(rid, current)
        if row["version"] != body.version:
            raise HTTPException(409, "Refresh this run before submitting a diagnosis")
        p = row["payload"]
        options = diagnosis_options(rid, p)
        if body.root_node not in {n["id"] for n in options["nodes"]} or body.cause not in options["causes"]:
            raise HTTPException(400, "Choose one of the listed systems and explanations")
        main.clock_tick(row)
        if p["tick"] >= p["horizon"]:
            raise HTTPException(409, "Diagnosis is closed after completion; use a fresh exercise to practise")
        p["diagnosis"] = dict(root_node=body.root_node, cause=body.cause, tick=p["tick"])
        main.save_run(row, current, "run.diagnosis")
        return main.run_view(store.get(rid))

    @app.get("/api/runs/{rid}/scorecard")
    def scorecard(rid: str, current=Depends(user)):
        row, p, result, complete = run_state(rid, current)
        if not complete:
            raise HTTPException(400, "Complete the run to reveal the scorecard")
        spec = p["spec"]
        baseline = main.simulation(p, [])
        diag = p.get("diagnosis") or {}
        root_ok = diag.get("root_node") == spec["incident"]["node"]
        cause_ok = diag.get("cause") == spec["incident"]["cause"]
        wasted = unnecessary_actions(spec, p["decisions"], baseline)
        onset = spec["incident"]["tick"]
        sc = result["scorecard"]
        with store.connection() as db:
            council_uses = db.execute(
                "SELECT COUNT(*) FROM audit WHERE detail=? AND action IN ('agents.propose','commander.propose')", (rid,)
            ).fetchone()[0]
        base_loss = max(1e-9, baseline["metrics"]["loss"])
        dims = dict(
            business_impact=max(0.0, min(100.0, 100 * (base_loss - result["metrics"]["loss"]) / base_loss)),
            detection_speed=100.0 if sc["detection_delay"] is not None and sc["detection_delay"] <= 5 else max(0.0, 100 - 5 * (sc["detection_delay"] if sc["detection_delay"] is not None else 20)),
            root_cause_accuracy=50.0 * root_ok + 50.0 * cause_ok,
            recovery_time=100.0 if sc["recovered_at"] is None and sc["min_service"] >= 85 else (max(0.0, 100 - 3 * (sc["recovered_at"] - onset)) if sc["recovered_at"] else 0.0),
            cost_efficiency=max(0.0, 100 * (1 - result["metrics"]["spent"] / max(1, result["metrics"]["budget"]))),
            sla_impact=max(0.0, min(100.0, 100 - 100 * result["metrics"]["late"] / max(1, baseline["metrics"]["late"] or 1))),
            collaboration=min(100.0, 50.0 * council_uses),
            necessary_actions=max(0.0, 100 - 34 * len(wasted)),
        )
        weights = dict(business_impact=0.25, detection_speed=0.1, root_cause_accuracy=0.2, recovery_time=0.1, cost_efficiency=0.1, sla_impact=0.1, collaboration=0.05, necessary_actions=0.1)
        return dict(
            overall=round(sum(dims[k] * w for k, w in weights.items()), 1),
            dimensions={k: round(v, 1) for k, v in dims.items()},
            weights=weights,
            diagnosis=dict(submitted=diag, root_correct=root_ok, cause_correct=cause_ok),
            unnecessary_actions=wasted,
            scorecard=sc,
            baseline_scorecard=baseline["scorecard"],
            ground_truth=result["ground_truth"],
        )

    # ------------------------------------------------------------------ connections
    def lab_nodes():
        return [
            dict(key=f"lab:{s['key']}", title=s["title"], kind="lab", category="ML Failure Lab", consumes=s.get("consumes", []))
            for s in ml_catalog.scenarios()
            if s.get("consumes")
        ]

    @app.get("/api/scenario-graph")
    def scenario_graph(current=Depends(user)):
        worlds = [s for s in main.scenarios() if s["kind"] == "world"]
        graph = connections.scenario_graph(worlds + lab_nodes())
        return dict(graph, shared_entities=connections.references(worlds))

    @app.get("/api/shared-entities")
    def shared_entities(current=Depends(user)):
        worlds = [s for s in main.scenarios() if s["kind"] == "world"]
        return dict(registry=connections.registry(), references=connections.references(worlds))

    @app.get("/api/runs/{rid}/signals")
    def run_signals(rid: str, current=Depends(user)):
        row, p, result, complete = run_state(rid, current)
        active = connections.active_signals(p["spec"], result)
        names = {a["signal"] for a in active}
        targets = [
            dict(key=s["key"], title=s["title"], kind=s["kind"], signal=sig)
            for s in [x for x in main.scenarios() if x["kind"] == "world"] + lab_nodes()
            for sig in s.get("consumes", [])
            if sig in names and s["key"] != p["spec"]["key"]
        ]
        return dict(active=active, targets=targets)

    @app.post("/api/runs/{rid}/handoff")
    def handoff(rid: str, body: Handoff, current=Depends(user)):
        row, p, result, complete = run_state(rid, current)
        signal = next((a for a in connections.active_signals(p["spec"], result) if a["signal"] == body.signal), None)
        if not signal:
            raise HTTPException(400, "That signal is not active in this run")
        if body.target.startswith("lab:"):
            key = body.target[4:]
            lab_scen = next((s for s in ml_catalog.scenarios() if s["key"] == key), None)
            if not lab_scen or body.signal not in lab_scen.get("consumes", []):
                raise HTTPException(400, "That lab does not consume this signal")
            cfg = ml.create_config(key, seed=p["seed"], handoff=dict(signal=body.signal, from_run=rid, intensity=signal["intensity"]))
            lid = store.create("ml_lab", current["id"], dict(
                config=cfg, probes=[], submission=None, created=time.time(),
                learning_check=learning_paths.initial_state()))
            store.audit(current["id"], "handoff.lab", f"{rid}->{lid}")
            return dict(kind="lab", id=lid)
        target = scenario(body.target)
        if body.signal not in target.get("consumes", []):
            raise HTTPException(400, "That scenario does not consume this signal")
        spec = connections.handoff_spec(target, signal)
        with main.generation_lock:
            data = experience.prepare(spec, p["seed"], p["population"], p["horizon"])
        pid = store.create("preparation", current["id"], data)
        payload = dict(
            spec=data["spec"], seed=data["seed"], population=data["population"], horizon=data["horizon"],
            tick=0, decisions=[], engine_version=2, preparation_id=pid, work_items=data["tables"]["work_items"],
            briefing=experience.briefing(data["original"]), clock={"running": False, "speed": 1}, parent=rid,
            handoff=dict(from_run=rid, signal=body.signal, intensity=signal["intensity"]),
        )
        new_id = store.create("run", current["id"], payload)
        store.audit(current["id"], "handoff.run", f"{rid}->{new_id}")
        return dict(kind="run", id=new_id)

    # ------------------------------------------------------------------ run dataset bundle
    @app.get("/api/runs/{rid}/bundle")
    def bundle(rid: str, current=Depends(user)):
        row, p, result, complete = run_state(rid, current)
        spec = p["spec"]
        items = evidence.build(spec, result, p["seed"], rid, complete)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("entities.csv", _csv(result["entities"]))
            z.writestr("events.csv", _csv([e for e in result["events"]]))
            telemetry = [dict(tick=h["tick"], system=k, health=v, service=h["service"], queued=h.get("queues", {}).get(k)) for h in result["history"] for k, v in h["health"].items()]
            z.writestr("telemetry.csv", _csv(telemetry))
            transactions = [dict(r, evidence=i["id"]) for i in items if i["modality"] == "transaction" for r in i["content"]["rows"]]
            z.writestr("transactions.csv", _csv(transactions))
            relationships = [dict(source=e["source"], target=e["target"], relation="depends_on") for e in spec["edges"]]
            relationships += [dict(source=e["source"], target=e["target"], relation=e["type"]) for i in items if i["modality"] == "graph" for e in i["content"]["edges"]]
            z.writestr("relationships.csv", _csv(relationships))
            messages = [dict(id=i["id"], tick=i["tick"], modality=i["modality"], system=i["node"], **{k: v for k, v in i["content"].items() if not k.startswith("_")}) for i in items if i["modality"] in {"email", "chat", "ticket"}]
            z.writestr("messages.jsonl", "\n".join(json.dumps(m, default=str) for m in messages))
            logs = [dict(evidence=i["id"], system=i["node"], line=line) for i in items if i["modality"] == "log" for line in i["content"]["lines"]]
            z.writestr("logs.jsonl", "\n".join(json.dumps(x) for x in logs))
            for i in items:
                if i["modality"] == "document":
                    z.writestr(f"documents/{i['id']}.md", f"# {i['content']['title']}\n\n" + "\n\n".join(i["content"]["paragraphs"]) + "\n")
                if i["modality"] == "image":
                    media = evidence.media(items, i["id"])
                    if media:
                        z.writestr(f"images/{i['id']}.png", media[0])
            graph = nx.DiGraph()
            for n in spec["nodes"]:
                graph.add_node(n["id"], label=n["label"], role=n["role"], capacity=n["capacity"], modality=n.get("modality", "log"))
            for e in spec["edges"]:
                graph.add_edge(e["source"], e["target"])
            gml = io.BytesIO()
            nx.write_graphml(graph, gml)
            z.writestr("world_graph.graphml", gml.getvalue())
            z.writestr("decisions.jsonl", "\n".join(json.dumps(d) for d in p["decisions"]))
            if complete:
                z.writestr("ground_truth.json", json.dumps(result["ground_truth"], indent=2))
                hidden = [dict(tick=e["tick"], node=e["node"], kind=e["kind"]) for e in result["events"] if e["kind"] == "incident"]
                hidden += [dict(id=i["id"], tick=i["tick"], node=i["node"], decoy=True, title=i["title"]) for i in items if i.get("decoy")]
                z.writestr("hidden_events.json", json.dumps(dict(incidents=hidden, rules=spec.get("rules", []), extra_incidents=spec.get("incidents_extra", [])), indent=2, default=str))
            z.writestr("README.md", f"# {spec['title']} run bundle\n\nSeed {p['seed']}, minute {p['tick']} of {p['horizon']}. Synthetic data only.\nGround truth and hidden events are included only after the run completes.\n")
        store.audit(current["id"], "run.bundle", rid)
        return Response(buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="run-{rid}-bundle.zip"'})

    # ------------------------------------------------------------------ packs
    @app.get("/api/packs/status")
    def pack_status(current=Depends(admin)):
        builtin, errors = packs.builtin()
        user_specs, user_errors = packs.user_packs()
        return dict(builtin=len(builtin), user=len(user_specs), errors=errors + user_errors, user_dir=str(packs.USER_DIR))

    @app.get("/api/packs/{key}/yaml")
    def pack_yaml(key: str, current=Depends(admin)):
        spec = scenario(key)
        if spec["kind"] != "world":
            raise HTTPException(400, "Only simulation worlds have a pack definition")
        return Response(packs.to_yaml(spec), media_type="text/yaml")

    # ------------------------------------------------------------------ dataset studio
    @app.get("/api/studio/templates")
    def studio_templates(current=Depends(user)):
        return dict(
            templates=[dict(key=k, name=v["name"], description=v["description"], tables=len(v["tables"])) for k, v in datasets.TEMPLATES.items()],
            column_types=datasets.COLUMN_TYPES,
            anomaly_types=datasets.ANOMALY_TYPES,
            shared_kinds=list(connections.SHARED_KINDS),
            image_kinds=vision.KINDS,
            faker_providers=sorted(datasets.FAKER_PROVIDERS),
            limits=dict(tables=datasets.MAX_TABLES, columns=datasets.MAX_COLUMNS, rows=datasets.MAX_ROWS, cells=datasets.MAX_CELLS, images=datasets.MAX_IMAGES),
        )

    @app.get("/api/studio/templates/{key}")
    def studio_template(key: str, current=Depends(user)):
        if key not in datasets.TEMPLATES:
            raise HTTPException(404, "Template not found")
        return datasets.TEMPLATES[key]

    @app.get("/api/studio/recommend/{key}")
    def studio_recommend(key: str, current=Depends(user)):
        spec = scenario(key)
        if spec["kind"] != "world":
            template = datasets.TEMPLATES["retail_crm"]
            return dict(template, name=f"{spec['title']} dataset", guide=dict(what="Training scenarios use the built-in ten-table generator. Start from this editable relational template.", steps=[], tasks=[], column_types=datasets.COLUMN_TYPES, anomaly_types=datasets.ANOMALY_TYPES))
        return datasets.recommend(spec)

    def checked(schema):
        problems = datasets.validate(schema)
        if problems:
            raise HTTPException(422, dict(message="Schema has problems", problems=problems))

    @app.post("/api/studio/validate")
    def studio_validate(body: Schema, current=Depends(user)):
        problems = datasets.validate(body.dataset)
        return dict(valid=not problems, problems=problems)

    @app.post("/api/studio/preview")
    def studio_preview(body: Schema, current=Depends(user)):
        checked(body.dataset)
        full, truth = datasets.generate(body.dataset)
        return dict(
            tables={k: datasets.public_rows(v[:25]) for k, v in full.items()},
            profile=datasets.profile(full),
            ground_truth=dict(anomalies=[{k: v for k, v in a.items() if k != "affected_rows"} | dict(sample_rows=a["affected_rows"][:10]) for a in truth["anomalies"]]),
        )

    @app.post("/api/studio/datasets")
    def studio_save(body: SaveDataset, current=Depends(user)):
        checked(body.dataset)
        rid = store.create("studio_dataset", current["id"], dict(name=body.name, dataset=body.dataset, scenario_key=body.scenario_key, created=time.time()))
        store.audit(current["id"], "studio.save", body.name)
        return dict(id=rid, name=body.name)

    @app.get("/api/studio/datasets")
    def studio_list(current=Depends(user)):
        return [dict(id=r["id"], name=r["payload"]["name"], scenario_key=r["payload"].get("scenario_key"), tables=len(r["payload"]["dataset"]["tables"]), created=r["created"], owner=r["owner"]) for r in store.list_resources("studio_dataset", current)]

    @app.get("/api/studio/datasets/{rid}")
    def studio_get(rid: str, current=Depends(user)):
        row = resource(rid, "studio_dataset", current)
        return dict(id=rid, **row["payload"])

    @app.get("/api/studio/datasets/{rid}/export")
    def studio_export(rid: str, current=Depends(user)):
        row = resource(rid, "studio_dataset", current)
        data = datasets.export_zip(row["payload"]["dataset"])
        store.audit(current["id"], "studio.export", rid)
        return Response(data, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="dataset-{rid}.zip"'})

    @app.get("/api/studio/image")
    def studio_image(kind: str, seed: int = 0, defect: bool = True, lighting: float = 1.0, current=Depends(user)):
        if kind not in vision.KINDS or not 0.3 <= lighting <= 2.0:
            raise HTTPException(400, "Unknown image kind or lighting outside 0.3-2.0")
        img, _ = vision.render(kind, seed, defect, 0.7, lighting)
        return Response(vision.png(img), media_type="image/png")

    # ------------------------------------------------------------------ ML failure lab
    @app.get("/api/mllab/catalog")
    def lab_catalog(current=Depends(user)):
        return dict(
            scenarios=ml_catalog.scenarios(),
            failures=[dict(key=k, **v) for k, v in ml_catalog.FAILURES.items()],
            fixes=[dict(key=k, **v) for k, v in ml_catalog.FIXES.items()],
            profiles=[dict(key=k, title=v["title"], family="classification", group=v["group"]) for k, v in ml_catalog.CLASSIFICATION.items()]
            + [dict(key=k, title=v["title"], family="forecasting", group="Forecasting") for k, v in ml_catalog.FORECASTING.items()],
        )

    def lab_row(rid, current):
        return resource(rid, "ml_lab", current)

    def lab_view(row, current):
        cfg = row["payload"]["config"]
        check = row["payload"].get("learning_check") or {}
        baseline_pending = (row["owner"] == current["id"]
                            and check.get("version") == learning_paths.VERSION
                            and not check.get("before")
                            and not check.get("evidence_started")
                            and not row["payload"].get("submission"))
        if baseline_pending:
            # The starting check stays meaningful even for direct API callers:
            # model monitoring and probe data are unavailable until it is taken
            # or explicitly skipped. Older saved labs keep their old response.
            brief = {k: cfg.get(k) for k in ("scenario", "title", "group", "story", "profile", "family")}
            return dict(id=row["id"], owner=row["owner"], config=brief,
                        probes_used=row["payload"]["probes"], submission=None,
                        baseline_pending=True)
        view = ml.overview(ml.build(cfg), cfg)
        view.update(id=row["id"], probes_used=row["payload"]["probes"], submission=row["payload"]["submission"], agent=row["payload"].get("agent"), owner=row["owner"])
        return view

    @app.post("/api/mllab/labs")
    def lab_create(body: NewLab, current=Depends(user)):
        if (body.failures or body.profile) and current["role"] == "learner":
            raise HTTPException(403, "Learners start catalogue challenges; Admin / Trainer configures custom failure mixes")
        try:
            cfg = ml.create_config(body.scenario_key, body.profile, body.failures, body.count, body.seed)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        with LAB_LOCK:
            rid = store.create("ml_lab", current["id"], dict(
                config=cfg, probes=[], submission=None, created=time.time(),
                learning_check=learning_paths.initial_state()))
            view = lab_view(store.get(rid), current)
        store.audit(current["id"], "mllab.create", cfg["title"])
        return view

    @app.get("/api/mllab/labs")
    def lab_list(current=Depends(user)):
        return [
            dict(id=r["id"], title=r["payload"]["config"]["title"], group=r["payload"]["config"]["group"], family=r["payload"]["config"]["family"], created=r["created"], score=(r["payload"]["submission"] or {}).get("score"), owner=r["owner"])
            for r in store.list_resources("ml_lab", current)
        ]

    @app.get("/api/mllab/labs/{rid}")
    def lab_get(rid: str, current=Depends(user)):
        with LAB_LOCK:
            return lab_view(lab_row(rid, current), current)

    @app.post("/api/mllab/labs/{rid}/probes/{name}")
    def lab_probe(rid: str, name: str, record: bool = True, current=Depends(user)):
        row = lab_row(rid, current)
        cfg = row["payload"]["config"]
        try:
            with LAB_LOCK:
                data = ml.run_probe(ml.build(cfg), name, cfg)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        row = learning_paths.mark_evidence_started(row, current)
        if record and row["owner"] == current["id"] and name not in row["payload"]["probes"] and not row["payload"]["submission"]:
            row["payload"]["probes"].append(name)
            store.update(rid, row["payload"], row["version"])
        return data

    @app.post("/api/mllab/labs/{rid}/submit")
    def lab_submit(rid: str, body: LabSubmission, current=Depends(user)):
        row = lab_row(rid, current)
        if row["owner"] != current["id"]:
            raise HTTPException(403, "Only the learner who started this lab can submit")
        if row["payload"]["submission"]:
            raise HTTPException(409, "Already submitted; start a new lab to try again")
        cfg = row["payload"]["config"]
        diagnosis = dict(body.model_dump(), fixes=[f.model_dump() for f in body.fixes], probes_used=row["payload"]["probes"])
        with LAB_LOCK:
            result = ml.score(ml.build(cfg), cfg, diagnosis)
        row["payload"]["submission"] = dict(result, submitted=diagnosis, at=time.time())
        if not store.update(rid, row["payload"], row["version"]):
            raise HTTPException(409, "Lab changed; refresh and resubmit")
        store.audit(current["id"], "mllab.submit", f"{rid} score {result['score']}")
        return result

    @app.post("/api/mllab/labs/{rid}/agent")
    def lab_agent(rid: str, current=Depends(user)):
        row = lab_row(rid, current)
        cfg = row["payload"]["config"]
        with LAB_LOCK:
            lab = ml.build(cfg)
            agent = ml.auto_investigate(lab, cfg)
            agent_score = ml.score(lab, cfg, dict(failures=agent["failures"], fixes=agent["fixes"], probes_used=agent["probes_used"]))
        # The agent's score is only revealed once the learner has submitted.
        agent["score"] = agent_score["score"] if row["payload"]["submission"] else None
        agent["parts"] = agent_score["parts"] if row["payload"]["submission"] else None
        if not row["payload"]["submission"]:
            agent = dict(agent_name=agent["agent"], probes_run=len(agent["probes_used"]), message="The AI investigator has finished. Its diagnosis is revealed after you submit yours.", agent=agent["agent"])
        row = learning_paths.mark_evidence_started(row, current)
        row["payload"]["agent"] = agent
        store.update(rid, row["payload"], row["version"])
        return agent

    @app.get("/api/mllab/labs/{rid}/ground_truth.json")
    def lab_truth(rid: str, current=Depends(user)):
        row = lab_row(rid, current)
        if not row["payload"]["submission"] and current["role"] == "learner":
            raise HTTPException(403, "Ground truth is revealed after submission")
        cfg = row["payload"]["config"]
        with LAB_LOCK:
            truth = ml.ground_truth(ml.build(cfg), cfg)
        return Response(json.dumps(truth, indent=2), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="ground_truth-{rid}.json"'})

    @app.get("/api/mllab/labs/{rid}/image/{n}")
    def lab_image(rid: str, n: int, current=Depends(user)):
        row = lab_row(rid, current)
        prof = ml_catalog.profile(row["payload"]["config"]["profile"])
        if not prof.get("visual") or not 0 <= n < 24:
            raise HTTPException(404, "No sample images for this lab")
        lighting = 1.45 if n >= 12 and "data_drift" in row["payload"]["config"]["failures"] else 1.0
        img, _ = vision.render(prof["visual"], row["payload"]["config"]["seed"] * 31 + n, n % 3 == 0, 0.7, lighting)
        learning_paths.mark_evidence_started(row, current)
        return Response(vision.png(img), media_type="image/png")

    @app.get("/api/mllab/labs/{rid}/export")
    def lab_export(rid: str, current=Depends(user)):
        row = lab_row(rid, current)
        row = learning_paths.mark_evidence_started(row, current)
        cfg = row["payload"]["config"]
        with LAB_LOCK:
            lab = ml.build(cfg)
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                if lab.family == "classification":
                    pipe = lab.evaluate()["pipe"]
                    feats = [f for f in pipe["features"]]
                    served = lab.served(pipe)
                    train = [dict(day=int(lab.train["day"][i]), segment=lab.train["seg"][i], **{f: float(lab.train["X"][f][i]) for f in feats}, label=int(lab.train["y_obs"][i])) for i in range(len(lab.train["day"]))]
                    prod = [dict(day=int(lab.prod["day"][i]), segment=lab.prod["seg"][i], **{f: float(served[f][i]) for f in feats}) for i in range(len(lab.prod["day"]))]
                    z.writestr("train.csv", _csv(train))
                    z.writestr("production_served.csv", _csv(prod))
                else:
                    rec = lab.recorded(lab.evaluate()["pipe"])
                    rows = [dict(series=s, day=d, recorded_actual=None if rec[s][d] != rec[s][d] else float(rec[s][d]), **{lab.driver: float(lab.data["driver"][s][d])}, event=float(lab.data["event"][d])) for s in lab.data["series"] for d in range(len(lab.data["event"]))]
                    z.writestr("series.csv", _csv(rows))
                z.writestr("README.md", f"# {cfg['title']}\n\nSynthetic ML failure lab export. Labels/actuals are as recorded (they may be wrong). ground_truth.json is available after submission.\n")
                if row["payload"]["submission"]:
                    z.writestr("ground_truth.json", json.dumps(ml.ground_truth(lab, cfg), indent=2))
        return Response(buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="mllab-{rid}.zip"'})

    # ------------------------------------------------------------------ Codex sandbox (admin)
    @app.get("/api/codex/sandbox/guide")
    def sandbox_guide(current=Depends(admin)):
        return codex_sandbox.WIZARD

    @app.post("/api/codex/sandbox/preview")
    def sandbox_preview(body: SandboxRequest, current=Depends(admin)):
        try:
            pack = codex_sandbox.guided_pack(body.answers)
        except (ValueError, TypeError) as e:
            raise HTTPException(400, str(e)) from e
        spec = packs.expand(pack, "guided-builder")
        return dict(pack=pack, yaml=packs.to_yaml(spec), checks=packs.scenario_tests(spec))

    @app.post("/api/codex/sandbox/jobs")
    def sandbox_start(body: SandboxRequest, current=Depends(admin)):
        if body.mode == "guided":
            try:
                codex_sandbox.guided_pack(body.answers)
            except (ValueError, TypeError) as e:
                raise HTTPException(400, str(e)) from e
        rid = codex_sandbox.start(body.answers, body.mode, current["id"])
        store.audit(current["id"], "codex.sandbox", body.answers.get("title", "")[:80])
        return dict(id=rid, status="running")

    @app.get("/api/codex/sandbox/jobs")
    def sandbox_jobs(current=Depends(admin)):
        return [dict(id=r["id"], status=r["payload"]["status"], title=r["payload"]["answers"].get("title"), source=r["payload"].get("source"), created=r["created"]) for r in store.list_resources("sandbox_job", current)]

    @app.get("/api/codex/sandbox/jobs/{rid}")
    def sandbox_job(rid: str, current=Depends(admin)):
        return dict(id=rid, **resource(rid, "sandbox_job", current)["payload"])

    return dict(catalog=catalog)
