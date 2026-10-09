import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from . import settings


@contextmanager
def connection():
    settings.DATA.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(settings.DATA / "simforge.sqlite3"), timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000).hex()
    return salt + ":" + digest


def initialize():
    with connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, password TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS resources(id TEXT PRIMARY KEY,kind TEXT NOT NULL,owner TEXT NOT NULL REFERENCES users(id),payload TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 0,created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT NOT NULL,action TEXT NOT NULL,detail TEXT NOT NULL,created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS login_attempts(client TEXT NOT NULL,created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS resource_kind ON resources(kind,created);
        CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT NOT NULL REFERENCES users(id),scenario_key TEXT NOT NULL,title TEXT NOT NULL,message TEXT NOT NULL,seen INTEGER NOT NULL DEFAULT 0,created REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS notification_user ON notifications(user_id,id);
        """)
        if settings.PRODUCTION:
            if db.execute("SELECT 1 FROM metadata WHERE key='development_seeded'").fetchone():
                raise RuntimeError(
                    "Production requires a fresh data directory; this database contains development accounts"
                )
            if not db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                password = os.getenv("SIMFORGE_ADMIN_PASSWORD", "")
                if len(password) < 14:
                    raise RuntimeError(
                        "Set SIMFORGE_ADMIN_PASSWORD to at least 14 characters for initial production setup"
                    )
                db.execute(
                    "INSERT INTO users VALUES(?,?,?,?)",
                    ("admin", "Administrator", "admin", password_hash(password)),
                )
            if db.execute("SELECT 1 FROM users WHERE id IN ('learner','trainer')").fetchone():
                raise RuntimeError(
                    "Production requires a fresh data directory; development demo users are present"
                )
        else:
            db.execute("INSERT OR IGNORE INTO metadata VALUES('development_seeded','true')")
            for role in ("admin", "learner"):
                db.execute(
                    "INSERT OR IGNORE INTO users VALUES(?,?,?,?)",
                    (role, "Admin / Trainer" if role == "admin" else role.title(), role, password_hash(role + "123")),
                )


        retired = db.execute("SELECT id FROM users WHERE role='trainer'").fetchall()
        for row in retired:
            db.execute("UPDATE users SET role='learner' WHERE id=?", (row["id"],))
            db.execute("DELETE FROM sessions WHERE user_id=?", (row["id"],))
            db.execute("INSERT INTO audit(user_id,action,detail,created) VALUES(?,?,?,?)",
                       (row["id"], "role.migrate", "Retired trainer role converted to learner; records preserved; no privilege escalation", time.time()))
        db.execute("INSERT OR REPLACE INTO metadata VALUES('role_model','admin_learner_v1')")


def authenticate(username, password, client):
    with connection() as db:
        now = time.time()
        db.execute("DELETE FROM login_attempts WHERE created<?", (now - 60,))
        if (
            db.execute("SELECT COUNT(*) FROM login_attempts WHERE client=?", (client,)).fetchone()[
                0
            ]
            >= 10
        ):
            return "limited"
        db.execute("INSERT INTO login_attempts VALUES(?,?)", (client, now))
        user = db.execute("SELECT * FROM users WHERE id=?", (username,)).fetchone()
        # Always perform a password derivation to avoid a fast unknown-user path.
        expected = user["password"] if user else "0" * 32 + ":" + "0" * 64
        if not hmac.compare_digest(password_hash(password, expected.split(":")[0]), expected):
            return None
        token = secrets.token_urlsafe(32)
        db.execute("DELETE FROM sessions WHERE expires<?", (now,))
        db.execute(
            "INSERT INTO sessions VALUES(?,?,?)",
            (hashlib.sha256(token.encode()).hexdigest(), user["id"], now + 28800),
        )
        return token


def session_user(token):
    with connection() as db:
        row = db.execute(
            "SELECT u.id,u.name,u.role FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires>?",
            (hashlib.sha256(token.encode()).hexdigest(), time.time()),
        ).fetchone()
        return dict(row) if row else None


def audit(user, action, detail):
    with connection() as db:
        db.execute(
            "INSERT INTO audit(user_id,action,detail,created) VALUES(?,?,?,?)",
            (user, action, detail[:500], time.time()),
        )


def create(kind, owner, payload):
    rid = secrets.token_hex(12)
    with connection() as db:
        db.execute(
            "INSERT INTO resources(id,kind,owner,payload,created) VALUES(?,?,?,?,?)",
            (rid, kind, owner, json.dumps(payload), time.time()),
        )
    return rid


def get(rid, kind=None):
    with connection() as db:
        row = db.execute("SELECT * FROM resources WHERE id=?", (rid,)).fetchone()
        if row and (kind is None or row["kind"] == kind):
            return dict(row, id=row["id"], payload=json.loads(row["payload"]))
    return None


def list_resources(kind, user=None):
    with connection() as db:
        rows = db.execute(
            "SELECT * FROM resources WHERE kind=? ORDER BY created DESC LIMIT 200", (kind,)
        ).fetchall()
        return [
            dict(r, payload=json.loads(r["payload"]))
            for r in rows
            if user is None or user["role"] == "admin" or r["owner"] == user["id"]
        ]


def update(rid, payload, version):
    with connection() as db:
        changed = db.execute(
            "UPDATE resources SET payload=?,version=version+1 WHERE id=? AND version=?",
            (json.dumps(payload), rid, version),
        ).rowcount
        return bool(changed)


def list_active_resources(kind, user=None):
    # Filter before LIMIT so archived history cannot push fresh items out of the queue.
    with connection() as db:
        rows = db.execute(
            "SELECT * FROM resources WHERE kind=? AND json_extract(payload,'$.archived') IS NULL "
            "ORDER BY created DESC LIMIT 200", (kind,),
        ).fetchall()
        return [dict(r, payload=json.loads(r["payload"])) for r in rows
                if user is None or user["role"] == "admin" or r["owner"] == user["id"]]


def recover_interrupted_jobs():
    """Fail orphaned in-process jobs on single-worker startup, without replaying model calls.

    Keep their inputs, events and completed steps for review. Simulations and drafts are
    not background jobs and must remain untouched. Call once before serving requests.
    """
    message = "Interrupted by a server restart. Review the saved inputs and start a new job."
    with connection() as db:
        rows = db.execute(
            "SELECT id,payload FROM resources "
            "WHERE kind IN ('authoring_job','sandbox_job','factory_job') "
            "AND json_extract(payload,'$.status') IN ('running','queued')"
        ).fetchall()
        for row in rows:
            payload = json.loads(row["payload"])
            payload.update(status="failed", message=message, error=message, finished=time.time())
            for step in payload.get("steps", []):
                if step.get("status") == "running":
                    step.update(status="failed", detail=message, finished=payload["finished"])
            db.execute(
                "UPDATE resources SET payload=?,version=version+1 WHERE id=?",
                (json.dumps(payload), row["id"]),
            )
        return len(rows)


def notify(user_ids, scenario_key, title, message, db=None):
    def insert(conn):
        conn.executemany(
            "INSERT INTO notifications(user_id,scenario_key,title,message,created) VALUES(?,?,?,?,?)",
            [(uid, scenario_key, title, message, time.time()) for uid in user_ids],
        )

    if db is not None:
        insert(db)
    else:
        with connection() as conn:
            insert(conn)
