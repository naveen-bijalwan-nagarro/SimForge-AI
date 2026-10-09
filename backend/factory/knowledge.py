"""SOP knowledge base: sanitized chunks with hybrid lexical + vector retrieval.

Default storage is the application's SQLite database with deterministic hashed embeddings
(no model download). If ``SIMFORGE_PGVECTOR_DSN`` is set and ``psycopg`` is installed, chunks
and vectors are also written to PostgreSQL + pgvector and searched there.
"""

import hashlib
import json
import math
import os
import re
from collections import Counter

from .. import store

DIM = 384
TOKEN = re.compile(r"[a-z][a-z0-9_]+")
STOP = set("the a an and or of to in on for with by is are be as at this that from it its if then when within".split())


def tokens(text):
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP]


def embed(text):
    """Feature-hashed TF-IDF-like vector with unigrams and bigrams, L2-normalized."""
    vec = [0.0] * DIM
    toks = tokens(text)
    grams = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
    for g, n in Counter(grams).items():
        h = int(hashlib.md5(g.encode()).hexdigest()[:8], 16)
        vec[h % DIM] += (1 if (h >> 9) & 1 else -1) * (1 + math.log(n))
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm, 5) for v in vec]


def chunk(text, size=700):
    """Split on headings/steps first, then pack paragraphs up to ``size`` characters."""
    blocks = re.split(r"\n(?=#+ |\s*(?:step\s*)?\d+[.)]\s)", text, flags=re.I)
    chunks, current = [], ""
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if len(current) + len(block) > size and current:
            chunks.append(current)
            current = block
        else:
            current = f"{current}\n{block}".strip()
    if current:
        chunks.append(current)
    return chunks


def initialize():
    with store.connection() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS sop_chunks(id INTEGER PRIMARY KEY AUTOINCREMENT, sop_id TEXT NOT NULL, ord INTEGER NOT NULL, text TEXT NOT NULL, vector TEXT NOT NULL)"
        )
        db.execute("CREATE INDEX IF NOT EXISTS sop_chunk_doc ON sop_chunks(sop_id, ord)")


def _pg():
    dsn = os.getenv("SIMFORGE_PGVECTOR_DSN")
    if not dsn:
        return None
    try:
        import psycopg  # type: ignore
    except ImportError:
        return None
    conn = psycopg.connect(dsn, autocommit=True)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.execute(f"CREATE TABLE IF NOT EXISTS simforge_sop_chunks(id bigserial primary key, sop_id text, ord int, text text, embedding vector({DIM}))")
    return conn


def backend_name():
    return "PostgreSQL + pgvector" if os.getenv("SIMFORGE_PGVECTOR_DSN") else "SQLite + hashed vectors (BM25 hybrid)"


def index(sop_id, text):
    initialize()
    parts = chunk(text)
    with store.connection() as db:
        db.execute("DELETE FROM sop_chunks WHERE sop_id=?", (sop_id,))
        db.executemany(
            "INSERT INTO sop_chunks(sop_id,ord,text,vector) VALUES(?,?,?,?)",
            [(sop_id, i, c, json.dumps(embed(c))) for i, c in enumerate(parts)],
        )
    conn = _pg()
    if conn:
        with conn:
            conn.execute("DELETE FROM simforge_sop_chunks WHERE sop_id=%s", (sop_id,))
            for i, c in enumerate(parts):
                conn.execute("INSERT INTO simforge_sop_chunks(sop_id,ord,text,embedding) VALUES(%s,%s,%s,%s)", (sop_id, i, c, str(embed(c))))
    return len(parts)


def search(query, sop_id=None, k=5):
    initialize()
    conn = _pg()
    if conn:
        with conn:
            rows = conn.execute(
                "SELECT sop_id, ord, text, 1 - (embedding <=> %s::vector) AS score FROM simforge_sop_chunks "
                + ("WHERE sop_id=%s " if sop_id else "")
                + "ORDER BY embedding <=> %s::vector LIMIT %s",
                (str(embed(query)), *( [sop_id] if sop_id else []), str(embed(query)), k),
            ).fetchall()
        return [dict(sop_id=r[0], ord=r[1], text=r[2], score=round(float(r[3]), 4)) for r in rows]
    with store.connection() as db:
        rows = db.execute(
            "SELECT sop_id, ord, text, vector FROM sop_chunks" + (" WHERE sop_id=?" if sop_id else ""),
            (sop_id,) if sop_id else (),
        ).fetchall()
    if not rows:
        return []
    q_tokens, q_vec = tokens(query), embed(query)
    docs = [tokens(r["text"]) for r in rows]
    avg = sum(len(d) for d in docs) / len(docs)
    df = Counter(t for d in docs for t in set(d))
    scored = []
    for r, d in zip(rows, docs):
        tf = Counter(d)
        bm25 = sum(
            math.log(1 + (len(docs) - df[t] + 0.5) / (df[t] + 0.5)) * tf[t] * 2.2 / (tf[t] + 1.2 * (0.25 + 0.75 * len(d) / max(avg, 1)))
            for t in q_tokens
            if t in tf
        )
        cosine = sum(a * b for a, b in zip(q_vec, json.loads(r["vector"])))
        scored.append((0.6 * bm25 / (1 + bm25) + 0.4 * max(0.0, cosine), r))
    scored.sort(key=lambda x: -x[0])
    return [dict(sop_id=r["sop_id"], ord=r["ord"], text=r["text"], score=round(s, 4)) for s, r in scored[:k]]
