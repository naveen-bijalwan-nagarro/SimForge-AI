"""Recoverable archive of the custom publication queue; never delete learner data."""

import hashlib
import json
import secrets
import time

from fastapi import HTTPException

from . import store

KINDS = ("scenario", "scenario_draft", "authoring_job")


def active_rows(db):
    return [dict(r, payload=json.loads(r["payload"])) for r in db.execute(
        "SELECT * FROM resources WHERE kind IN ('scenario','scenario_draft','authoring_job') "
        "AND json_extract(payload,'$.archived') IS NULL ORDER BY id",
    )]


def fingerprint(rows):
    return hashlib.sha256(json.dumps([(r["id"], r["version"]) for r in rows]).encode()).hexdigest()


def plan():
    with store.connection() as db:
        rows = active_rows(db)
        history = [dict(id=r["id"], **json.loads(r["payload"])) for r in db.execute(
            "SELECT id,payload FROM resources WHERE kind='scenario_archive' ORDER BY created DESC LIMIT 10",
        )]
    return dict(token=fingerprint(rows), counts={k: sum(r["kind"] == k for r in rows) for k in KINDS},
                records=[dict(id=r["id"], kind=r["kind"], title=r["payload"].get("title") or
                              r["payload"].get("definition", {}).get("title", "Generation job")) for r in rows],
                history=history)


def archive(token, actor):
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        rows = active_rows(db)
        if token != fingerprint(rows):
            raise HTTPException(409, "Queue changed; review the cleanup preview again")
        if any(r["payload"].get("status") in {"running", "queued"} for r in rows):
            raise HTTPException(409, "Wait for active scenario generation before cleanup")
        if not rows:
            return dict(id=None, count=0)
        batch = secrets.token_hex(12)
        for row in rows:
            p = row["payload"]
            p["archived"] = dict(batch=batch, by=actor, at=time.time())
            db.execute("UPDATE resources SET payload=?,version=version+1 WHERE id=?",
                       (json.dumps(p), row["id"]))
        payload = dict(ids=[r["id"] for r in rows], count=len(rows), restored=False, by=actor, at=time.time())
        db.execute("INSERT INTO resources(id,kind,owner,payload,created) VALUES(?,?,?,?,?)",
                   (batch, "scenario_archive", actor, json.dumps(payload), time.time()))
        db.execute("INSERT INTO audit(user_id,action,detail,created) VALUES(?,?,?,?)",
                   (actor, "scenario.archive", f"{len(rows)} records archived; batch {batch}", time.time()))
    return dict(id=batch, count=len(rows))


def restore(batch, actor):
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT payload FROM resources WHERE id=? AND kind='scenario_archive'", (batch,)).fetchone()
        if not row:
            raise HTTPException(404, "Archive not found")
        payload = json.loads(row[0])
        if payload["restored"]:
            raise HTTPException(409, "Archive already restored")
        for rid in payload["ids"]:
            raw = db.execute("SELECT payload FROM resources WHERE id=?", (rid,)).fetchone()
            p = json.loads(raw[0]) if raw else {}
            if p.get("archived", {}).get("batch") != batch:
                raise HTTPException(409, "Archived record changed; restore blocked")
            del p["archived"]
            db.execute("UPDATE resources SET payload=?,version=version+1 WHERE id=?", (json.dumps(p), rid))
        payload.update(restored=True, restored_by=actor, restored_at=time.time())
        db.execute("UPDATE resources SET payload=?,version=version+1 WHERE id=?", (json.dumps(payload), batch))
        db.execute("INSERT INTO audit(user_id,action,detail,created) VALUES(?,?,?,?)",
                   (actor, "scenario.restore", batch, time.time()))
    return dict(count=payload["count"])


def retired_keys():
    with store.connection() as db:
        return {json.loads(r[0])["key"] for r in db.execute(
            "SELECT payload FROM resources WHERE kind='scenario' AND json_extract(payload,'$.archived') IS NOT NULL",
        )}
