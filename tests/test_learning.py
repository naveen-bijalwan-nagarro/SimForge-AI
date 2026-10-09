"""Objective-only learning checks and evidence-based practice scores."""

import pytest
from fastapi.testclient import TestClient

from backend import main, settings, store
from test_api import HEADERS, login


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA", tmp_path)
    monkeypatch.setattr(settings, "PRODUCTION", False)
    with TestClient(main.app, headers=HEADERS) as c:
        login(c, "learner")
        yield c


def start(client):
    result = client.post("/api/runs", json=dict(scenario_key="supply_chain", population=60, horizon=25))
    assert result.status_code == 200, result.text
    return result.json()


def finish(client, run):
    current = client.get(f"/api/runs/{run['id']}").json()
    response = client.post(f"/api/runs/{run['id']}/advance", json=dict(ticks=30, version=current["version"]))
    assert response.status_code == 200, response.text
    return response.json()


def check(client, run, phase, choices):
    return client.post(f"/api/runs/{run['id']}/learning-check/{phase}", json={"choices": choices})


def test_objective_checks_and_upfront_progress(client):
    run = start(client)
    before = client.get(f"/api/runs/{run['id']}/learning-check").json()
    assert before["baseline_open"] and not before["post_open"]
    assert before["learning_score"] is None and before["gain_pp"] is None
    assert before["answer_keys"] is None
    assert all(set(q) == {"id", "prompt", "options"} for q in before["before_questions"])
    saved = check(client, run, "before", [1, 0, 2])
    assert saved.status_code == 200 and saved.json()["before"]["score"] == 100
    assert check(client, run, "before", [1, 0, 2]).status_code == 409
    finish(client, run)
    result = check(client, run, "after", [2, 1, 0])
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["after"]["score"] == 100 and data["gain_pp"] == 0
    assert data["learning_score"] == 50  # Knowledge only; no observed investigation/actions
    assert data["score_components"] == {"knowledge": 50, "diagnosis": 0, "evidence": 0, "decision": 0}
    assert data["answer_keys"]["after"] == [2, 1, 0]
    assert data["learning_journey"]["next_steps"]
    assert check(client, run, "after", [2, 1, 0]).status_code == 409
    assert client.get(f"/api/runs/{run['id']}/report").json()["learning"]["learning_score"] == 50


def test_missing_baseline_and_negative_change(client):
    run = start(client)
    finish(client, run)
    result = check(client, run, "after", [0, 0, 0]).json()
    assert result["gain_pp"] is None and result["before"] is None
    run = start(client)
    check(client, run, "before", [1, 0, 2])
    finish(client, run)
    result = check(client, run, "after", [0, 0, 0]).json()
    assert result["gain_pp"] == -66.7
    assert result["learning_score"] >= 0


def test_objective_behavior_score_without_subjective_grading(client):
    from backend.learning import evidence, objective_result
    run = start(client)
    p = store.get(run["id"])["payload"]
    incident = p["spec"]["incident"]
    inspect = next(a["id"] for a in p["spec"]["actions"] if a["effect"] == "inspect")
    repair = next(a["id"] for a in p["spec"]["actions"] if a["effect"] == "repair" and a["target"] == incident["node"])
    p["decisions"] = [dict(action_id=inspect, tick=6), dict(action_id=repair, tick=7)]
    p["diagnosis"] = dict(root_node=incident["node"], cause=incident["cause"], tick=6)
    p["tick"] = p["horizon"]
    p["learning_check"] = dict(after=dict(correct=3, total=3, score=100, choices=[2, 1, 0]))
    assert evidence(p)["inspected_before_response"] and evidence(p)["diagnosis_correct"]
    assert objective_result(p)["score"] == 100
    p["decisions"].reverse()
    p["diagnosis"]["tick"] = p["horizon"]
    assert objective_result(p)["score"] == 60  # Knowledge 50 + targeted repair 10


def test_role_and_quiz_rules(client):
    run = start(client)
    assert check(client, run, "after", [2, 1, 0]).status_code == 409
    assert check(client, run, "before", [3, 0, 0]).status_code == 422
    login(client, "admin")
    assert client.get(f"/api/runs/{run['id']}/learning-check").status_code == 200
    assert check(client, run, "before", [1, 0, 2]).status_code == 403
    assert client.post(f"/api/runs/{run['id']}/learning-review", json={}).status_code in (404, 405)


def test_custom_workflow_question_does_not_expose_hidden_cause():
    from backend.learning import question_set
    spec = dict(key="custom_demo", nodes=[
        dict(id="dispatch", label="Supplier dispatch"),
        dict(id="receiving", label="Inbound receiving"),
        dict(id="delivery", label="Customer delivery")],
        incident=dict(cause="Hidden dispatch failure"))
    p = dict(spec=spec)
    before, after = question_set("before", p), question_set("after", p)
    assert "Supplier dispatch" in before[0][0]
    assert "Inbound receiving" in after[0][0]
    assert all("Hidden dispatch failure" not in q[0] for q in before + after)


def test_baseline_closes_on_playback_and_forks_do_not_fake_gain(client):
    run = start(client)
    row = store.get(run["id"])
    row["payload"]["clock"].update(running=False, started_at=99999999999, started_tick=0, speed=1)
    store.update(row["id"], row["payload"], row["version"])
    assert check(client, run, "before", [1, 0, 2]).status_code == 409
    finish(client, run)
    assert check(client, run, "after", [2, 1, 0]).status_code == 200
    fork = client.post(f"/api/runs/{run['id']}/fork").json()
    assert not store.get(fork["id"])["payload"].get("learning_check")
    assert check(client, fork, "before", [1, 0, 2]).status_code == 409
    assert client.get(f"/api/runs/{fork['id']}/learning-check").json()["learning_score"] is None


def test_submitted_scores_and_subjective_fields_are_rejected(client):
    run = start(client)
    for field in ["score", "learning_score", "explanation"]:
        response = client.post(f"/api/runs/{run['id']}/learning-check/before",
                               json={"choices": [1, 0, 2], field: "client-controlled"})
        assert response.status_code == 422
    assert not store.get(run["id"])["payload"].get("learning_check")
    assert check(client, run, "unknown", [1, 0, 2]).status_code == 404


def test_late_and_premature_actions_do_not_receive_repair_credit(client):
    from backend.learning import evidence
    run = start(client)
    p = store.get(run["id"])["payload"]
    action = next(a for a in p["spec"]["actions"] if a["effect"] == "repair"
                  and a["target"] == p["spec"]["incident"]["node"])
    p["decisions"] = [dict(action_id=action["id"], tick=p["horizon"] - action["duration"] + 1)]
    assert not evidence(p)["targeted_repair"]
    p["decisions"][0]["tick"] = p["spec"]["incident"]["tick"] - 1
    assert not evidence(p)["targeted_repair"]
    p["decisions"][0]["tick"] = p["spec"]["incident"]["tick"]
    assert evidence(p)["targeted_repair"]
    p["diagnosis"] = dict(root_node=p["spec"]["incident"]["node"],
                         cause=p["spec"]["incident"]["cause"], tick=0)
    assert not evidence(p)["diagnosis_correct"]


def test_legacy_subjective_review_is_preserved_but_cannot_change_objective_score(client):
    run = start(client)
    finish(client, run)
    check(client, run, "after", [2, 1, 0])
    row = store.get(run["id"])
    row["payload"]["learning_check"]["review"] = dict(total=6, feedback="Historical record")
    store.update(row["id"], row["payload"], row["version"])
    view = client.get(f"/api/runs/{run['id']}/learning-check").json()
    assert view["learning_score"] == 50
    assert "review" not in view
    assert store.get(run["id"])["payload"]["learning_check"]["review"]["total"] == 6


def test_questions_are_saved_and_admin_cannot_change_owner_decisions(client):
    run = start(client)
    check(client, run, "before", [1, 0, 2])
    p = store.get(run["id"])["payload"]
    assert p["learning_check"]["before"]["questions"]
    assert "answer_keys" not in p["learning_check"]["before"]
    assert client.get(f"/api/runs/{run['id']}").json()["learning_progress"]["baseline_recorded"]
    login(client, "admin")
    previous = store.get(run["id"])
    assert check(client, run, "before", [1, 0, 2]).status_code == 403
    assert store.get(run["id"]) == previous
