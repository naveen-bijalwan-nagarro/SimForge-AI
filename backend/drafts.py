"""Shared draft persistence and provenance; publication is an administrator action."""

import json
import secrets
import time

from . import store


def view(row):
    return dict(
        **row["payload"],
        id=row["id"],
        owner=row["owner"],
        version=row["version"],
        created=row["created"],
    )


def save(payload, owner):
    rid = secrets.token_hex(12)
    title = payload["definition"]["title"]
    with store.connection() as db:
        db.execute(
            "INSERT INTO resources(id,kind,owner,payload,created) VALUES(?,?,?,?,?)",
            (rid, "scenario_draft", owner, json.dumps(payload), time.time()),
        )
        db.execute(
            "INSERT INTO audit(user_id,action,detail,created) VALUES(?,?,?,?)",
            (owner, "scenario.draft", f"{payload['source']}: {title}"[:500], time.time()),
        )
    return view(store.get(rid, "scenario_draft"))
