"""Data preparation, playback, publication, assignment and notification endpoints."""

import json
import secrets
import time
from typing import Literal

from fastapi import BackgroundTasks, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, SecretStr

from . import authoring, catalog, drafts as draft_store, experience, labs, packs, scenario_policy, store
from . import scenario_lifecycle as lifecycle, scenario_sources as sources


def checks_for(body):
    from .main import spec_from_draft

    spec = spec_from_draft(body)
    return spec, packs.scenario_tests(spec) + scenario_policy.review_checks(spec)


def publish_direct(body, current, draft_row=None):
    body = type(body).model_validate(scenario_policy.clean(body.model_dump()))
    spec, checks = checks_for(body)
    return publish_spec(spec, checks, current, draft_row)


def pack_draft(pack, current_id, source, extra=None):
    """Store a full scenario pack as a draft that only an administrator can publish."""
    spec = packs.expand(pack, source)
    checks = packs.scenario_tests(spec)
    payload = dict(
        definition=dict(title=spec["title"], mission=spec.get("objective") or spec["summary"], category=spec.get("category")),
        pack=pack,
        pack_yaml=packs.to_yaml(spec),
        checks=checks,
        status="draft",
        source=source,
        **(extra or {}),
    )
    return draft_store.save(payload, current_id)


def publish_spec(spec, checks, current, draft_row=None):
    checks = [c for c in checks if c["category"] not in {"privacy", "governance"}] + scenario_policy.review_checks(spec)
    if not all(c["passed"] for c in checks):
        raise HTTPException(
            422, {"message": "Scenario must pass every publish check", "checks": checks}
        )
    sid = secrets.token_hex(12)
    governance = dict(draft_row["payload"].get("governance", {}) if draft_row else {})
    governance["events"] = [e for e in governance.get("events", [])
                            if not (e["stage"] == "Administrator publication approval" and e["status"] == "pending")] + [
        scenario_policy.security_event("Publication privacy and governance recheck"),
        scenario_policy.security_event("Administrator publication approval", actor=current["id"]),
    ]
    spec["key"] = "custom_" + sid
    spec["publication"] = dict(
        status="published", author=current["id"], created=time.time(),
        draft_id=draft_row["id"] if draft_row else None,
        draft_author=draft_row["owner"] if draft_row else current["id"],
        source=draft_row["payload"]["source"] if draft_row else "manual",
        documents=draft_row["payload"].get("documents", []) if draft_row else [],
        governance=governance,
    )
    with store.connection() as db:
        if draft_row:
            latest = db.execute("SELECT payload FROM resources WHERE id=?", (draft_row["id"],)).fetchone()
            if not latest or json.loads(latest[0]).get("archived"):
                raise HTTPException(409, "Archived draft cannot be published")
            payload = dict(
                draft_row["payload"], status="published", scenario_key=spec["key"], checks=checks,
                governance=governance,
            )
            changed = db.execute(
                "UPDATE resources SET payload=?,version=version+1 WHERE id=? AND version=?",
                (json.dumps(payload), draft_row["id"], draft_row["version"]),
            ).rowcount
            if not changed:
                raise HTTPException(409, "Draft changed; refresh before publishing")
        db.execute(
            "INSERT INTO resources(id,kind,owner,payload,created) VALUES(?,?,?,?,?)",
            (sid, "scenario", current["id"], json.dumps(spec), time.time()),
        )
        recipients = [
            r[0] for r in db.execute("SELECT id FROM users WHERE role='learner'")
        ]
        store.notify(
            recipients,
            spec["key"],
            "New simulation available",
            f"{spec['title']} was published. Open the mission and generate your own training environment.",
            db=db,
        )
    store.audit(current["id"], "scenario.publish", spec["title"])
    return catalog.public_scenario(experience.decorate(spec))


class Preparation(BaseModel):
    scenario_key: str
    seed: int = Field(default=2026, ge=0, le=2147483647)
    population: int = Field(default=300, ge=20, le=5000)
    horizon: int = Field(default=45, ge=20, le=120)


class Playback(BaseModel):
    command: Literal["play", "pause"]
    speed: Literal[0.25, 1, 3] = 1
    version: int
    role: str = "operations"


class Assignment(BaseModel):
    scenario_key: str
    learners: list[str] = Field(min_length=1, max_length=100)
    guidance: str = Field(min_length=10, max_length=1500)


class CodexRequest(BaseModel):
    prompt: str = Field(min_length=30, max_length=6000)
    document_ids: list[str] = Field(default_factory=list, max_length=8)


class Cleanup(BaseModel):
    token: str = Field(min_length=64, max_length=64)
    confirmation: Literal["ARCHIVE"]


class ApiConnection(BaseModel):
    api_key: SecretStr | None = None
    model: str = "gpt-4.1-mini"


class CodexLogin(BaseModel):
    method: Literal["browser", "device"] = "browser"


class CodexSettings(BaseModel):
    enabled: bool


class CodexModel(BaseModel):
    model: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.:/-]+$")
    effort: str = Field(min_length=1, max_length=20, pattern=r"^[a-z]+$")


def install(app, user, admin, resource, scenario, draft_model):
    from . import main

    @app.post("/api/preparations")
    def prepare(body: Preparation, current=Depends(user)):
        spec = scenario(body.scenario_key)
        with main.generation_lock:
            payload = experience.prepare(spec, body.seed, body.population, body.horizon)
        rid = store.create("preparation", current["id"], payload)
        store.audit(current["id"], "environment.prepare", rid)
        return experience.prepared_view(store.get(rid))

    @app.get("/api/preparations", name="prepared_environments")
    def prepared_environments(current=Depends(user)):
        return [experience.prepared_view(row) for row in store.list_resources("preparation", current)]

    @app.get("/api/preparations/{rid}")
    def prepared(rid: str, current=Depends(user)):
        return experience.prepared_view(resource(rid, "preparation", current))

    @app.get("/api/preparations/{rid}/tables/{table}")
    def prepared_table(
        rid: str, table: str, offset: int = 0, limit: int = 50, current=Depends(user)
    ):
        tables = resource(rid, "preparation", current)["payload"]["tables"]
        if table not in tables:
            raise HTTPException(404, "Table not found")
        rows = tables[table]
        return {
            "rows": rows[max(0, offset) : max(0, offset) + min(100, max(1, limit))],
            "total": len(rows),
        }

    @app.get("/api/preparations/{rid}/export")
    def export_prepared(rid: str, current=Depends(user)):
        payload = resource(rid, "preparation", current)["payload"]
        bundle = dict(
            payload["tables"],
            meta=dict(
                seed=payload["seed"],
                relationships=payload["relationships"],
                validation=payload["validation"],
            ),
        )
        return Response(
            labs.bundle_zip(bundle),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="environment-{rid}.zip"'},
        )

    @app.post("/api/runs/{rid}/playback")
    def playback(rid: str, body: Playback, current=Depends(user)):
        row = main.writable_run(rid, current)
        if row["version"] != body.version:
            raise HTTPException(409, "Run changed; refresh before controlling playback")
        main.clock_tick(row)
        p = row["payload"]
        p["clock"] = dict(
            running=body.command == "play" and p["tick"] < p["horizon"],
            speed=body.speed,
            started_at=time.time(),
            started_tick=p["tick"],
        )
        main.save_run(row, current, "run." + body.command)
        return main.run_view(store.get(rid), body.role)

    @app.get("/api/runs/{rid}/data/{table}")
    def live_table(
        rid: str,
        table: str,
        offset: int = 0,
        limit: int = 50,
        work_id: str = "",
        current=Depends(user),
    ):
        row = main.sync_clock(resource(rid, "run", current))
        p = row["payload"]
        result = main.simulation(p)
        prepared_row = store.get(p.get("preparation_id", ""), "preparation")
        tables = prepared_row["payload"]["tables"] if prepared_row else {}
        if table == "work_items":
            rows = result["entities"]
        elif table == "live_telemetry":
            rows = [
                dict(
                    observation_id=f"T-{h['tick']}-{node}",
                    tick=h["tick"],
                    system_id=node,
                    health=value,
                    completed=h["completed"],
                    queued=h["queues"][node],
                    processing=h["processing"][node],
                )
                for h in result["history"]
                for node, value in h["health"].items()
            ]
        elif table == "activity_log":
            rows = result["activity"][::-1]
        elif table == "source_events":
            rows = [dict(e, source_system=e["node"]) for e in result["events"][::-1]]
        elif table.startswith("records_") and table in tables:
            by_id = {e["id"]: e for e in result["entities"]}
            rows = []
            for record in tables[table]:
                entity = by_id[record["work_id"]]
                current_index = (
                    entity["planned_path"].index(entity["current_node"])
                    if entity["current_node"]
                    else -1
                )
                step_index = entity["planned_path"].index(record["system_id"])
                done = entity["state"] == "completed" or (current_index > step_index)
                state = (
                    "completed"
                    if done
                    else entity["state"]
                    if entity["current_node"] == record["system_id"]
                    else "awaiting processing"
                )
                health = next(
                    n["health"] for n in result["nodes"] if n["id"] == record["system_id"]
                )
                signal = next(
                    (
                        e["message"]
                        for e in reversed(result["events"])
                        if e["node"] == record["system_id"]
                    ),
                    "No abnormal signal observed",
                )
                rows.append(
                    dict(
                        record,
                        control_status=state,
                        observed_at=p["tick"],
                        system_health=health,
                        latest_source_signal=signal,
                    )
                )
        elif table in tables:
            rows = tables[table]
        else:
            raise HTTPException(404, "Table not found")
        if work_id:
            rows = [r for r in rows if r.get("work_id", r.get("id")) == work_id]
        offset = max(0, offset)
        return {
            "rows": rows[offset : offset + min(100, max(1, limit))],
            "total": len(rows),
            "tick": p["tick"],
            "retention": "Activity log retains the latest 4,000 transitions; workload and telemetry retain the full bounded run.",
        }

    @app.get("/api/notifications")
    def notifications(current=Depends(user)):
        retired = lifecycle.retired_keys()
        with store.connection() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 100",
                    (current["id"],),
                ) if r["scenario_key"] not in retired
            ]

    @app.post("/api/notifications/{nid}/read")
    def mark_read(nid: int, current=Depends(user)):
        with store.connection() as db:
            changed = db.execute(
                "UPDATE notifications SET seen=1 WHERE id=? AND user_id=?", (nid, current["id"])
            ).rowcount
            if not changed:
                raise HTTPException(404, "Notification not found")
        return {"ok": True}

    @app.get("/api/learners")
    def learners(current=Depends(admin)):
        with store.connection() as db:
            return [
                dict(r)
                for r in db.execute("SELECT id,name FROM users WHERE role='learner' ORDER BY name")
            ]

    @app.post("/api/assignments")
    def assign(body: Assignment, current=Depends(admin)):
        spec = scenario(body.scenario_key)
        ids = sorted(set(body.learners))
        with store.connection() as db:
            allowed = {r[0] for r in db.execute("SELECT id FROM users WHERE role='learner'")}
            if not set(ids).issubset(allowed):
                raise HTTPException(400, "Assignments may target learner accounts only")
            rid = secrets.token_hex(12)
            payload = dict(body.model_dump(), title=spec["title"], trainer=current["name"])
            db.execute(
                "INSERT INTO resources(id,kind,owner,payload,created) VALUES(?,?,?,?,?)",
                (rid, "assignment", current["id"], json.dumps(payload), time.time()),
            )
            store.notify(
                ids, spec["key"], "Your trainer assigned an exercise", body.guidance, db=db
            )
        store.audit(current["id"], "exercise.assign", rid)
        return dict(id=rid, **payload)

    @app.get("/api/assignments")
    def assignments(current=Depends(user)):
        retired = lifecycle.retired_keys()
        return [
            dict(id=r["id"], **r["payload"])
            for r in store.list_resources("assignment")
            if r["payload"]["scenario_key"] not in retired and
            (current["role"] == "admin" or current["id"] in r["payload"]["learners"])
        ]

    @app.get("/api/scenario-drafts")
    def drafts(current=Depends(admin)):
        return [draft_store.view(r) for r in store.list_active_resources("scenario_draft")]

    @app.post("/api/scenario-documents")
    def upload_documents(body: sources.Upload, current=Depends(admin)):
        return sources.upload(body, current["id"])

    @app.get("/api/scenario-documents")
    def documents(current=Depends(admin)):
        return [dict(id=r["id"], **r["payload"]) for r in store.list_resources("scenario_document", current)
                if r["owner"] == current["id"]]

    @app.get("/api/scenario-cleanup")
    def cleanup_plan(current=Depends(admin)):
        return lifecycle.plan()

    @app.post("/api/scenario-cleanup")
    def cleanup(body: Cleanup, current=Depends(admin)):
        return lifecycle.archive(body.token, current["id"])

    @app.post("/api/scenario-cleanup/{batch}/restore")
    def restore(batch: str, current=Depends(admin)):
        return lifecycle.restore(batch, current["id"])

    @app.post("/api/scenario-drafts")
    def create_draft(body: draft_model, current=Depends(admin)):
        findings = scenario_policy.privacy_summary(body.model_dump())
        body = draft_model.model_validate(scenario_policy.clean(body.model_dump()))
        _, checks = checks_for(body)
        payload = dict(definition=body.model_dump(), status="draft", checks=checks, source="manual",
                       governance=scenario_policy.draft_governance(findings, checks))
        return draft_store.save(payload, current["id"])

    @app.post("/api/scenario-drafts/{rid}/revise")
    def revise_draft(rid: str, body: draft_model, current=Depends(admin)):
        previous = resource(rid, "scenario_draft", current)
        if previous["payload"].get("archived"):
            raise HTTPException(409, "Restore an archived draft before revising")
        findings = scenario_policy.privacy_summary(body.model_dump())
        body = draft_model.model_validate(scenario_policy.clean(body.model_dump()))
        _, checks = checks_for(body)
        return draft_store.save(dict(
            definition=body.model_dump(), status="draft", checks=checks,
            source=previous["payload"]["source"], revised_from=rid, edited_by=current["id"],
            documents=previous["payload"].get("documents", []),
            governance=scenario_policy.draft_governance(findings, checks, previous["payload"].get("governance")),
        ), current["id"])

    @app.get("/api/authoring/policy")
    def authoring_policy(current=Depends(admin)):
        import hashlib
        prompt = scenario_policy.system_prompt()
        return dict(policy_version=scenario_policy.POLICY_VERSION, system_prompt=prompt,
                    sha256=hashlib.sha256(prompt.encode()).hexdigest())

    @app.get("/api/scenario-examples")
    def examples(current=Depends(admin)):
        from .scenario_examples import catalogue
        return dict(examples=catalogue(), policy_version=scenario_policy.POLICY_VERSION,
                    system_prompt=scenario_policy.system_prompt())

    @app.post("/api/scenario-examples/{key}/load")
    def load_example(key: str, current=Depends(admin)):
        from .scenario_examples import load
        return load(key, current["id"])

    @app.post("/api/authoring/preview")
    def preview_authoring(body: CodexRequest, current=Depends(admin)):
        prompt, findings = sources.sanitize(body.prompt)
        context, documents = sources.reference_context(prompt, body.document_ids, current)
        return dict(prompt=prompt, input_privacy=findings, documents=documents,
                    security_log=scenario_policy.input_log(findings, documents),
                    context_characters=len(context), policy_version=scenario_policy.POLICY_VERSION)

    @app.post("/api/scenario-drafts/{rid}/publish")
    def publish(rid: str, current=Depends(admin)):
        row = resource(rid, "scenario_draft", current)
        if row["payload"].get("archived"):
            raise HTTPException(409, "Archived draft cannot be published")
        if row["payload"]["status"] == "published":
            raise HTTPException(409, "This draft is already published")
        if row["payload"].get("pack"):
            spec = packs.expand(row["payload"]["pack"], row["payload"]["source"])
            return publish_spec(spec, packs.scenario_tests(spec), current, row)
        return publish_direct(
            draft_model.model_validate(row["payload"]["definition"]), current, row
        )

    @app.get("/api/authoring/status")
    def codex_status(refresh: bool = False, current=Depends(admin)):
        return authoring.status(refresh)

    @app.post("/api/authoring/login")
    def codex_login(body: CodexLogin, current=Depends(admin)):
        from . import codex_login as login_bridge
        try:
            session = login_bridge.start(current["id"], body.method)
        except RuntimeError as e:
            raise HTTPException(400, str(e)) from e
        store.audit(current["id"], "codex.login", body.method)
        return session

    @app.get("/api/authoring/login")
    def codex_login_state(current=Depends(admin)):
        from . import codex_login as login_bridge
        return login_bridge.current(current["id"])

    @app.post("/api/authoring/login/cancel")
    def codex_login_cancel(current=Depends(admin)):
        from . import codex_login as login_bridge
        try:
            return login_bridge.cancel(current["id"])
        except RuntimeError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/authoring/logout")
    def codex_logout(current=Depends(admin)):
        from . import codex_login as login_bridge
        try:
            result = login_bridge.logout(current["id"])
        except RuntimeError as exc:
            raise HTTPException(400, str(exc)) from exc
        store.audit(current["id"], "codex.logout", "Local CLI credentials removed")
        return result

    @app.post("/api/authoring/settings")
    def codex_settings(body: CodexSettings, current=Depends(admin)):
        try:
            result = authoring.configure(body.enabled)
        except RuntimeError as exc:
            raise HTTPException(400, str(exc)) from exc
        store.audit(current["id"], "codex.settings", f"Authoring enabled: {body.enabled}")
        return result

    @app.get("/api/authoring/models")
    def codex_models(refresh: bool = False, current=Depends(admin)):
        from . import codex_models as model_bridge
        try:
            return model_bridge.catalogue(refresh)
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.post("/api/authoring/model")
    def codex_model(body: CodexModel, current=Depends(admin)):
        try:
            result = authoring.configure_model(body.model, body.effort)
        except RuntimeError as exc:
            raise HTTPException(400, str(exc)) from exc
        store.audit(current["id"], "codex.model", f"{body.model}, effort={body.effort}")
        return result

    @app.post("/api/authoring/codex")
    def codex_draft(body: CodexRequest, background: BackgroundTasks, current=Depends(admin)):
        prompt, findings = sources.sanitize(body.prompt)
        generation_prompt, documents = sources.reference_context(prompt, body.document_ids, current)
        state = authoring.status()
        if not state["enabled"] or not state["installed"]:
            raise HTTPException(
                503,
                state["reason"] + ". Manual JSON authoring remains available offline.",
            )
        if state["authenticated"] is not True:
            raise HTTPException(503, "Codex is installed but not signed in. Use 'Sign in to Codex' first.")
        if not state["ready"]:
            raise HTTPException(503, state["reason"])
        if not authoring.JOB_LOCK.acquire(blocking=False):
            raise HTTPException(409, "A Codex draft is already being generated")
        try:
            rid = store.create(
                "authoring_job", current["id"], dict(status="running", prompt=prompt, engine="codex", input_privacy=findings,
                                                    generation_prompt=generation_prompt, documents=documents,
                                                    security_log=scenario_policy.input_log(findings, documents))
            )
            background.add_task(authoring.build_job, rid, draft_model)
        except Exception:
            authoring.JOB_LOCK.release()
            raise
        store.audit(current["id"], "codex.draft", rid)
        return dict(id=rid, status="running")

    @app.get("/api/authoring/jobs")
    def authoring_jobs(current=Depends(admin)):
        return [dict(id=row["id"], **{k: v for k, v in row["payload"].items() if k != "generation_prompt"})
                for row in store.list_active_resources("authoring_job")]

    @app.get("/api/authoring/openai")
    def api_status(current=Depends(admin)):
        from . import openai_authoring
        return openai_authoring.status()

    @app.post("/api/authoring/openai/config")
    def api_connection(body: ApiConnection, current=Depends(admin)):
        from . import openai_authoring
        try:
            result = openai_authoring.configure(
                body.api_key.get_secret_value() if body.api_key is not None else None, body.model,
            )
        except RuntimeError as exc:
            raise HTTPException(400, str(exc)) from None
        store.audit(current["id"], "authoring.api.configure", "API credentials updated; secret not persisted")
        return result

    @app.post("/api/authoring/openai/clear")
    def api_clear(current=Depends(admin)):
        from . import openai_authoring
        result = openai_authoring.clear()
        store.audit(current["id"], "authoring.api.clear", "Transient API credentials cleared")
        return result

    @app.post("/api/authoring/openai")
    def api_draft(body: CodexRequest, background: BackgroundTasks, current=Depends(admin)):
        from . import openai_authoring
        prompt, findings = sources.sanitize(body.prompt)
        generation_prompt, documents = sources.reference_context(prompt, body.document_ids, current)
        state = openai_authoring.status()
        if not state["ready"]:
            raise HTTPException(503, state["reason"])
        if not authoring.JOB_LOCK.acquire(blocking=False):
            raise HTTPException(409, "A scenario draft is already being generated")
        try:
            rid = store.create("authoring_job", current["id"], dict(
                status="running", prompt=prompt, input_privacy=findings, engine="openai_api", model=state["model"],
                generation_prompt=generation_prompt, documents=documents,
                security_log=scenario_policy.input_log(findings, documents),
            ))
            background.add_task(authoring.build_job, rid, draft_model)
        except Exception:
            authoring.JOB_LOCK.release()
            raise
        store.audit(current["id"], "authoring.api.draft", rid)
        return dict(id=rid, status="running", engine="openai_api")

    @app.get("/api/authoring/jobs/{rid}")
    def job(rid: str, current=Depends(admin)):
        row = resource(rid, "authoring_job", current)
        return dict(id=rid, **{k: v for k, v in row["payload"].items() if k != "generation_prompt"})
