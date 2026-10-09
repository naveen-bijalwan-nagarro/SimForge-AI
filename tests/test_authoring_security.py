"""Value-free security receipts and policy visibility across the authoring boundary."""
import base64
import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from test_demo_examples import definition
from test_api import HEADERS, login
from backend import authoring, main, scenario_policy, settings, store


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA", tmp_path)
    monkeypatch.setattr(settings, "PRODUCTION", False)
    with TestClient(main.app, headers=HEADERS) as session:
        login(session)
        yield session


def test_policy_is_dedicated_and_matches_actual_server_prompt(client):
    response = client.get("/api/authoring/policy")
    assert response.status_code == 200
    policy = response.json()
    assert policy["system_prompt"] == scenario_policy.system_prompt()
    assert policy["sha256"] == hashlib.sha256(policy["system_prompt"].encode()).hexdigest()


def test_reference_screening_receipt_survives_generation(client, monkeypatch):
    uploaded = client.post("/api/scenario-documents", json={"files": [{
        "name": "reference.txt", "content": base64.b64encode(
            b"Contact fixture@example.test. Inspect synthetic handoffs before acting."
        ).decode(),
    }]}).json()["documents"][0]
    request = {"prompt": "Create a safe training exercise about processing interruptions.",
               "document_ids": [uploaded["id"]]}
    preview = client.post("/api/authoring/preview", json=request).json()
    assert preview["security_log"][1]["entities"] == {"EMAIL_ADDRESS": 1}
    assert not store.list_resources("authoring_job")
    monkeypatch.setattr(authoring, "status", lambda: dict(enabled=True, installed=True, authenticated=True, ready=True))
    def generate(prompt, schema):
        assert "fixture@example.test" not in prompt
        assert "<EMAIL_ADDRESS>" in prompt
        return definition()
    monkeypatch.setattr(authoring, "generate", generate)
    job = client.post("/api/authoring/codex", json=request).json()
    completed = client.get("/api/authoring/jobs/" + job["id"]).json()
    assert completed["status"] == "ready"
    events = store.get(completed["draft_id"], "scenario_draft")["payload"]["governance"]["events"]
    assert events[1]["document_id"] == uploaded["id"]
    assert events[1]["total"] == 1
    assert "fixture@example.test" not in json.dumps(events)
