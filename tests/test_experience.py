import copy
import json
import time

import pytest
from fastapi.testclient import TestClient

from backend import authoring, catalog, experience, main, settings
from backend.engine import simulate
from test_api import HEADERS, login, world_draft


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA", tmp_path)
    monkeypatch.setattr(settings, "PRODUCTION", False)
    with TestClient(main.app, headers=HEADERS) as c:
        yield c


@pytest.mark.parametrize("spec", catalog.all_scenarios(), ids=lambda s: s["key"])
def test_every_scenario_has_a_guided_linked_runnable_environment(spec):
    prepared = experience.prepare(spec, 61, 20, 30)
    assert len(spec["briefing"]["steps"]) == 5
    assert len(spec["briefing"]["journey"]) >= 5
    assert spec["category"] != "Agentic Games"
    assert len(prepared["tables"]) >= 13
    assert prepared["validation"]["passed"]
    work = prepared["tables"]["work_items"]
    result = simulate(prepared["spec"], 61, 20, 30, work_items=work)
    assert {e["id"] for e in result["entities"]} == {e["work_id"] for e in work}
    assert len(result["activity"]) > 20
    assert any(e["kind"] == "incident" for e in result["events"])
    assert all(e["tick"] <= 30 for e in result["activity"])
    assert all(
        e["system_id"] in {n["id"] for n in prepared["spec"]["nodes"]} or e["state"] == "completed"
        for e in result["activity"]
    )


def test_prepared_workload_drives_engine_not_a_second_generation():
    spec = catalog.all_scenarios()[0]
    prepared = experience.prepare(spec, 3, 20, 30)
    work = copy.deepcopy(prepared["tables"]["work_items"])
    for item in work:
        item["arrival"] = 29
    result = simulate(prepared["spec"], 999, 20, 28, work_items=work)
    assert all(e["state"] == "scheduled" for e in result["entities"])
    assert result["activity"] == []


def test_prepare_inspect_launch_clock_pause_resume_and_data(client, monkeypatch):
    login(client, "learner")
    p = client.post(
        "/api/preparations", json=dict(scenario_key="mmorpg_economy", population=30, horizon=30)
    ).json()
    assert p["validation"]["foreign_key_checks"] >= 20
    starting = client.get(f"/api/preparations/{p['id']}/tables/work_items").json()
    assert starting["total"] == 30
    assert client.get(f"/api/preparations/{p['id']}/export").content[:2] == b"PK"
    r = client.post("/api/runs", json={"preparation_id": p["id"]}).json()
    rid = r["id"]
    assert r["tick"] == 0 and r["status"] == "paused"
    assert "ground_truth" not in r
    before = client.get(f"/api/runs/{rid}/data/live_telemetry").json()
    assert max(x["tick"] for x in before["rows"]) == 0
    now = time.time()
    monkeypatch.setattr(main.time, "time", lambda: now)
    r = client.post(
        f"/api/runs/{rid}/playback", json=dict(command="play", speed=1, version=r["version"])
    ).json()
    monkeypatch.setattr(main.time, "time", lambda: now + 8.2)
    r = client.get(f"/api/runs/{rid}").json()
    assert r["tick"] == 8 and r["status"] == "running"
    assert r["live"]["activity"]
    assert sum(r["live"]["states"].values()) == 30
    client.post(
        f"/api/runs/{rid}/playback", json=dict(command="pause", speed=1, version=r["version"])
    )
    monkeypatch.setattr(main.time, "time", lambda: now + 200)
    paused = client.get(f"/api/runs/{rid}").json()
    assert paused["tick"] == 8 and paused["status"] == "paused"
    trace = client.get(
        f"/api/runs/{rid}/data/work_items?work_id={starting['rows'][0]['work_id']}"
    ).json()
    assert trace["total"] == 1
    assert client.get(f"/api/runs/{rid}/data/not_a_table").status_code == 404
    assert (
        client.post(
            f"/api/runs/{rid}/playback",
            json=dict(command="play", speed=999, version=paused["version"]),
        ).status_code
        == 422
    )
    playing = client.post(
        f"/api/runs/{rid}/playback", json=dict(command="play", speed=3, version=paused["version"])
    ).json()
    monkeypatch.setattr(main.time, "time", lambda: now + 300)
    complete = client.get(f"/api/runs/{rid}").json()
    assert playing["clock"]["speed"] == 3
    assert complete["tick"] == 30 and complete["status"] == "completed"
    assert "ground_truth" in complete
    assert client.get(f"/api/runs/{rid}/report").status_code == 200


def test_admin_publishes_draft_and_separate_learner_receives_it(client):
    login(client, "admin")
    learner = TestClient(main.app, headers=HEADERS)
    login(learner, "learner")
    definition = dict(world_draft(), environment_style="voxel")
    assert learner.post("/api/scenario-drafts", json=definition).status_code == 403
    assert learner.post("/api/scenarios", json=definition).status_code == 403
    draft = client.post("/api/scenario-drafts", json=definition).json()
    assert draft["status"] == "draft"
    assert all(c["passed"] for c in draft["checks"])
    assert not any(s["title"] == definition["title"] for s in learner.get("/api/scenarios").json())
    assert learner.get("/api/scenario-drafts").status_code == 403
    published = client.post(f"/api/scenario-drafts/{draft['id']}/publish").json()
    key = published["key"]
    assert published["environment_style"] == "voxel"
    assert any(s["key"] == key for s in learner.get("/api/scenarios").json())
    notices = learner.get("/api/notifications").json()
    assert len(notices) == 1 and notices[0]["scenario_key"] == key
    assert not notices[0]["seen"]
    assert client.post(f"/api/notifications/{notices[0]['id']}/read").status_code == 404
    assert learner.post(f"/api/notifications/{notices[0]['id']}/read").status_code == 200
    assert client.post(f"/api/scenario-drafts/{draft['id']}/publish").status_code == 409
    assert len(learner.get("/api/notifications").json()) == 1
    r = learner.post("/api/runs", json=dict(scenario_key=key, population=20)).json()
    assert r["environment_style"] == "voxel"
    assert client.get(f"/api/runs/{r['id']}").status_code == 200
    assert (
        client.post(
            f"/api/runs/{r['id']}/advance", json=dict(ticks=1, version=r["version"])
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/runs/{r['id']}/decisions", json=dict(action_id="repair", version=r["version"])
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/runs/{r['id']}/playback", json=dict(command="play", version=r["version"])
        ).status_code
        == 403
    )
    assignment = client.post(
        "/api/assignments",
        json=dict(
            scenario_key=key,
            learners=["learner"],
            guidance="Follow one delivery from the mines to the settlement.",
        ),
    )
    assert assignment.status_code == 200
    assert len(learner.get("/api/assignments").json()) == 1
    assert len(learner.get("/api/notifications").json()) == 2
    assert (
        learner.post(
            "/api/assignments",
            json=dict(
                scenario_key=key, learners=["learner"], guidance="Not allowed to assign exercises."
            ),
        ).status_code
        == 403
    )
    learner.close()


def test_two_role_admin_can_publish_assign_and_observe_without_taking_over(client):
    login(client, "admin")
    with TestClient(main.app, headers=HEADERS) as learner:
        login(learner, "learner")
        definition = dict(world_draft(), environment_style="service_app")
        draft = client.post("/api/scenario-drafts", json=definition).json()
        assert draft["source"] == "manual" and draft["owner"] == "admin"
        assert draft["version"] == 0
        assert learner.get("/api/scenario-drafts").status_code == 403
        assert learner.post(f"/api/scenario-drafts/{draft['id']}/publish").status_code == 403
        assert not any(s["title"] == definition["title"] for s in learner.get("/api/scenarios").json())
        published = client.post(f"/api/scenario-drafts/{draft['id']}/publish").json()
        assert published["publication"]["draft_id"] == draft["id"]
        assert published["publication"]["source"] == "manual"
        assert client.post(f"/api/scenario-drafts/{draft['id']}/publish").status_code == 409
        notices = learner.get("/api/notifications").json()
        assert len(notices) == 1 and notices[0]["scenario_key"] == published["key"]
        assignment = client.post("/api/assignments", json=dict(
            scenario_key=published["key"], learners=["learner"],
            guidance="Inspect the linked records, explain the fault and choose a response.",
        ))
        assert assignment.status_code == 200
        assert len(learner.get("/api/assignments").json()) == 1
        run = learner.post("/api/runs", json=dict(
            scenario_key=published["key"], population=20, horizon=20,
        )).json()
        rid = run["id"]
        assert client.get(f"/api/runs/{rid}").status_code == 200
        for endpoint, body in [
            ("advance", dict(ticks=1, version=run["version"])),
            ("decisions", dict(action_id=run["actions"][0]["id"], version=run["version"])),
            ("playback", dict(command="play", version=run["version"])),
            ("diagnosis", dict(root_node=run["nodes"][0]["id"], cause="An observed fault", version=run["version"])),
        ]:
            response = client.post(f"/api/runs/{rid}/{endpoint}", json=body)
            assert response.status_code == 403, response.text
        assert learner.get(f"/api/runs/{rid}").json()["version"] == run["version"]
        progressed = learner.post(f"/api/runs/{rid}/advance", json=dict(
            ticks=20, version=run["version"],
        ))
        assert progressed.status_code == 200
        assert learner.get(f"/api/runs/{rid}/report").status_code == 200
        assert client.get(f"/api/runs/{rid}/report").status_code == 200
        own_preview = client.post("/api/runs", json=dict(
            scenario_key=published["key"], population=20, horizon=20,
        )).json()
        assert client.post(f"/api/runs/{own_preview['id']}/advance", json=dict(
            ticks=1, version=own_preview["version"],
        )).status_code == 200


def test_preparations_are_private_and_snapshot_is_immutable(client):
    login(client, "admin")
    prepared = client.post(
        "/api/preparations", json=dict(scenario_key="supply_chain", population=20)
    ).json()
    client.post("/api/auth/logout")
    login(client, "learner")
    assert client.get(f"/api/preparations/{prepared['id']}").status_code == 404
    assert client.post("/api/runs", json=dict(preparation_id=prepared["id"])).status_code == 404


def test_codex_disabled_fails_closed_and_mocked_job_requires_publication(client, monkeypatch):
    login(client, "learner")
    assert client.get("/api/authoring/status").status_code == 403
    client.post("/api/auth/logout")
    login(client, "admin")
    monkeypatch.delenv("SIMFORGE_CODEX_ENABLED", raising=False)
    prompt = {"prompt": "Build a safe warehouse simulation with six connected systems."}
    assert client.post("/api/authoring/codex", json=prompt).status_code == 503
    monkeypatch.setenv("SIMFORGE_CODEX_ENABLED", "1")
    monkeypatch.setattr(authoring, "executable", lambda: "fake-codex.exe")
    monkeypatch.setattr(authoring, "probe", lambda refresh=False: dict(authenticated=True, version="fake", detail="Signed in"))
    monkeypatch.setattr(authoring, "generate", lambda prompt, schema: world_draft())
    job = client.post("/api/authoring/codex", json=prompt).json()
    finished = client.get("/api/authoring/jobs/" + job["id"]).json()
    assert finished["status"] == "ready"
    assert not any(s["title"] == "Custom scenario" for s in client.get("/api/scenarios").json())
    assert (
        client.post("/api/scenario-drafts/" + finished["draft_id"] + "/publish").status_code == 200
    )
    monkeypatch.setattr(authoring, "generate", lambda prompt, schema: {"bad": "not a definition"})
    failed = client.post("/api/authoring/codex", json=prompt).json()
    assert client.get("/api/authoring/jobs/" + failed["id"]).json()["status"] == "failed"
    assert not authoring.JOB_LOCK.locked()


def test_schema_blocks_code_and_invalid_graphs(client):
    login(client, "admin")
    definition = world_draft()
    definition["python"] = 'print("not executed")'
    assert client.post("/api/scenario-drafts", json=definition).status_code == 422
    definition.pop("python")
    definition["edges"].append({"source": "c", "target": "a"})
    assert client.post("/api/scenario-drafts", json=definition).status_code == 422
    assert "additionalProperties" in json.dumps(
        authoring.strict_schema(main.WorldDraft.model_json_schema())
    )
