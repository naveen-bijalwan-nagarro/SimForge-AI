import sqlite3
import pytest
from fastapi.testclient import TestClient
from backend import settings, store
from backend.main import app

HEADERS = {"X-SimForge-Request": "1"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA", tmp_path)
    monkeypatch.setattr(settings, "PRODUCTION", False)
    with TestClient(app, headers=HEADERS) as c:
        yield c


def login(client, role="admin"):
    r = client.post("/api/auth/login", json={"username": role, "password": role + "123"})
    assert r.status_code == 200


def test_auth_roles_and_csrf(client):
    assert client.get("/api/scenarios").status_code == 401
    assert (
        client.post(
            "/api/auth/login",
            headers={"X-SimForge-Request": ""},
            json={"username": "admin", "password": "admin123"},
        ).status_code
        == 403
    )
    login(client, "learner")
    assert client.post("/api/connectors", json={"name": "test", "type": "file"}).status_code == 403
    assert client.get("/api/audit").status_code == 403
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/logout").status_code == 200


def test_world_lifecycle_restart_report_and_ownership(client):
    login(client)
    assert len(client.get("/api/scenarios").json()) == 75
    r = client.post(
        "/api/runs", json={"scenario_key": "mmorpg_economy", "population": 50, "horizon": 30}
    ).json()
    rid = r["id"]
    assert "ground_truth" not in r
    assert client.get(f"/api/runs/{rid}/report").status_code == 400
    r = client.post(f"/api/runs/{rid}/advance", json={"ticks": 10, "version": 0}).json()
    assert (
        client.post(f"/api/runs/{rid}/advance", json={"ticks": 5, "version": 0}).status_code == 409
    )
    assert len(client.post(f"/api/runs/{rid}/agents").json()) == 3
    decision = {"action_id": "patch_rewards", "version": r["version"]}
    r = client.post(f"/api/runs/{rid}/decisions", json=decision).json()
    assert (
        client.post(
            f"/api/runs/{rid}/decisions", json=dict(decision, version=r["version"])
        ).status_code
        == 409
    )
    store.initialize()  # same persistent DB remains resumable
    assert client.get(f"/api/runs/{rid}").json() == r
    r = client.post(f"/api/runs/{rid}/advance", json={"ticks": 30, "version": r["version"]}).json()
    assert r["tick"] == 30 and "ground_truth" in r
    report = client.get(f"/api/runs/{rid}/report").json()
    assert report["comparison"]["loss_avoided"] > 0
    assert (
        client.get(f"/api/runs/{rid}/export").headers["content-type"].startswith("application/json")
    )
    fork = client.post(f"/api/runs/{rid}/fork").json()
    assert fork["tick"] == 0 and not fork["decisions"]
    client.post("/api/auth/logout")
    login(client, "learner")
    assert client.get(f"/api/runs/{rid}").status_code == 404


def test_training_assessment_exports_and_sqlite_connector(client):
    login(client)
    r = client.post("/api/datasets", json={"scenario_key": "supplier_risk"})
    assert r.status_code == 200, r.text
    data = r.json()
    rid = data["id"]
    assert data["quality"]["score"] == 100
    table = client.get(f"/api/datasets/{rid}/tables/suppliers").json()
    assert next(x for x in table["rows"] if x["supplier_id"] == "S-03")["on_time_pct"] == 62.5
    assert client.get(f"/api/datasets/{rid}/export").content[:2] == b"PK"
    r = client.post(
        f"/api/datasets/{rid}/assess",
        json={
            "root_cause": "Supplier S-03 deterioration is causing late inbound deliveries",
            "evidence": ["S-03", "late", "lead_time", "stock"],
            "recommendation": "alternate supplier buffer contract expedite",
        },
    )
    assert r.json()["score"] == 100
    cid = client.post("/api/connectors", json={"name": "Local SQLite", "type": "sqlite"}).json()[
        "id"
    ]
    result = client.post(f"/api/connectors/{cid}/push/{rid}").json()
    with sqlite3.connect(result["destination"]) as db:
        assert db.execute('SELECT COUNT(*) FROM "suppliers"').fetchone()[0] == 8


def world_draft():
    return dict(
        title="Custom scenario",
        summary="Test a connected warehouse workflow",
        unit="jobs",
        nodes=[
            dict(id="a", label="Source", role="investigator"),
            dict(id="b", label="Queue"),
            dict(id="c", label="Outcome", role="finance"),
        ],
        edges=[dict(source="a", target="b"), dict(source="b", target="c")],
        incident_node="a",
        cause="An upstream source fails during dispatch",
    )


def test_custom_world_validates_graph_and_is_runnable(client):
    login(client, "admin")
    payload = world_draft()
    r = client.post("/api/scenarios", json=payload)
    assert r.status_code == 200, r.text
    assert r.json()["key"].startswith("custom_")
    assert (
        client.post(
            "/api/runs", json={"scenario_key": r.json()["key"], "population": 20}
        ).status_code
        == 200
    )
    payload["edges"].append(dict(source="c", target="a"))
    assert client.post("/api/scenarios", json=payload).status_code == 422
    payload = world_draft()
    payload["nodes"][1]["id"] = "a"
    assert client.post("/api/scenarios", json=payload).status_code == 422


def test_bounds_invalid_actions_and_login_throttle(client):
    login(client)
    assert (
        client.post(
            "/api/runs", json={"scenario_key": "supply_chain", "population": 1000000}
        ).status_code
        == 422
    )
    assert client.post("/api/runs", json={"scenario_key": "sales_decline"}).status_code == 200
    r = client.post("/api/runs", json={"scenario_key": "supply_chain", "population": 20}).json()
    assert (
        client.post(
            f"/api/runs/{r['id']}/decisions", json={"version": 0, "action_id": "unknown"}
        ).status_code
        == 400
    )
    for _ in range(12):
        response = client.post("/api/auth/login", json={"username": "bad", "password": "bad"})
    assert response.status_code == 429


def test_production_fails_closed_without_admin_password(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA", tmp_path)
    monkeypatch.setattr(settings, "PRODUCTION", True)
    monkeypatch.delenv("SIMFORGE_ADMIN_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="SIMFORGE_ADMIN_PASSWORD"):
        store.initialize()


def test_production_bootstrap_has_no_demo_users(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA", tmp_path)
    monkeypatch.setattr(settings, "PRODUCTION", True)
    monkeypatch.setenv("SIMFORGE_ADMIN_PASSWORD", "test-only-long-bootstrap-password")
    store.initialize()
    with store.connection() as db:
        assert [r[0] for r in db.execute("SELECT id FROM users")] == ["admin"]
    assert store.authenticate("admin", "admin123", "test") is None
    assert store.authenticate("admin", "test-only-long-bootstrap-password", "test")


def test_production_rejects_development_database(client, monkeypatch):
    monkeypatch.setattr(settings, "PRODUCTION", True)
    with pytest.raises(RuntimeError, match="development"):
        store.initialize()


def test_authoritative_budget_rejects_overspend(client):
    login(client)
    created = client.post(
        "/api/runs", json={"scenario_key": "supply_chain", "population": 20}
    ).json()
    row = store.get(created["id"])
    row["payload"]["spec"]["budget"] = 100
    assert store.update(row["id"], row["payload"], row["version"])
    response = client.post(
        f"/api/runs/{row['id']}/decisions", json={"action_id": "alternate_supplier", "version": 1}
    )
    assert response.status_code == 400
    assert not store.get(row["id"])["payload"]["decisions"]


def test_invalid_size_header_is_a_client_error(client):
    response = client.post(
        "/api/auth/login",
        headers={"Content-Length": "nonsense"},
        json={"username": "trainer", "password": "trainer123"},
    )
    assert response.status_code == 400
