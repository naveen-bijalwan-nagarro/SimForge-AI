import json
import os

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import authoring, authoring_config, main, openai_authoring, settings, store
from test_api import HEADERS, login, world_draft

KEY = "sk-test-placeholder-not-a-real-key-123456"
HTTP_CLIENT = httpx.Client


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA", tmp_path)
    monkeypatch.setattr(settings, "PRODUCTION", False)
    monkeypatch.setattr(openai_authoring, "_SESSION", {})
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SIMFORGE_AUTHORING_CONFIG", raising=False)
    monkeypatch.delenv("SIMFORGE_OPENAI_MODEL", raising=False)
    monkeypatch.setenv("SIMFORGE_OPENAI_ENABLED", "1")
    monkeypatch.setattr(authoring, "executable", lambda: None)
    with TestClient(main.app, headers=HEADERS) as client:
        yield client


def mock_api(monkeypatch, handler):
    monkeypatch.setattr(openai_authoring.httpx, "Client", lambda **kwargs: HTTP_CLIENT(
        transport=httpx.MockTransport(handler), **kwargs,
    ))


def configure(client):
    login(client, "admin")
    response = client.post("/api/authoring/openai/config", json=dict(api_key=KEY, model="gpt-4.1-mini"))
    assert response.status_code == 200
    assert KEY not in response.text
    return response.json()


def test_api_without_cli_generates_checked_draft_and_fresh_learner_data(client, monkeypatch):
    configure(client)
    calls = []

    def provider(request):
        calls.append(request)
        payload = json.loads(request.content)
        assert str(request.url) == "https://api.openai.com/v1/responses"
        assert request.headers["Authorization"] == "Bearer " + KEY
        assert payload["store"] is False and payload["max_output_tokens"] == 6000
        assert payload["text"]["format"]["strict"] is True
        assert payload["text"]["format"]["schema"]["additionalProperties"] is False
        assert "tools" not in payload and KEY not in json.dumps(payload)
        return httpx.Response(200, json=dict(status="completed", output=[dict(
            type="message", content=[dict(type="output_text", text=json.dumps(world_draft()))],
        )]))

    mock_api(monkeypatch, provider)
    response = client.post("/api/authoring/openai", json=dict(
        prompt="Create a synthetic delivery exercise linking dispatch, storage and customer orders.",
    ))
    assert response.status_code == 200
    job = client.get(f"/api/authoring/jobs/{response.json()['id']}").json()
    assert job["status"] == "ready" and job["engine"] == "openai_api"
    assert len(calls) == 1 and not authoring.JOB_LOCK.locked()
    draft = next(d for d in client.get("/api/scenario-drafts").json() if d["id"] == job["draft_id"])
    assert draft["source"] == "openai_api" and all(c["passed"] for c in draft["checks"])
    assert not any(s["title"] == draft["definition"]["title"] for s in client.get("/api/scenarios").json())
    published = client.post(f"/api/scenario-drafts/{draft['id']}/publish").json()
    assert published["publication"]["source"] == "openai_api"
    with TestClient(main.app, headers=HEADERS) as learner:
        login(learner, "learner")
        assert learner.get("/api/notifications").json()[0]["scenario_key"] == published["key"]
        prepared = learner.post("/api/preparations", json=dict(
            scenario_key=published["key"], population=60, horizon=30, seed=51,
        )).json()
        assert prepared["validation"]["passed"] and {"work_items", "workflow_steps", "people"} <= set(prepared["tables"])
        assert learner.get("/api/preparations").json()[0]["id"] == prepared["id"]
        assert prepared["owner"] == "learner"
        assert client.get("/api/preparations").json()[0]["owner"] == "learner"
        assert client.post("/api/runs", json=dict(preparation_id=prepared["id"])).status_code == 403
        work = learner.get(f"/api/preparations/{prepared['id']}/tables/work_items").json()
        assert work["total"] == 60
        run = learner.post("/api/runs", json=dict(preparation_id=prepared["id"])).json()
        assert run["preparation_id"] == prepared["id"]
    with store.connection() as db:
        for table, column in [("metadata", "value"), ("resources", "payload"), ("audit", "detail")]:
            assert all(KEY not in row[0] for row in db.execute(f"SELECT {column} FROM {table}"))


def test_only_two_roles_and_key_settings_are_admin_only(client):
    with store.connection() as db:
        assert {r[0] for r in db.execute("SELECT role FROM users")} == {"admin", "learner"}
    login(client, "learner")
    for path, method, data in [
        ("/api/authoring/openai", "get", None),
        ("/api/authoring/openai/config", "post", dict(api_key=KEY)),
        ("/api/authoring/openai/clear", "post", {}),
        ("/api/authoring/openai", "post", dict(prompt="A safe synthetic scenario for supply-chain training.")),
    ]:
        response = getattr(client, method)(path, **({"json": data} if data is not None else {}))
        assert response.status_code == 403 and KEY not in response.text
    client.post("/api/auth/logout")
    login(client, "admin")
    assert client.post("/api/users", json=dict(
        username="coach", name="Coach", password="a-long-test-password", role="trainer",
    )).status_code == 422


def test_config_validation_never_echoes_credentials_and_clear_is_explicit(client):
    state = configure(client)
    assert state["ready"] and state["key_source"] == "server memory"
    for body in [dict(api_key=KEY, model=[]), dict(api_key=[KEY]), [dict(api_key=KEY)]]:
        response = client.post("/api/authoring/openai/config", json=body)
        assert response.status_code == 422 and KEY not in response.text
    invalid = client.post("/api/authoring/openai/config", json=dict(api_key=KEY, model="bad model"))
    assert invalid.status_code == 400 and KEY not in invalid.text
    assert client.post("/api/authoring/openai/clear", json={}).json()["configured"] is False
    assert client.post("/api/authoring/openai", json=dict(
        prompt="Create a safe synthetic warehouse scenario for learner investigation.",
    )).status_code == 503


@pytest.mark.parametrize("code", [400, 401, 403, 404, 429, 500])
def test_provider_errors_are_redacted_and_never_retried(client, monkeypatch, code):
    configure(client)
    calls = []

    def error(request):
        calls.append(request)
        return httpx.Response(code, json={"error": {"message": "secret " + KEY}})

    mock_api(monkeypatch, error)
    job = client.post("/api/authoring/openai", json=dict(
        prompt="A synthetic supply-chain training scenario with several connected systems.",
    )).json()
    failed = client.get(f"/api/authoring/jobs/{job['id']}")
    assert failed.json()["status"] == "failed" and KEY not in failed.text
    assert len(calls) == 1 and not authoring.JOB_LOCK.locked()
    assert client.get("/api/scenario-drafts").json() == []


@pytest.mark.parametrize("response", [
    {"status": "incomplete", "output": []},
    {"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal"}]}]},
    {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": "[]"}]}]},
])
def test_refusal_incomplete_and_invalid_definition_fail_closed(client, monkeypatch, response):
    configure(client)
    mock_api(monkeypatch, lambda request: httpx.Response(200, json=response))
    job = client.post("/api/authoring/openai", json=dict(
        prompt="Create a synthetic training workflow for staff to diagnose and repair.",
    )).json()
    assert client.get(f"/api/authoring/jobs/{job['id']}").json()["status"] == "failed"
    assert client.get("/api/scenario-drafts").json() == []


def test_production_requires_opt_in_and_environment_credentials_not_exposed(client, monkeypatch):
    login(client, "admin")
    monkeypatch.setattr(settings, "PRODUCTION", True)
    monkeypatch.delenv("SIMFORGE_OPENAI_ENABLED")
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    state = client.get("/api/authoring/openai")
    assert not state.json()["ready"] and KEY not in state.text
    monkeypatch.setenv("SIMFORGE_OPENAI_ENABLED", "1")
    state = client.get("/api/authoring/openai").json()
    assert state["ready"] and state["key_source"] == "server environment"
    assert client.post("/api/authoring/openai/clear", json={}).json()["configured"]


def test_retired_trainers_keep_records_without_admin_escalation(client):
    with store.connection() as db:
        db.execute("INSERT INTO users VALUES(?,?,?,?)", (
            "old-coach", "Former coach", "trainer", store.password_hash("safe-test-password"),
        ))
    token = store.authenticate("old-coach", "safe-test-password", "migration-test")
    rid = store.create("dataset", "old-coach", {"title": "Existing exercise"})
    store.initialize()
    assert store.session_user(token) is None
    assert store.get(rid)["owner"] == "old-coach"
    with store.connection() as db:
        assert db.execute("SELECT role FROM users WHERE id='old-coach'").fetchone()[0] == "learner"


def private_file(text):
    target = authoring_config.path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    target.chmod(0o600)
    return target


def test_private_backup_survives_restart_without_secret_exposure_or_export(client, monkeypatch):
    private_file(f'[openai_backup]\napi_key = "{KEY}"\nmodel = "configured-test-model"\n')
    login(client, "admin")
    state = client.get("/api/authoring/openai")
    assert state.json()["ready"] and state.json()["key_source"] == "private server file"
    assert state.json()["primary"] == "codex" and state.json()["automatic_fallback"] is False
    assert KEY not in state.text and os.getenv("OPENAI_API_KEY") is None
    assert openai_authoring.credentials()[:2] == (KEY, "configured-test-model")
    monkeypatch.setattr(openai_authoring, "_SESSION", {})  # Simulate transient state lost on restart.
    assert client.get("/api/authoring/openai").json()["configured"]
    # Removing a UI key must not overwrite/delete a server-managed persistent file.
    assert client.post("/api/authoring/openai/clear", json={}).json()["configured"]
    assert authoring_config.path().exists()
    calls = []
    mock_api(monkeypatch, lambda request: calls.append(request) or httpx.Response(500))
    assert client.post("/api/authoring/codex", json=dict(
        prompt="Create a synthetic mock-data scenario for warehouse staff to investigate.",
    )).status_code == 503
    assert calls == [] and client.get("/api/authoring/jobs").json() == []
    def provider(request):
        calls.append(request)
        assert request.headers["Authorization"] == "Bearer " + KEY
        assert json.loads(request.content)["model"] == "configured-test-model"
        return httpx.Response(200, json=dict(status="completed", output=[dict(
            type="message", content=[dict(type="output_text", text=json.dumps(world_draft()))],
        )]))
    mock_api(monkeypatch, provider)
    backup_job = client.post("/api/authoring/openai", json=dict(
        prompt="Create a synthetic mock-data warehouse exercise using the explicit backup.",
    )).json()
    assert client.get(f"/api/authoring/jobs/{backup_job['id']}").json()["status"] == "ready"
    assert len(calls) == 1 and os.getenv("OPENAI_API_KEY") is None
    login(client, "learner")
    assert client.get("/api/authoring/openai").status_code == 403
    assert client.get("/api/assets/data/secrets/authoring.local.toml").status_code == 404
    assert KEY not in client.get("/data/secrets/authoring.local.toml").text


def test_memory_then_environment_then_file_priority_and_config_model(client, monkeypatch):
    file_key = "sk-file-placeholder-not-a-real-secret-456"
    private_file(f'[openai_backup]\napi_key = "{file_key}"\nmodel = "file-model"\n')
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    monkeypatch.setenv("SIMFORGE_OPENAI_MODEL", "environment-model")
    assert openai_authoring.credentials() == (KEY, "environment-model", "server environment")
    memory_key = "sk-memory-placeholder-not-a-real-secret-789"
    openai_authoring.configure(memory_key, "memory-model")
    assert openai_authoring.credentials() == (memory_key, "memory-model", "server memory")
    openai_authoring.clear()
    monkeypatch.delenv("OPENAI_API_KEY")
    monkeypatch.delenv("SIMFORGE_OPENAI_MODEL")
    assert openai_authoring.credentials() == (file_key, "file-model", "private server file")


@pytest.mark.parametrize("text", [
    '[openai_backup]\napi_key = "' + KEY,
    'openai_backup = ["' + KEY + '"]',
    '[openai_backup]\napi_key = 12',
    '[openai_backup]\napi_key = "' + KEY + '"\nmodel = "bad model"',
    '# ' + KEY + '\n' + 'x' * 5000,
])
def test_invalid_private_files_fail_closed_and_never_echo_source(client, text):
    private_file(text)
    login(client, "admin")
    state = client.get("/api/authoring/openai")
    assert not state.json()["ready"] and KEY not in state.text
    assert "configuration file" in state.json()["reason"]
    with pytest.raises(RuntimeError, match="configuration file"):
        openai_authoring.credentials()


def test_explicit_custom_file_path(client, monkeypatch, tmp_path):
    monkeypatch.setenv("SIMFORGE_AUTHORING_CONFIG", str(tmp_path / "server-secrets" / "backup.toml"))
    private_file(f'[openai_backup]\napi_key = "{KEY}"\n')
    assert openai_authoring.status()["key_source"] == "private server file"
