"""UI account controls: no real credential changes or billable calls in these tests."""

import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import authoring, codex_login, codex_models, main, settings, store
from test_api import HEADERS, login


@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA", tmp_path)
    monkeypatch.setattr(settings, "PRODUCTION", False)
    monkeypatch.delenv("SIMFORGE_CODEX_ENABLED", raising=False)
    monkeypatch.setattr(authoring, "_PROBE", dict(at=0, value=None))
    monkeypatch.setattr(codex_login, "_SESSION", None)
    monkeypatch.setattr(codex_models, "_CACHE", dict(key=None, at=0, value=None))
    store.initialize()
    yield tmp_path
    codex_login.shutdown()


@pytest.fixture
def cli(monkeypatch):
    state = {"authenticated": False, "calls": []}
    monkeypatch.setattr(authoring, "executable", lambda: "fake-codex.exe")

    def run(args, timeout=30):
        state["calls"].append(args)
        if args == ["--version"]:
            return subprocess.CompletedProcess(args, 0, "codex-cli test", "")
        if args == ["logout"]:
            state["authenticated"] = False
            return subprocess.CompletedProcess(args, 0, "", "Successfully logged out")
        return subprocess.CompletedProcess(args, 0 if state["authenticated"] else 1, "", "WARNING: local-path secret-test-token\n" + ("Logged in using ChatGPT" if state["authenticated"] else "Not logged in"))

    monkeypatch.setattr(authoring, "_run", run)
    return state


def fake_login(monkeypatch, script):
    calls = []
    def command(args):
        calls.append(args)
        return [sys.executable, "-u", "-c", script]
    monkeypatch.setattr(authoring, "command", command)
    return calls


def wait_until(predicate):
    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    pytest.fail("Login did not reach the expected state")


def test_readiness_persists_and_has_one_source_of_truth(local, cli, monkeypatch):
    cli["authenticated"] = True
    assert authoring.status()["reason"] == "Enable Codex authoring in this panel"
    assert authoring.configure(True)["ready"] is True
    assert authoring.enabled() is True
    with TestClient(main.app, headers=HEADERS) as client:
        login(client, "admin")
        state = client.get("/api/authoring/status").json()
        assert client.get("/api/factory/status").json()["codex"] == state
        assert state["detail"] == "Signed in using ChatGPT"
        assert "secret-test-token" not in str(state)
    monkeypatch.setenv("SIMFORGE_CODEX_ENABLED", "0")
    assert authoring.status()["ready"] is False
    with pytest.raises(RuntimeError, match="server configuration"):
        authoring.configure(True)
    monkeypatch.setenv("SIMFORGE_CODEX_ENABLED", "1")
    assert authoring.configure(False)["enabled"] is False
    monkeypatch.setattr(settings, "PRODUCTION", True)
    assert authoring.enabled() is True


def test_credential_file_is_not_proof_of_authentication(local, monkeypatch):
    monkeypatch.setattr(authoring, "executable", lambda: "fake")
    monkeypatch.setattr(authoring, "_run", lambda *args: None)
    monkeypatch.setattr(Path, "home", lambda: local)
    (local / ".codex").mkdir()
    (local / ".codex" / "auth.json").write_text('{"expired":true}', encoding="utf-8")
    authoring.configure(True)
    assert authoring.status(True)["authenticated"] is False
    assert authoring.status()["ready"] is False


def test_npm_windows_shim_runs_without_a_shell(local, monkeypatch):
    shim = local / "npm" / "codex.cmd"
    entry = shim.parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
    entry.parent.mkdir(parents=True)
    entry.write_text("// fixture", encoding="utf-8")
    monkeypatch.setattr(authoring, "executable", lambda: str(shim))
    monkeypatch.setattr(authoring.shutil, "which", lambda name: "node.exe")
    assert authoring.command(["login", "status"]) == ["node.exe", str(entry), "login", "status"]


def test_npm_prefers_native_binary_so_cancellation_reaps_the_cli(local, monkeypatch):
    shim = local / "npm" / "codex.cmd"
    native = shim.parent / "node_modules/@openai/codex/node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe"
    native.parent.mkdir(parents=True)
    native.write_bytes(b"fixture")
    monkeypatch.setattr(authoring, "executable", lambda: str(shim))
    monkeypatch.setattr(authoring.platform, "machine", lambda: "AMD64")
    assert authoring.command(["login"]) == [str(native), "login"]


@pytest.mark.parametrize("role", ["learner"])
def test_account_controls_are_admin_only(local, cli, role):
    with TestClient(main.app, headers=HEADERS) as client:
        login(client, role)
        for url, body in [("login", {}), ("login/cancel", {}), ("logout", {}), ("settings", {"enabled": True})]:
            assert client.post("/api/authoring/" + url, json=body).status_code == 403
        assert client.get("/api/authoring/login").status_code == 403
        assert client.get("/api/authoring/jobs").status_code == 403
        assert client.get("/api/authoring/models").status_code == 403
        assert client.post("/api/authoring/model", json={"model": "test", "effort": "low"}).status_code == 403
        assert cli["calls"] == []


def test_settings_csrf_and_production_guard(local, cli, monkeypatch):
    with TestClient(main.app, headers=HEADERS) as client:
        login(client, "admin")
        assert client.post("/api/authoring/settings", json={"enabled": True}, headers={"X-SimForge-Request": ""}).status_code == 403
        assert client.post("/api/authoring/settings", json={"enabled": True}).json()["enabled"] is True
        monkeypatch.setattr(settings, "PRODUCTION", True)
        for url, body in [("login", {}), ("logout", {}), ("settings", {"enabled": True})]:
            assert client.post("/api/authoring/" + url, json=body).status_code == 400


@pytest.mark.parametrize("method", ["browser", "device"])
def test_login_links_codes_are_owner_scoped_and_cancellable(local, cli, monkeypatch, method):
    calls = fake_login(monkeypatch, "import time; print('https://evil.example/oauth/authorize', flush=True); print('https://auth.openai.com/codex/device', flush=True); print('ABCD-EFGH', flush=True); time.sleep(60)")
    session = codex_login.start("admin", method)
    wait_until(lambda: codex_login.current("admin")["auth_url"] is not None)
    current = codex_login.current("admin")
    assert current["auth_url"] == "https://auth.openai.com/codex/device"
    assert current["device_code"] == ("ABCD-EFGH" if method == "device" else None)
    assert codex_login.current("other-admin") is None
    with pytest.raises(RuntimeError, match="Another administrator"):
        codex_login.start("other-admin", method)
    assert codex_login.start("admin", method)["id"] == session["id"]
    assert calls == [["login"] + (["--device-auth"] if method == "device" else [])]
    assert "process" not in current and "owner" not in current
    cancelled = codex_login.cancel("admin")
    assert cancelled["status"] == "cancelled"
    assert cancelled["auth_url"] is None and cancelled["device_code"] is None
    assert codex_login._SESSION["process"].poll() is not None


def test_success_checks_cli_and_clears_one_time_details(local, cli, monkeypatch):
    fake_login(monkeypatch, "import time; print('https://auth.openai.com/oauth/authorize?state=test', flush=True); time.sleep(0.2)")
    codex_login.start("admin")
    cli["authenticated"] = True
    wait_until(lambda: codex_login.current("admin")["status"] == "authenticated")
    assert codex_login.current("admin")["auth_url"] is None
    authoring.configure(True)
    assert authoring.status()["ready"] is True
    assert codex_login.logout("admin")["ready"] is False
    assert ["logout"] in cli["calls"]


def test_device_failure_is_actionable_and_never_leaks_output(local, cli, monkeypatch):
    fake_login(monkeypatch, "import sys; print('device auth disabled 403 private-secret-token', flush=True); sys.exit(1)")
    codex_login.start("admin", "device")
    wait_until(lambda: codex_login.current("admin")["status"] == "failed")
    assert "browser sign-in" in codex_login.current("admin")["message"]
    assert "private-secret" not in str(codex_login.current("admin"))


def test_silent_login_expires_and_is_reaped(local, cli, monkeypatch):
    monkeypatch.setattr(codex_login, "LOGIN_TIMEOUT", 0.15)
    fake_login(monkeypatch, "import time; time.sleep(60)")
    codex_login.start("admin", "device")
    wait_until(lambda: codex_login.current("admin")["status"] == "expired")
    assert codex_login._SESSION["process"].poll() is not None


def test_existing_login_does_not_launch_oauth(local, cli, monkeypatch):
    cli["authenticated"] = True
    monkeypatch.setattr(authoring, "command", lambda args: pytest.fail("Already signed in"))
    assert codex_login.start("admin")["status"] == "authenticated"


def test_job_history_is_available_after_navigation(local, cli, monkeypatch):
    from test_api import world_draft
    cli["authenticated"] = True
    authoring.configure(True)
    monkeypatch.setattr(authoring, "generate", lambda *args: world_draft())
    with TestClient(main.app, headers=HEADERS) as client:
        login(client, "admin")
        job = client.post("/api/authoring/codex", json={"prompt": "Create a mock six-system warehouse exercise."}).json()
        history = client.get("/api/authoring/jobs").json()
        assert history[0]["id"] == job["id"]
        assert history[0]["status"] == "ready"
        assert client.get("/api/authoring/jobs/" + job["id"]).json()["draft_id"]


def test_model_settings_are_validated_shared_and_do_not_change_cli_defaults(local, cli, monkeypatch):
    value = dict(models=[dict(id="supported", label="Supported", default=True, efforts=["low", "medium"], default_effort="low")], configured_model="unsupported-default", configured_effort="ultra")
    cli["authenticated"] = True
    monkeypatch.setattr(codex_models, "cached", lambda: value)
    monkeypatch.setattr(codex_models, "catalogue", lambda refresh=False: value)
    authoring.configure(True)
    assert authoring.status()["ready"] is False
    with TestClient(main.app, headers=HEADERS) as client:
        login(client, "admin")
        assert client.post("/api/authoring/model", json={"model": "unsupported-default", "effort": "low"}).status_code == 400
        assert client.post("/api/authoring/model", json={"model": "supported", "effort": "ultra"}).status_code == 400
        state = client.post("/api/authoring/model", json={"model": "supported", "effort": "medium"}).json()
        assert state["ready"] is True and state["model"] == "supported" and state["effort"] == "medium"
        assert client.get("/api/factory/status").json()["codex"]["model"] == "supported"
        assert authoring.command(["exec", "-"])[1:] == ["exec", "--model", "supported", "-c", 'model_reasoning_effort="medium"', "-"]
        assert value["configured_model"] == "unsupported-default"
        monkeypatch.setattr(settings, "PRODUCTION", True)
        assert client.post("/api/authoring/model", json={"model": "supported", "effort": "low"}).status_code == 400


def test_model_catalogue_handshake_and_configuration_are_bounded(local, cli, monkeypatch):
    script = '''import json, sys
for line in sys.stdin:
    q = json.loads(line)
    if "id" not in q: continue
    if q["method"] == "initialize": result = {"userAgent":"test"}
    elif q["method"] == "model/list": result = {"data":[{"model":"supported", "displayName":"Supported model", "isDefault":True, "supportedReasoningEfforts":[{"reasoningEffort":"low"}], "defaultReasoningEffort":"low"}], "nextCursor":None}
    else: result = {"config":{"model":"unsupported-default", "model_reasoning_effort":"ultra", "private-secret":"never return this"}}
    print(json.dumps({"id":q["id"], "result":result}), flush=True)
'''
    fake_login(monkeypatch, script)
    result = codex_models._catalogue(timeout=3)
    assert result["models"][0]["id"] == "supported"
    assert result["configured_model"] == "unsupported-default"
    assert "private-secret" not in str(result)


def test_silent_model_discovery_has_a_deadline(local, cli, monkeypatch):
    fake_login(monkeypatch, "import time; time.sleep(60)")
    with pytest.raises(RuntimeError, match="timed out"):
        codex_models._catalogue(timeout=0.1)


@pytest.mark.parametrize("text,expected", [("gpt-x model is not supported secret", "Choose a listed model"), ("usage limit secret", "usage limit reached"), ("invalid schema secret", "output schema"), ("access is denied secret", "permissions"), ("401 unauthorized secret", "sign-in needs renewal")])
def test_generation_errors_are_actionable_without_exposing_raw_output(text, expected):
    message = authoring.failure_reason(text)
    assert expected in message
    assert "secret" not in message
