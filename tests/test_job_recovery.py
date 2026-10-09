"""Background jobs must terminate visibly, even after a crash or a silent CLI."""

import copy
import subprocess
import sys
import time

import pytest
import yaml
from fastapi.testclient import TestClient

from backend import codex_sandbox, main, settings, store


@pytest.fixture
def job_store(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA", tmp_path)
    monkeypatch.setattr(settings, "PRODUCTION", False)
    store.initialize()
    return tmp_path


@pytest.mark.parametrize("kind", ["authoring_job", "sandbox_job", "factory_job"])
@pytest.mark.parametrize("status", ["running", "queued"])
def test_startup_recovers_only_interrupted_jobs(job_store, kind, status):
    payload = dict(
        status=status,
        prompt="Keep these synthetic requirements",
        events=[{"detail": "Earlier progress"}],
        steps=[dict(key="plan", status="completed"), dict(key="design", status="running")],
    )
    rid = store.create(kind, "admin", payload)
    retained = {
        store.create(kind, "admin", dict(status=s, draft_id="keep-me")): s
        for s in ["ready", "completed", "failed", "awaiting_approval", "approved", "blocked"]
    }
    run_id = store.create("run", "learner", dict(status="running", tick=12))
    draft_id = store.create("scenario_draft", "admin", dict(status="draft"))
    with TestClient(main.app):
        recovered = store.get(rid)
        assert recovered["version"] == 1
        assert recovered["payload"]["status"] == "failed"
        assert "server restart" in recovered["payload"]["error"]
        assert recovered["payload"]["prompt"] == payload["prompt"]
        assert recovered["payload"]["events"] == payload["events"]
        assert recovered["payload"]["steps"][0]["status"] == "completed"
        assert recovered["payload"]["steps"][1]["status"] == "failed"
        assert store.recover_interrupted_jobs() == 0
        for key, expected in retained.items():
            assert store.get(key)["payload"]["status"] == expected
            assert store.get(key)["version"] == 0
        assert store.get(run_id)["payload"] == dict(status="running", tick=12)
        assert store.get(draft_id)["payload"] == dict(status="draft")


def test_recovery_is_not_limited_to_resource_list_page(job_store):
    for _ in range(205):
        store.create("authoring_job", "admin", dict(status="running"))
    assert store.recover_interrupted_jobs() == 205


def run_fake_cli(monkeypatch, script):
    real_popen = subprocess.Popen
    children = []

    def start(_args, **kwargs):
        child = real_popen([sys.executable, "-u", "-c", script], **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(codex_sandbox.subprocess, "Popen", start)
    monkeypatch.setattr(codex_sandbox.authoring, "executable", lambda: "test-codex")
    return children


def test_silent_codex_process_obeys_deadline(job_store, monkeypatch):
    children = run_fake_cli(monkeypatch, "import sys, time; sys.stdin.read(); time.sleep(30)")
    rid = store.create("sandbox_job", "admin", dict(status="running", events=[]))
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="time limit"):
        codex_sandbox.run_codex(rid, codex_sandbox.WIZARD["example"], timeout=0.3)
    assert time.monotonic() - started < 8
    assert children[0].poll() is not None


@pytest.mark.parametrize("exit_code,event", [(1, "{}"), (0, '{"type":"turn.failed","error":{"message":"usage limit reached"}}')])
def test_failed_codex_never_accepts_a_partial_draft(job_store, monkeypatch, exit_code, event):
    run_fake_cli(
        monkeypatch,
        f"import sys; sys.stdin.read(); print({event!r}, flush=True); sys.exit({exit_code})",
    )
    rid = store.create("sandbox_job", "admin", dict(status="running", events=[]))
    drafts = job_store / "codex_workspaces" / rid / "drafts"
    drafts.mkdir(parents=True)
    (drafts / "partial.yaml").write_text("title: Unfinished draft", encoding="utf-8")
    with pytest.raises(RuntimeError, match="unsuccessfully|usage limit"):
        codex_sandbox.run_codex(rid, codex_sandbox.WIZARD["example"], timeout=10)


def test_successful_codex_stream_preserves_events_and_yaml(job_store, monkeypatch):
    run_fake_cli(monkeypatch, 'import sys; sys.stdin.read(); print(\'{"type":"item.completed","item":{"type":"agent_message","text":"Draft validated"}}\', flush=True)')
    rid = store.create("sandbox_job", "admin", dict(status="running", events=[]))
    drafts = job_store / "codex_workspaces" / rid / "drafts"
    drafts.mkdir(parents=True)
    pack = codex_sandbox.guided_pack(copy.deepcopy(codex_sandbox.WIZARD["example"]))
    (drafts / "complete.yaml").write_text(yaml.safe_dump(pack), encoding="utf-8")
    generated, message = codex_sandbox.run_codex(rid, codex_sandbox.WIZARD["example"], timeout=10)
    assert generated == pack
    assert message == "Draft validated"
    assert store.get(rid)["payload"]["events"][0]["text"] == message
