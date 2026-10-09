"""Read the installed CLI's model catalogue over its documented stdio protocol."""
import json
import queue
import re
import subprocess
import threading
import time

from . import authoring

_LOCK = threading.Lock()
_CACHE = dict(key=None, at=0, value=None)


def invalidate():
    _CACHE.update(key=None, at=0, value=None)


def cached():
    key = (authoring.executable(), authoring.os.getenv("CODEX_HOME"))
    return _CACHE["value"] if _CACHE["key"] == key and time.monotonic() - _CACHE["at"] < 300 else None


def _catalogue(timeout=25):
    proc = subprocess.Popen(authoring.command(["app-server"]), stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                            encoding="utf-8", errors="replace",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    lines = queue.Queue(maxsize=100)
    def read():
        try:
            while line := proc.stdout.readline(128_000):
                try:
                    lines.put_nowait(line)
                except queue.Full:
                    pass
        finally:
            try:
                lines.put_nowait(None)
            except queue.Full:
                pass
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    deadline = time.monotonic() + timeout
    def send(message):
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()
    def request(id, method, params):
        send(dict(id=id, method=method, params=params))
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("Codex model discovery timed out. Check the CLI's network access and retry.")
            try:
                line = lines.get(timeout=remaining)
            except queue.Empty as exc:
                raise RuntimeError("Codex model discovery timed out. Refresh models to retry.") from exc
            if line is None:
                raise RuntimeError("Codex closed model discovery. Check the local CLI installation.")
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and obj.get("id") == id:
                if obj.get("error"):
                    raise RuntimeError("The installed Codex CLI could not list its models. Update the CLI or retry after sign-in.")
                return obj.get("result") or {}
    try:
        request(1, "initialize", dict(clientInfo=dict(name="simforge_ai", title="SimForge AI", version="2.0.0")))
        send(dict(method="initialized", params={}))
        items, cursor = [], None
        for page in range(5):
            params = dict(limit=100, includeHidden=False)
            if cursor:
                params["cursor"] = cursor
            data = request(2 + page, "model/list", params)
            items.extend(data.get("data", []))
            cursor = data.get("nextCursor")
            if not cursor:
                break
        configured = request(10, "config/read", dict(includeLayers=False)).get("config", {})
        models = []
        for item in items:
            model = item.get("model") or item.get("id")
            if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,100}", model):
                continue
            efforts = [e.get("reasoningEffort") for e in item.get("supportedReasoningEfforts", []) if isinstance(e, dict)]
            efforts = [e for e in efforts if isinstance(e, str) and re.fullmatch(r"[a-z]{1,20}", e)]
            models.append(dict(id=model, label=item.get("displayName") or model,
                               default=bool(item.get("isDefault")), efforts=efforts,
                               default_effort=item.get("defaultReasoningEffort")))
        return dict(models=models, configured_model=configured.get("model"),
                    configured_effort=configured.get("model_reasoning_effort"))
    finally:
        authoring.terminate(proc)
        reader.join(timeout=2)
        if not reader.is_alive():
            proc.stdout.close()
        proc.stdin.close()


def catalogue(refresh=False):
    with _LOCK:
        value = cached()
        if value and not refresh:
            return value
        try:
            value = _catalogue()
        except OSError as exc:
            raise RuntimeError("Could not start Codex model discovery. Check local permissions.") from exc
        _CACHE.update(key=(authoring.executable(), authoring.os.getenv("CODEX_HOME")), at=time.monotonic(), value=value)
        return value
