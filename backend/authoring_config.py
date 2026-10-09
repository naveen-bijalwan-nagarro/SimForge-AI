"""Read a private server-only API backup file without exporting secrets to children."""

import os
import re
import stat
import tomllib
from pathlib import Path

from . import settings


def path():
    return Path(os.getenv("SIMFORGE_AUTHORING_CONFIG") or settings.DATA / "secrets" / "authoring.local.toml")


def backup():
    target = path()
    try:
        if not target.exists():
            return {}
        if target.is_symlink() or not target.is_file() or target.stat().st_size > 4096:
            raise ValueError
        with target.open("rb") as source:
            raw = source.read(4097)
        if len(raw) > 4096:
            raise ValueError
        document = tomllib.loads(raw.decode("utf-8"))
        config = document.get("openai_backup", {})
        key, model = config.get("api_key", ""), config.get("model", "gpt-4.1-mini")
        if not isinstance(key, str) or not isinstance(model, str):
            raise ValueError
        if key and (not 20 <= len(key) <= 512 or any(c.isspace() for c in key)):
            raise ValueError
        if not re.fullmatch(r"[a-zA-Z0-9._:-]{1,100}", model):
            raise ValueError
        if key and os.name != "nt" and stat.S_IMODE(target.stat().st_mode) & 0o077:
            return {"error": "API backup file must be owner-only (chmod 600) before use."}
        return {"key": key, "model": model}
    except (OSError, ValueError, TypeError, AttributeError):
        # TOML parse errors can contain source values. Never forward them or the file.
        return {"error": "Cannot read valid private API backup settings. Check the server configuration file."}
