import copy
import hashlib
import json
import threading
import time
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from . import catalog, experience, labs, settings, store
from .engine import ROLES, agent_workflow, graph_for, roles_in, simulate
from .extensions import install as install_extensions
from .factory.api import install as install_factory
from .studio import install


@asynccontextmanager
async def lifespan(app):
    store.initialize()
    store.recover_interrupted_jobs()
    try:
        yield
    finally:
        from . import codex_login
        codex_login.shutdown()


app = FastAPI(title="SimForge-AI", version="2.0.0", lifespan=lifespan)
if not settings.PRODUCTION:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-SimForge-Request"],
    )


@app.middleware("http")
async def protect_requests(request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if request.headers.get("x-simforge-request") != "1":
            return Response("Missing same-origin request header", status_code=403)
        try:
            length = int(request.headers.get("content-length", "0") or "0")
        except ValueError:
            return Response("Invalid Content-Length", status_code=400)
        if length < 0:
            return Response("Invalid Content-Length", status_code=400)
        if length > 1_000_000:
            return Response("Request too large", status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def safe_validation(request: Request, exc: RequestValidationError):
    if request.url.path == "/api/authoring/openai/config":
        return JSONResponse(status_code=422, content={"detail": "Invalid API connection settings"})
    from fastapi.exception_handlers import request_validation_exception_handler
    return await request_validation_exception_handler(request, exc)


def user(request: Request):
    current = store.session_user(request.cookies.get("simforge_session", ""))
    if not current:
        raise HTTPException(401, "Sign in to continue")
    return current


def admin(current=Depends(user)):
    if current["role"] != "admin":
        raise HTTPException(403, "Only administrators can create or publish scenarios")
    return current


def resource(rid, kind, current):
    row = store.get(rid, kind)
    if not row or (row["owner"] != current["id"] and current["role"] != "admin"):
        raise HTTPException(404, "Resource not found")
    return row


def scenarios():
    return catalog.all_scenarios([r["payload"] for r in store.list_resources("scenario")])


def scenario(key):
    found = next((s for s in scenarios() if s["key"] == key), None)
    if not found:
        raise HTTPException(404, "Scenario not found")
    return found


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


@app.get("/api/health")
def health():
    return dict(
        status="ok",
        name="SimForge-AI",
        engine="SimPy + NetworkX",
        database="SQLite",
        cpu_only=True,
        mode="production" if settings.PRODUCTION else "development",
    )


@app.post("/api/auth/login")
def login(body: Login, request: Request, response: Response):
    token = store.authenticate(
        body.username, body.password, request.client.host if request.client else "local"
    )
    if token == "limited":
        raise HTTPException(429, "Too many sign-in attempts; wait one minute")
    if not token:
        raise HTTPException(401, "Incorrect username or password")
    response.set_cookie(
        "simforge_session",
        token,
        httponly=True,
        samesite="strict",
        secure=settings.PRODUCTION,
        max_age=28800,
    )
    current = store.session_user(token)
    store.audit(current["id"], "login", "Session started")
    return current


@app.get("/api/auth/me")
def me(current=Depends(user)):
    return current


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    with store.connection() as db:
        db.execute(
            "DELETE FROM sessions WHERE token=?",
            (hashlib.sha256(request.cookies.get("simforge_session", "").encode()).hexdigest(),),
        )
    response.delete_cookie("simforge_session")
    return {"ok": True}


class NewUser(BaseModel):
    username: str = Field(pattern=r"^[a-zA-Z0-9_-]{3,40}$")
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=14, max_length=256)
    role: Literal["learner", "admin"] = "learner"


@app.post("/api/users")
def add_user(body: NewUser, current=Depends(admin)):
    if current["role"] != "admin":
        raise HTTPException(403, "Administrator role required")
    with store.connection() as db:
        if db.execute("SELECT 1 FROM users WHERE id=?", (body.username,)).fetchone():
            raise HTTPException(409, "Username already exists")
        db.execute(
            "INSERT INTO users VALUES(?,?,?,?)",
            (body.username, body.name, body.role, store.password_hash(body.password)),
        )
    store.audit(current["id"], "user.create", body.username)
    return {"id": body.username, "role": body.role}


@app.get("/api/scenarios")
def get_scenarios(current=Depends(user)):
    return [catalog.public_scenario(s) for s in scenarios()]


@app.get("/api/overview")
def overview(current=Depends(user)):
    items = scenarios()
    runs = store.list_resources("run", current)
    datasets = store.list_resources("dataset", current)
    return dict(
        scenarios=len(items),
        worlds=sum(s["kind"] == "world" for s in items),
        training=sum(s["kind"] == "training" for s in items),
        runs=len(runs),
        datasets=len(datasets),
        recent_runs=[run_summary(r) for r in runs[:6]],
    )


class StartRun(BaseModel):
    scenario_key: str = ""
    preparation_id: str | None = None
    seed: int = Field(default=2026, ge=0, le=2147483647)
    population: int = Field(default=300, ge=20, le=settings.MAX_POPULATION)
    horizon: int = Field(default=45, ge=20, le=settings.MAX_HORIZON)


def run_summary(row):
    p = row["payload"]
    return dict(
        id=row["id"],
        title=p["spec"]["title"],
        tick=p["tick"],
        horizon=p["horizon"],
        seed=p["seed"],
        population=p["population"],
        created=row["created"],
        status="completed"
        if p["tick"] >= p["horizon"]
        else ("running" if p.get("clock", {}).get("running") else "paused"),
        owner=row["owner"],
    )


def simulation(p, decisions=None):
    return simulate(
        p["spec"],
        p["seed"],
        p["population"],
        p["tick"],
        p["decisions"] if decisions is None else decisions,
        p.get("work_items"),
    )


def clock_tick(row):
    p = row["payload"]
    clock = p.get("clock", {})
    if clock.get("running"):
        elapsed = max(0, time.time() - clock["started_at"])
        p["tick"] = min(
            p["horizon"], max(p["tick"], clock["started_tick"] + int(elapsed * clock["speed"]))
        )
        if p["tick"] >= p["horizon"]:
            clock["running"] = False


def sync_clock(row):
    for _ in range(3):
        before = row["payload"]["tick"]
        clock_tick(row)
        if before == row["payload"]["tick"]:
            return row
        if store.update(row["id"], row["payload"], row["version"]):
            return store.get(row["id"], "run")
        row = store.get(row["id"], "run")
    raise HTTPException(409, "Run changed during playback; refresh")


def writable_run(rid, current):
    row = resource(rid, "run", current)
    if row["owner"] != current["id"]:
        raise HTTPException(
            403, "Observers can view learner runs but cannot make their decisions"
        )
    return row


def run_view(row, role="operations"):
    p = row["payload"]
    result = simulation(p)
    complete = p["tick"] >= p["horizon"]
    if not complete:
        result.pop("ground_truth", None)
    result["events"] = [e for e in result["events"] if complete or e["role"] in {role, "all"}]
    result.update(
        run_summary(row),
        role=role,
        decisions=p["decisions"],
        actions=p["spec"]["actions"],
        unit=p["spec"]["unit"],
        version=row["version"],
        clock=p.get("clock", {"running": False, "speed": 1}),
        preparation_id=p.get("preparation_id"),
        briefing=p.get("briefing") or experience.briefing(p["spec"]),
        environment_style=p["spec"].get("environment_style", "workflow"),
        live=experience.live_summary(result),
        perspectives=[dict(id=r, label=ROLES[r]) for r in roles_in(p["spec"])],
    )
    return result


@app.post("/api/runs")
def start_run(body: StartRun, current=Depends(user)):
    if body.preparation_id:
        prepared = resource(body.preparation_id, "preparation", current)
        # Learners use their own frozen environment, even when a trainer assigns the same scenario.
        if prepared["owner"] != current["id"]:
            raise HTTPException(403, "Generate your own environment before starting a run")
        data = prepared["payload"]
    else:
        source = scenario(body.scenario_key)
        with generation_lock:
            data = experience.prepare(source, body.seed, body.population, body.horizon)
        pid = store.create("preparation", current["id"], data)
        prepared = store.get(pid)
    spec = data["spec"]
    payload = dict(
        spec=spec,
        seed=data["seed"],
        population=data["population"],
        horizon=data["horizon"],
        tick=0,
        decisions=[],
        engine_version=2,
        preparation_id=prepared["id"],
        work_items=data["tables"]["work_items"],
        briefing=experience.briefing(data["original"]),
        clock={"running": False, "speed": 1},
    )
    rid = store.create("run", current["id"], payload)
    store.audit(current["id"], "run.create", spec["title"])
    return run_view(store.get(rid))


@app.get("/api/runs")
def runs(current=Depends(user)):
    return [run_summary(sync_clock(r)) for r in store.list_resources("run", current)]


@app.get("/api/runs/{rid}")
def get_run(
    rid: str,
    role: str = "operations",
    current=Depends(user),
):
    if role not in ROLES:
        raise HTTPException(400, "Unknown specialist perspective")
    return run_view(sync_clock(resource(rid, "run", current)), role)


class Advance(BaseModel):
    ticks: int = Field(default=5, ge=1, le=30)
    version: int
    role: str = "operations"


def save_run(row, current, action):
    if not store.update(row["id"], row["payload"], row["version"]):
        raise HTTPException(409, "This run changed in another tab. Refresh and retry.")
    store.audit(current["id"], action, row["id"])


@app.post("/api/runs/{rid}/advance")
def advance(rid: str, body: Advance, current=Depends(user)):
    row = writable_run(rid, current)
    if row["version"] != body.version:
        raise HTTPException(409, "Refresh this run before advancing")
    p = row["payload"]
    clock_tick(row)
    p.setdefault("clock", {})["running"] = False
    p["tick"] = min(p["horizon"], p["tick"] + body.ticks)
    save_run(row, current, "run.advance")
    return run_view(store.get(rid), body.role)


class Decision(BaseModel):
    action_id: str
    version: int
    role: str = "operations"


@app.post("/api/runs/{rid}/decisions")
def decide(rid: str, body: Decision, current=Depends(user)):
    row = writable_run(rid, current)
    p = row["payload"]
    if row["version"] != body.version:
        raise HTTPException(409, "Refresh this run before deciding")
    clock_tick(row)
    p.setdefault("clock", {})["running"] = False
    if p["tick"] >= p["horizon"]:
        raise HTTPException(400, "Run is complete; fork it to try another decision")
    a = next((a for a in p["spec"]["actions"] if a["id"] == body.action_id), None)
    if not a:
        raise HTTPException(400, "Unknown action")
    if any(d["action_id"] == a["id"] for d in p["decisions"]):
        raise HTTPException(409, "Each response action can be committed once per run")
    costs = {a["id"]: a["cost"] for a in p["spec"]["actions"]}
    if sum(costs[d["action_id"]] for d in p["decisions"]) + a["cost"] > p["spec"].get(
        "budget", 10000
    ):
        raise HTTPException(400, "Response budget would be exceeded")
    p["decisions"].append(dict(action_id=a["id"], tick=p["tick"]))
    save_run(row, current, "run.decision")
    return run_view(store.get(rid), body.role)


@app.post("/api/runs/{rid}/agents")
def agents(rid: str, current=Depends(user)):
    row = resource(rid, "run", current)
    p = row["payload"]
    result = simulation(p)
    store.audit(current["id"], "agents.propose", rid)
    return [agent_workflow(p["spec"], result, role) for role in roles_in(p["spec"])]


@app.post("/api/runs/{rid}/fork")
def fork_run(rid: str, current=Depends(user)):
    row = resource(rid, "run", current)
    payload = copy.deepcopy(row["payload"])
    payload.update(tick=0, decisions=[], parent=rid, clock={"running": False, "speed": 1})
    new_id = store.create("run", current["id"], payload)
    return run_view(store.get(new_id))


@app.get("/api/runs/{rid}/report")
def report(rid: str, current=Depends(user)):
    row = resource(rid, "run", current)
    p = row["payload"]
    if p["tick"] < p["horizon"]:
        raise HTTPException(400, "Complete the run to reveal the debrief and baseline comparison")
    result = run_view(row)
    baseline = simulation(p, [])
    result["baseline"] = baseline["metrics"]
    result["comparison"] = {
        "loss_avoided": round(baseline["metrics"]["loss"] - result["metrics"]["loss"], 2),
        "net_benefit": round(
            baseline["metrics"]["loss"] - result["metrics"]["loss"] - result["metrics"]["spent"], 2
        ),
        "score_change": round(result["metrics"]["score"] - baseline["metrics"]["score"], 1),
    }
    result["note"] = (
        "Illustrative synthetic units, not forecasts or real financial/safety advice. Baseline uses the identical seed, population and horizon with no decisions."
    )
    return result


@app.get("/api/runs/{rid}/export")
def export_run(rid: str, current=Depends(user)):
    result = report(rid, current)
    return Response(
        json.dumps(result, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="simforge-{rid}.json"'},
    )


class Generate(BaseModel):
    scenario_key: str
    seed: int = Field(default=2026, ge=0, le=2147483647)
    scale: int = Field(default=1, ge=1, le=3)


generation_lock = threading.Lock()


@app.post("/api/datasets")
def generate(body: Generate, current=Depends(user)):
    spec = scenario(body.scenario_key)
    if spec["kind"] != "training":
        raise HTTPException(400, "Choose a training scenario")
    # The preserved Faker generator uses a class-level seed.
    with generation_lock:
        bundle = catalog.legacy_generator().generate_bundle(spec, body.seed, body.scale)
    rid = store.create(
        "dataset",
        current["id"],
        dict(title=spec["title"], scenario=spec, bundle=bundle, assessments=[]),
    )
    store.audit(current["id"], "dataset.generate", rid)
    return dataset_view(store.get(rid))


def dataset_view(row):
    p = row["payload"]
    return dict(
        id=row["id"],
        title=p["title"],
        scenario=catalog.public_scenario(p["scenario"]),
        tables={k: len(v) for k, v in p["bundle"].items() if isinstance(v, list)},
        quality=labs.dataset_quality(p["bundle"]),
        assessments=p["assessments"],
        meta=p["bundle"].get("meta", {}),
    )


@app.get("/api/datasets")
def datasets(current=Depends(user)):
    return [dataset_view(r) for r in store.list_resources("dataset", current)]


@app.get("/api/datasets/{rid}")
def dataset(rid: str, current=Depends(user)):
    return dataset_view(resource(rid, "dataset", current))


@app.get("/api/datasets/{rid}/tables/{table}")
def table(rid: str, table: str, offset: int = 0, limit: int = 100, current=Depends(user)):
    rows = resource(rid, "dataset", current)["payload"]["bundle"].get(table)
    if not isinstance(rows, list):
        raise HTTPException(404, "Table not found")
    offset = max(0, offset)
    return dict(rows=rows[offset : offset + max(1, min(limit, 200))], total=len(rows))


@app.get("/api/datasets/{rid}/export")
def export_dataset(rid: str, current=Depends(user)):
    bundle = resource(rid, "dataset", current)["payload"]["bundle"]
    return Response(
        labs.bundle_zip(bundle),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="dataset-{rid}.zip"'},
    )


class Assessment(BaseModel):
    root_cause: str = Field(max_length=500)
    evidence: list[str] = Field(default_factory=list, max_length=20)
    recommendation: str = Field(min_length=1, max_length=3000)


@app.post("/api/datasets/{rid}/assess")
def assess(rid: str, body: Assessment, current=Depends(user)):
    row = resource(rid, "dataset", current)
    spec = row["payload"]["scenario"]
    expected = {e.lower() for e in spec["evidence"]}
    root = 55 if body.root_cause == spec["root_cause"] else 0
    evidence = (
        25 * len({e.lower().strip() for e in body.evidence} & expected) / max(1, len(expected))
    )
    recommendation = min(
        20,
        5 * sum(k.lower() in body.recommendation.lower() for k in spec["recommendation_keywords"]),
    )
    result = dict(
        score=round(root + evidence + recommendation, 1),
        root=root,
        evidence=round(evidence, 1),
        recommendation=recommendation,
        expected_root=spec["root_cause"],
        expected_evidence=spec["evidence"],
        note="Training rubric uses exact root selection, evidence labels and recommendation keywords; not a measure of professional competency.",
    )
    row["payload"]["assessments"].append(result)
    if not store.update(rid, row["payload"], row["version"]):
        raise HTTPException(409, "Dataset changed; retry assessment")
    store.audit(current["id"], "training.assess", rid)
    return result


class Synth(BaseModel):
    csv: str = Field(min_length=4, max_length=250000)
    rows: int = Field(default=100, ge=1, le=2000)
    seed: int = 2026
    method: Literal["independent", "bootstrap"] = "independent"


@app.post("/api/synthesis")
def synthesis(body: Synth, current=Depends(admin)):
    try:
        result = labs.synthesize(body.csv, body.rows, body.seed, body.method)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    store.audit(
        current["id"], "synthesis.run", f"{body.rows} rows; {body.method}; source not persisted"
    )
    return result


class Connector(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    type: Literal["file", "sqlite"]


@app.get("/api/connectors")
def connectors(current=Depends(admin)):
    return [dict(id=r["id"], **r["payload"]) for r in store.list_resources("connector", current)]


@app.post("/api/connectors")
def connector(body: Connector, current=Depends(admin)):
    rid = store.create("connector", current["id"], body.model_dump())
    return dict(id=rid, **body.model_dump())


@app.post("/api/connectors/{cid}/push/{rid}")
def push(cid: str, rid: str, current=Depends(admin)):
    profile = resource(cid, "connector", current)["payload"]
    bundle = resource(rid, "dataset", current)["payload"]["bundle"]
    result = labs.push_local(profile, bundle, cid + "-" + rid)
    store.audit(current["id"], "connector.push", json.dumps(result))
    return result


class WorldNode(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,29}$")
    label: str = Field(min_length=2, max_length=60)
    role: Literal[
        "investigator",
        "operations",
        "finance",
        "security",
        "safety",
        "engineering",
        "medical",
        "legal",
        "emergency",
        "executive",
    ] = "operations"
    capacity: int = Field(default=5, ge=1, le=30)


class Edge(BaseModel):
    source: str
    target: str


class WorldDraft(BaseModel):
    model_config = {"extra": "forbid"}
    title: str = Field(min_length=4, max_length=80)
    summary: str = Field(min_length=10, max_length=800)
    nodes: list[WorldNode] = Field(min_length=3, max_length=12)
    edges: list[Edge] = Field(min_length=2, max_length=30)
    incident_node: str
    cause: str = Field(min_length=10, max_length=500)
    unit: str = Field(default="tasks", pattern=r"^[a-zA-Z]{2,20}$")
    environment_style: Literal["workflow", "voxel", "service_app"] = "workflow"
    learner_role: str = Field(default="Incident coordinator", min_length=3, max_length=100)
    mission: str = Field(
        default="Investigate linked records, recover the workflow and explain the outcome.",
        min_length=10,
        max_length=800,
    )
    success: str = Field(
        default="Restore service within the budget and explain your decision using evidence.",
        min_length=10,
        max_length=500,
    )

    @model_validator(mode="after")
    def validate_graph(self):
        ids = [n.id for n in self.nodes]
        if len(ids) != len(set(ids)) or self.incident_node not in ids:
            raise ValueError("Nodes must be unique and include the incident node")
        if any(e.source not in ids or e.target not in ids for e in self.edges):
            raise ValueError("Every edge must reference an existing node")
        g = graph_for(
            dict(
                nodes=[n.model_dump() for n in self.nodes],
                edges=[e.model_dump() for e in self.edges],
            )
        )
        import networkx as nx

        if not nx.is_weakly_connected(g):
            raise ValueError("Every node must be connected to the workflow")
        return self


@app.post("/api/scenarios")
def create_world(body: WorldDraft, current=Depends(admin)):
    from .studio import publish_direct

    return publish_direct(body, current)


def spec_from_draft(body):
    root = body.incident_node
    downstream = next((n.id for n in body.nodes if n.id != root), root)
    spec = catalog.world(
        "draft",
        "",
        "Custom Worlds",
        body.summary,
        [(n.id, n.label, n.role, n.capacity) for n in body.nodes],
        [(e.source, e.target) for e in body.edges],
        root,
        body.cause,
        body.unit,
        [
            ("repair", "Repair the source", root, "repair", 2200, 4, "Restore source processing."),
            (
                "inspect",
                "Investigate source signals",
                root,
                "inspect",
                200,
                0,
                "Gather incident evidence.",
            ),
            (
                "reroute",
                "Open an alternate route",
                downstream,
                "reroute",
                1500,
                2,
                "Decouple a dependent system.",
            ),
        ],
    )
    spec["title"] = body.title
    spec["key"] = "candidate"
    spec["environment_style"] = body.environment_style
    spec["learning"] = dict(role=body.learner_role, mission=body.mission, success=body.success)
    spec["objective"] = body.mission
    spec["decoys"] = ["An unrelated demand spike", "A scheduled maintenance activity"]
    return spec


@app.get("/api/audit")
def audit_log(current=Depends(admin)):
    with store.connection() as db:
        return [dict(r) for r in db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 100")]


install(app, user, admin, resource, scenario, WorldDraft)
install_extensions(app, user, admin, resource, scenario)
install_factory(app, user, admin, resource)

# npm build produces static assets; one Uvicorn process can serve both API and React.
frontend = settings.ROOT / "frontend/dist"
if (frontend / "assets").exists():
    app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith("api/"):
        raise HTTPException(404, "API endpoint not found")
    if (frontend / "index.html").exists():
        return FileResponse(frontend / "index.html")
    return {
        "message": "SimForge-AI API is ready. Run npm install and npm run dev in frontend, or npm run build for single-server mode.",
        "docs": "/docs",
    }
