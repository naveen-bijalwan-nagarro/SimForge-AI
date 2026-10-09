"""Local administrator UI bridge for the official Codex OAuth flows.

Only transient, owner-scoped URLs/codes are exposed. Tokens and CLI output are
never persisted or returned. One login may use the local CLI profile at a time.
"""

import re
import secrets
import subprocess
import threading
import time
from urllib.parse import urlsplit

from . import authoring, settings

LOGIN_TIMEOUT = 15 * 60
_LOCK = threading.RLock()
_SESSION = None
_PUBLIC = ("id", "method", "status", "message", "auth_url", "device_code", "expires_at")
_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _local_only():
    if settings.PRODUCTION:
        raise RuntimeError("Local Codex account controls are disabled in production. Configure the service account on the server.")


def _view(session):
    return {key: session.get(key) for key in _PUBLIC}


def current(owner):
    with _LOCK:
        if _SESSION is None or _SESSION["owner"] != owner:
            return None
        return _view(_SESSION)


def _finish(session, status, message):
    session.update(status=status, message=message, auth_url=None, device_code=None)


def _read(session):
    proc = session["process"]
    text = ""
    try:
        for line in proc.stdout:
            text = (text + _ANSI.sub("", line))[-16000:]
            with _LOCK:
                if session["status"] != "pending":
                    continue
                for url in re.findall(r"https://[^\s<>\"']+", text):
                    parts = urlsplit(url)
                    if parts.hostname == "auth.openai.com" and parts.port in (None, 443) and not parts.username and parts.path in {"/oauth/authorize", "/codex/device"}:
                        session["auth_url"] = url
                if session["method"] == "device":
                    code = re.search(r"\b[A-Z0-9]{4,5}-[A-Z0-9]{4,5}\b", text)
                    if code:
                        session["device_code"] = code.group()
                if session["auth_url"]:
                    session["message"] = "Complete sign-in on the official OpenAI page. This panel checks automatically."
                # Keep diagnostics categorical: output can contain keys and local paths.
                lower = text.lower()
                if "device" in lower and ("disabled" in lower or "enable" in lower or "403" in lower):
                    session["failure_hint"] = "Device sign-in is unavailable. Enable device login in ChatGPT security settings or choose browser sign-in."
                elif "1455" in lower and ("in use" in lower or "bind" in lower):
                    session["failure_hint"] = "The browser callback port is busy. Cancel other Codex sign-in windows or use device sign-in."
    except (OSError, ValueError):
        pass


def _watch(session, reader):
    proc = session["process"]
    try:
        proc.wait(timeout=LOGIN_TIMEOUT)
        reader.join(timeout=2)
        with _LOCK:
            pending = session["status"] == "pending"
        if pending:
            state = authoring.probe(refresh=True) if proc.returncode == 0 else None
            with _LOCK:
                if session["status"] == "pending":
                    if state and state["authenticated"]:
                        from . import codex_models
                        codex_models.invalidate()
                        _finish(session, "authenticated", "Codex is signed in. You can generate scenarios from the UI.")
                    else:
                        _finish(session, "failed", session.get("failure_hint", "Codex sign-in did not complete. Retry browser sign-in or device sign-in."))
    except subprocess.TimeoutExpired:
        authoring.terminate(proc)
        with _LOCK:
            if session["status"] == "pending":
                _finish(session, "expired", "Sign-in timed out. Start a new sign-in from this panel.")
    finally:
        reader.join(timeout=2)
        if not reader.is_alive():
            proc.stdout.close()


def start(owner, method="browser"):
    global _SESSION
    _local_only()
    with _LOCK:
        if _SESSION and _SESSION["status"] == "pending":
            if _SESSION["owner"] != owner:
                raise RuntimeError("Another administrator is signing in to the local Codex profile")
            return _view(_SESSION)
        if authoring.probe(refresh=True)["authenticated"]:
            _SESSION = dict(id=secrets.token_hex(12), owner=owner, method=method)
            _finish(_SESSION, "authenticated", "The local Codex CLI is already signed in.")
            return _view(_SESSION)
        args = ["login"] + (["--device-auth"] if method == "device" else [])
        try:
            proc = subprocess.Popen(
                authoring.command(args), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            raise RuntimeError("Could not start the local Codex login process. Check the CLI installation and permissions.") from exc
        _SESSION = dict(id=secrets.token_hex(12), owner=owner, method=method, process=proc,
                        status="pending", message="Waiting for the official OpenAI sign-in link…",
                        auth_url=None, device_code=None, expires_at=time.time() + LOGIN_TIMEOUT)
        reader = threading.Thread(target=_read, args=(_SESSION,), daemon=True)
        reader.start()
        threading.Thread(target=_watch, args=(_SESSION, reader), daemon=True).start()
        return _view(_SESSION)


def cancel(owner):
    _local_only()
    with _LOCK:
        if not _SESSION or _SESSION["owner"] != owner:
            raise RuntimeError("No sign-in belongs to this administrator")
        if _SESSION["status"] == "pending":
            _finish(_SESSION, "cancelled", "Sign-in cancelled. You can start again.")
            proc = _SESSION["process"]
            if proc.poll() is None:
                authoring.terminate(proc)
        return _view(_SESSION)


def logout(owner):
    _local_only()
    with _LOCK:
        if _SESSION and _SESSION["status"] == "pending":
            if _SESSION["owner"] != owner:
                raise RuntimeError("Another administrator is signing in to this profile")
            cancel(owner)
        result = authoring._run(["logout"])
        if result is None or result.returncode:
            raise RuntimeError("Codex could not sign out. Check local CLI permissions and retry.")
        if _SESSION:
            _finish(_SESSION, "signed_out", "Signed out of the local Codex profile.")
        from . import codex_models
        codex_models.invalidate()
        return authoring.status(refresh=True)


def shutdown():
    with _LOCK:
        if _SESSION and _SESSION["status"] == "pending":
            _finish(_SESSION, "cancelled", "The backend stopped. Start sign-in again after restart.")
            proc = _SESSION["process"]
            if proc.poll() is None:
                authoring.terminate(proc)
