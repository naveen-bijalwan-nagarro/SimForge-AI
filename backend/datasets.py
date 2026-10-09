"""Dataset Studio: schema-driven synthetic data with controlled anomalies and ground truth.

A schema is plain JSON (tables → columns → generators) that users can read, edit and
validate. Generation is deterministic from the schema and seed, so only the schema needs to
be stored. Anomalies are injected after generation and every affected row is recorded in
``ground_truth.json`` so detectors, analysts or agents can be scored objectively.
"""

import ast
import copy
import csv
import hashlib
import io
import json
import math
import random
import re
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker

from . import vision
from .connections import SHARED_KINDS, registry, shared_id
from .evidence import sensor_profile

MAX_TABLES, MAX_COLUMNS, MAX_ROWS, MAX_CELLS, MAX_IMAGES = 12, 40, 20000, 400000, 200
COLUMN_TYPES = {
    "id": "Sequential identifier: prefix + number (prefix)",
    "int": "Whole numbers (min, max, dist: uniform|normal|poisson, mean, std, lam)",
    "float": "Decimals (min, max, dist: uniform|normal|lognormal|exponential, mean, std, sigma, decimals)",
    "bool": "True/False with probability p",
    "category": "One of values, optionally weighted",
    "datetime": "Timestamp between start and end, or sequential with step_minutes",
    "date": "Calendar date between start and end",
    "text": "Template text, e.g. 'Order {order_id} for {region}' or '{choice:low|high}'",
    "faker": "Realistic fake value from a Faker provider (name, company, email, city, sentence…)",
    "ref": "Foreign key: random value from table.column generated earlier",
    "shared": "ID from the shared cross-scenario master data (kind: Supplier, Machine…)",
    "formula": "Arithmetic of earlier columns, e.g. 'quantity * unit_price'",
    "series": "Time-series signal: base + amplitude·sin(2πi/period) + trend·i + noise",
    "label": "0/1 target from a logistic function of earlier numeric columns (weights, bias)",
    "image": "Synthetic labelled image (kind, defect_rate, lighting); adds defect columns",
}
ANOMALY_TYPES = {
    "missing": "Blank out a column for a fraction of rows (rate)",
    "duplicates": "Duplicate a fraction of rows with new IDs (rate)",
    "outliers": "Multiply values by factor for a fraction of rows (rate, factor)",
    "drift": "Shift a numeric column after start_fraction of rows (shift, optional where)",
    "label_flip": "Flip a 0/1 or boolean label for a fraction of rows (rate)",
    "unit_change": "Scale a column after start_fraction, e.g. dollars → cents (factor)",
    "stuck": "Freeze a sensor column at one value after start_fraction (where optional)",
    "delay": "Shift timestamps later by minutes for a fraction of rows (rate, minutes)",
    "fraud_ring": "Make a small group share one value in column and mark label=1 (size, label)",
}
FAKER_PROVIDERS = {
    "name",
    "first_name",
    "last_name",
    "company",
    "email",
    "safe_email",
    "city",
    "country",
    "street_address",
    "phone_number",
    "job",
    "sentence",
    "paragraph",
    "word",
    "iban",
    "ipv4",
    "user_name",
    "url",
    "color_name",
    "license_plate",
}
FUNCTIONS = {"min": min, "max": max, "round": round, "abs": abs, "log": math.log, "exp": math.exp, "sqrt": math.sqrt}
NAME = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


class SchemaError(ValueError):
    def __init__(self, problems):
        super().__init__("; ".join(problems[:5]))
        self.problems = problems


# ------------------------------------------------------------------ safe formula evaluation
ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Load, ast.Call,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv, ast.USub, ast.UAdd,
    ast.Compare, ast.Gt, ast.GtE, ast.Lt, ast.LtE, ast.Eq, ast.NotEq, ast.IfExp, ast.BoolOp,
    ast.And, ast.Or, ast.Not,
)


def compile_formula(expr):
    tree = ast.parse(str(expr), mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise ValueError(f"'{type(node).__name__}' is not allowed in formulas")
        if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS):
            raise ValueError(f"Only {', '.join(FUNCTIONS)} may be called in formulas")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise ValueError("Formulas may only contain numbers and column names")
    return compile(tree, "<formula>", "eval")


def formula_names(expr):
    return {n.id for n in ast.walk(ast.parse(str(expr), mode="eval")) if isinstance(n, ast.Name) and n.id not in FUNCTIONS}


def evaluate(code, row):
    values = {k: (v if isinstance(v, (int, float)) and not isinstance(v, bool) else 0) for k, v in row.items()}
    return eval(code, {"__builtins__": {}}, dict(FUNCTIONS, **values))  # noqa: S307 - AST-restricted


# ------------------------------------------------------------------ validation
def validate(schema):
    problems = []
    if not isinstance(schema, dict):
        return ["Schema must be a JSON object with 'tables'"]
    tables = schema.get("tables")
    if not isinstance(tables, list) or not tables:
        return ["Schema needs a non-empty 'tables' list"]
    if len(tables) > MAX_TABLES:
        problems.append(f"At most {MAX_TABLES} tables")
    seen, cells, images = {}, 0, 0
    for ti, table in enumerate(tables):
        where = f"tables[{ti}]"
        name = table.get("name", "")
        if not NAME.match(str(name)):
            problems.append(f"{where}.name '{name}' must be lowercase_snake_case")
        if name in seen:
            problems.append(f"{where}.name '{name}' is duplicated")
        data = table.get("data")
        rows = len(data) if isinstance(data, list) else table.get("rows")
        if not isinstance(rows, int) or not 1 <= rows <= MAX_ROWS:
            problems.append(f"{where}.rows must be 1-{MAX_ROWS}")
            rows = 0
        columns = table.get("columns", [])
        if not isinstance(columns, list) or (not columns and not data):
            problems.append(f"{where}.columns must list at least one column")
            columns = []
        if len(columns) > MAX_COLUMNS:
            problems.append(f"{where} has more than {MAX_COLUMNS} columns")
        cells += rows * max(1, len(columns))
        names = set(data[0].keys()) if data and isinstance(data[0], dict) else set()
        for ci, col in enumerate(columns):
            cw = f"{where}.columns[{ci}]"
            cname, ctype = col.get("name", ""), col.get("type")
            if not NAME.match(str(cname)):
                problems.append(f"{cw}.name '{cname}' must be lowercase_snake_case")
            if cname in names:
                problems.append(f"{cw}.name '{cname}' is duplicated")
            if ctype not in COLUMN_TYPES:
                problems.append(f"{cw}.type '{ctype}' is unknown. Use one of: {', '.join(COLUMN_TYPES)}")
                names.add(cname)
                continue
            if ctype == "category" and (not isinstance(col.get("values"), list) or not col["values"]):
                problems.append(f"{cw} category needs a non-empty 'values' list")
            if ctype == "category" and col.get("weights") and len(col["weights"]) != len(col.get("values", [])):
                problems.append(f"{cw} weights must match values")
            if ctype in {"int", "float"} and "min" in col and "max" in col and col["min"] > col["max"]:
                problems.append(f"{cw} min must not exceed max")
            if ctype == "ref":
                target = seen.get(col.get("table"))
                if target is None:
                    problems.append(f"{cw} references table '{col.get('table')}' which must be defined earlier")
                elif col.get("column") not in target:
                    problems.append(f"{cw} references unknown column '{col.get('table')}.{col.get('column')}'")
            if ctype == "shared" and col.get("kind") not in SHARED_KINDS:
                problems.append(f"{cw} shared kind must be one of {', '.join(SHARED_KINDS)}")
            if ctype == "faker" and col.get("provider") not in FAKER_PROVIDERS:
                problems.append(f"{cw} faker provider must be one of {', '.join(sorted(FAKER_PROVIDERS))}")
            if ctype == "formula":
                try:
                    compile_formula(col.get("expr", ""))
                    missing = formula_names(col.get("expr", "")) - names
                    if missing:
                        problems.append(f"{cw} formula uses unknown or later columns: {', '.join(sorted(missing))}")
                except (SyntaxError, ValueError) as e:
                    problems.append(f"{cw} formula error: {e}")
            if ctype == "label":
                unknown = set(col.get("weights", {})) - names
                if not col.get("weights"):
                    problems.append(f"{cw} label needs 'weights' of earlier numeric columns")
                if unknown:
                    problems.append(f"{cw} label weights use unknown columns: {', '.join(sorted(unknown))}")
            if ctype == "image":
                if col.get("kind") not in vision.KINDS:
                    problems.append(f"{cw} image kind must be one of {', '.join(vision.KINDS)}")
                images += rows
            if ctype == "datetime" and col.get("start"):
                try:
                    datetime.fromisoformat(str(col["start"]))
                except ValueError:
                    problems.append(f"{cw} start must be an ISO date/time such as 2026-09-01T00:00")
            names.add(cname)
        seen[name] = names
    if cells > MAX_CELLS:
        problems.append(f"Schema would generate {cells:,} cells; the limit is {MAX_CELLS:,}")
    if images > MAX_IMAGES:
        problems.append(f"At most {MAX_IMAGES} images per dataset")
    for ai, anomaly in enumerate(schema.get("anomalies", []) or []):
        aw = f"anomalies[{ai}]"
        if anomaly.get("type") not in ANOMALY_TYPES:
            problems.append(f"{aw}.type must be one of {', '.join(ANOMALY_TYPES)}")
            continue
        table = seen.get(anomaly.get("table"))
        if table is None:
            problems.append(f"{aw}.table '{anomaly.get('table')}' does not exist")
            continue
        if anomaly["type"] != "duplicates" and anomaly.get("column") not in table:
            problems.append(f"{aw}.column '{anomaly.get('column')}' does not exist in {anomaly.get('table')}")
        for key in (anomaly.get("where") or {}):
            if key not in table:
                problems.append(f"{aw}.where column '{key}' does not exist")
        rate = anomaly.get("rate", 0.05)
        if not isinstance(rate, (int, float)) or not 0 < rate <= 0.5:
            problems.append(f"{aw}.rate must be between 0 and 0.5")
    return problems


# ------------------------------------------------------------------ generation
def _seed(schema_seed, *parts):
    digest = hashlib.sha256(":".join(map(str, (schema_seed, *parts))).encode()).hexdigest()
    return int(digest[:12], 16)


def _value(col, i, row, rng, fake, generated, start_cache):
    t = col["type"]
    if t == "id":
        return f"{col.get('prefix', 'ID')}-{i + 1:0{col.get('width', 5)}d}"
    if t == "int":
        dist = col.get("dist", "uniform")
        if dist == "normal":
            v = round(rng.gauss(col.get("mean", 50), col.get("std", 10)))
        elif dist == "poisson":
            lam, k, p, limit = col.get("lam", 3), 0, 1.0, math.exp(-col.get("lam", 3))
            while True:
                p *= rng.random()
                if p <= limit or k > 10 * lam + 50:
                    break
                k += 1
            v = k
        else:
            v = rng.randint(int(col.get("min", 0)), int(col.get("max", 100)))
        if "min" in col:
            v = max(int(col["min"]), v)
        if "max" in col:
            v = min(int(col["max"]), v)
        return int(v)
    if t == "float":
        dist = col.get("dist", "uniform")
        if dist == "normal":
            v = rng.gauss(col.get("mean", 0.0), col.get("std", 1.0))
        elif dist == "lognormal":
            v = rng.lognormvariate(col.get("mean", 3.0), col.get("sigma", 0.8))
        elif dist == "exponential":
            v = rng.expovariate(1 / max(1e-9, col.get("mean", 1.0)))
        else:
            v = rng.uniform(col.get("min", 0.0), col.get("max", 1.0))
        if "min" in col:
            v = max(col["min"], v)
        if "max" in col:
            v = min(col["max"], v)
        return round(v, col.get("decimals", 3))
    if t == "bool":
        return rng.random() < col.get("p", 0.5)
    if t == "category":
        return rng.choices(col["values"], weights=col.get("weights"))[0]
    if t == "datetime":
        start = start_cache.setdefault(col["name"], datetime.fromisoformat(str(col.get("start", "2026-09-01T00:00"))))
        if col.get("step_minutes"):
            v = start + timedelta(minutes=col["step_minutes"] * (i // max(1, col.get("per_step", 1))))
        else:
            end = datetime.fromisoformat(str(col.get("end", "2026-09-28T00:00")))
            v = start + timedelta(seconds=rng.uniform(0, max(1, (end - start).total_seconds())))
        return v.strftime("%Y-%m-%dT%H:%M:%S")
    if t == "date":
        start = datetime.fromisoformat(str(col.get("start", "2026-01-01")))
        end = datetime.fromisoformat(str(col.get("end", "2026-09-28")))
        return (start + timedelta(days=rng.randint(0, max(0, (end - start).days)))).date().isoformat()
    if t == "text":
        text = re.sub(r"\{choice:([^}]*)\}", lambda m: rng.choice(m.group(1).split("|")), col.get("template", ""))
        return text.format_map(_SafeDict(row))
    if t == "faker":
        return str(getattr(fake, col["provider"])())
    if t == "ref":
        pool = generated[col["table"]]
        return rng.choice(pool)[col["column"]] if pool else None
    if t == "shared":
        return shared_id(col["kind"], rng)
    if t == "formula":
        v = evaluate(col["_code"], row)
        return round(v, col.get("decimals", 3)) if isinstance(v, float) else v
    if t == "series":
        idx = i % max(1, col.get("reset_every", 10**9))
        return round(
            col.get("base", 0.0)
            + col.get("amplitude", 1.0) * math.sin(2 * math.pi * idx / max(1, col.get("period", 24)))
            + col.get("trend", 0.0) * idx
            + rng.gauss(0, col.get("noise", 0.1)),
            col.get("decimals", 3),
        )
    if t == "label":
        z = col.get("bias", 0.0) + sum(float(row.get(k) or 0) * w for k, w in col["weights"].items())
        return int(rng.random() < 1 / (1 + math.exp(-max(-30, min(30, z)))))
    if t == "image":
        defect = rng.random() < col.get("defect_rate", 0.3)
        return dict(_image=True, defect=defect, seed=rng.randrange(10**8))
    return None


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def _matches(row, where):
    return all(row.get(k) == v for k, v in (where or {}).items())


def _inject(schema, tables, rng):
    truth = []
    for a in schema.get("anomalies", []) or []:
        rows = tables[a["table"]]
        col, rate = a.get("column"), a.get("rate", 0.05)
        id_col = next(iter(rows[0])) if rows else None
        eligible = [r for r in rows if _matches(r, a.get("where"))]
        start = int(len(eligible) * a.get("start_fraction", 0.0))
        affected = []
        kind = a["type"]
        if kind == "missing":
            for r in eligible:
                if rng.random() < rate:
                    r[col] = None
                    affected.append(r[id_col])
        elif kind == "duplicates":
            extra = []
            for r in eligible:
                if rng.random() < rate:
                    dup = dict(r)
                    dup[id_col] = f"{r[id_col]}-DUP"
                    extra.append(dup)
                    affected.append(dup[id_col])
            rows.extend(extra)
        elif kind == "outliers":
            for r in eligible:
                if isinstance(r.get(col), (int, float)) and not isinstance(r.get(col), bool) and rng.random() < rate:
                    r[col] = round(r[col] * a.get("factor", 6) + (a.get("factor", 6) if r[col] == 0 else 0), 3)
                    affected.append(r[id_col])
        elif kind in {"drift", "unit_change", "stuck"}:
            frozen = None
            for r in eligible[start:]:
                v = r.get(col)
                if not isinstance(v, (int, float)) or isinstance(v, bool):
                    continue
                if kind == "drift":
                    r[col] = round(v + a.get("shift", 1.0), 3)
                elif kind == "unit_change":
                    r[col] = round(v * a.get("factor", 100), 3)
                else:
                    frozen = v if frozen is None else frozen
                    r[col] = frozen
                affected.append(r[id_col])
        elif kind == "label_flip":
            for r in eligible:
                if rng.random() < rate and r.get(col) in (0, 1, True, False):
                    r[col] = (not r[col]) if isinstance(r[col], bool) else 1 - r[col]
                    affected.append(r[id_col])
        elif kind == "delay":
            for r in eligible:
                if rng.random() < rate and r.get(col):
                    ts = datetime.fromisoformat(r[col]) + timedelta(minutes=a.get("minutes", 60))
                    r[col] = ts.strftime("%Y-%m-%dT%H:%M:%S")
                    affected.append(r[id_col])
        elif kind == "fraud_ring":
            ring = rng.sample(eligible, min(len(eligible), a.get("size", 8) * 3))
            shared_value = f"RING-{rng.randint(100, 999)}"
            for r in ring:
                r[col] = shared_value
                if a.get("label") and a["label"] in r:
                    r[a["label"]] = 1
                affected.append(r[id_col])
        truth.append(dict(a, affected_rows=affected[:5000], count=len(affected)))
    return truth


def generate(schema, preview_rows=None):
    """Generate every table; images are described, not rendered, until export."""
    problems = validate(schema)
    if problems:
        raise SchemaError(problems)
    schema = copy.deepcopy(schema)
    seed = int(schema.get("seed", 2026))
    Faker.seed(seed)
    fake = Faker(schema.get("locale", "en_US"))
    tables = {}
    for table in schema["tables"]:
        rng = random.Random(_seed(seed, table["name"]))
        if isinstance(table.get("data"), list):
            tables[table["name"]] = [dict(r) for r in table["data"]]
            continue
        cols = table["columns"]
        for c in cols:
            if c["type"] == "formula":
                c["_code"] = compile_formula(c["expr"])
        count = table["rows"] if preview_rows is None else min(table["rows"], preview_rows)
        rows, start_cache = [], {}
        for i in range(count):
            row = {}
            for c in cols:
                v = _value(c, i, row, rng, fake, tables, start_cache)
                if isinstance(v, dict) and v.get("_image"):
                    row[c["name"]] = f"images/{table['name']}-{i + 1:05d}.png"
                    row[f"{c['name']}_defect"] = v["defect"]
                    row[f"_{c['name']}_seed"] = v["seed"]
                else:
                    row[c["name"]] = v
            rows.append(row)
        tables[table["name"]] = rows
    truth = _inject(schema, tables, random.Random(_seed(seed, "anomalies")))
    return tables, dict(schema=schema.get("name", "dataset"), seed=seed, anomalies=truth)


def public_rows(rows):
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]


def profile(tables):
    """Column statistics for the preview charts."""
    out = {}
    for name, rows in tables.items():
        rows = public_rows(rows)
        cols = {}
        for key in dict.fromkeys(k for r in rows[:1] for k in r):
            values = [r.get(key) for r in rows]
            present = [v for v in values if v is not None]
            numeric = [v for v in present if isinstance(v, (int, float)) and not isinstance(v, bool)]
            info = dict(missing=len(values) - len(present))
            if numeric and len(numeric) == len(present):
                lo, hi = min(numeric), max(numeric)
                bins = [0] * 12
                for v in numeric:
                    bins[min(11, int((v - lo) / ((hi - lo) or 1) * 12))] += 1
                info.update(kind="numeric", min=lo, max=hi, mean=round(sum(numeric) / len(numeric), 3), histogram=bins)
            else:
                counts = {}
                for v in present:
                    counts[str(v)] = counts.get(str(v), 0) + 1
                top = sorted(counts.items(), key=lambda kv: -kv[1])[:10]
                info.update(kind="categorical", distinct=len(counts), top=top)
            cols[key] = info
        out[name] = dict(rows=len(rows), columns=cols)
    return out


def _render_images(schema, tables):
    for table in schema["tables"]:
        for c in table.get("columns", []):
            if c["type"] != "image":
                continue
            for row in tables[table["name"]]:
                img, boxes = vision.render(
                    c["kind"], row[f"_{c['name']}_seed"], row[f"{c['name']}_defect"], c.get("severity", 0.7), c.get("lighting", 1.0), size=tuple(c.get("size", [320, 240]))
                )
                yield row[c["name"]], vision.png(img), boxes, row, c


def _csv(rows):
    out = io.StringIO(newline="")
    rows = public_rows(rows)
    if not rows:
        return ""
    fields = list(dict.fromkeys(k for r in rows for k in r))
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for r in rows:
        writer.writerow({k: ("'" + v if isinstance(v, str) and v[:1] in "=+-@" else v) for k, v in r.items()})
    return out.getvalue()


def data_card(schema, truth, tables):
    lines = [f"# {schema.get('name', 'Synthetic dataset')}", "", schema.get("description", ""), ""]
    lines += ["All records are synthetic and generated deterministically from `schema.json`.", ""]
    lines += ["## Tables", ""]
    for t in schema["tables"]:
        lines.append(f"### {t['name']} ({len(tables[t['name']])} rows)")
        if t.get("purpose"):
            lines.append(t["purpose"])
        for c in t.get("columns", []):
            lines.append(f"- `{c['name']}` ({c['type']}){': ' + c['description'] if c.get('description') else ''}")
        lines.append("")
    lines += ["## Injected anomalies (ground truth)", ""]
    for a in truth["anomalies"]:
        lines.append(f"- **{a['type']}** on `{a['table']}.{a.get('column', '*')}`: {a['count']} rows")
    if not truth["anomalies"]:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def export_zip(schema, include_sqlite=True):
    tables, truth = generate(schema)
    buf = io.BytesIO()
    coco = dict(images=[], annotations=[], categories=[])
    categories = {}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("schema.json", json.dumps(schema, indent=2))
        z.writestr("ground_truth.json", json.dumps(truth, indent=2, default=str))
        z.writestr("data_card.md", data_card(schema, truth, tables))
        for name, rows in tables.items():
            z.writestr(f"csv/{name}.csv", _csv(rows))
            z.writestr(f"jsonl/{name}.jsonl", "\n".join(json.dumps(r, default=str) for r in public_rows(rows)))
        for idx, (path, data, boxes, row, col) in enumerate(_render_images(schema, tables)):
            z.writestr(path, data)
            coco["images"].append(dict(id=idx + 1, file_name=path, width=col.get("size", [320, 240])[0], height=col.get("size", [320, 240])[1]))
            for b in boxes:
                cat = categories.setdefault(b["label"], len(categories) + 1)
                x0, y0, x1, y1 = b["box"]
                coco["annotations"].append(dict(id=len(coco["annotations"]) + 1, image_id=idx + 1, category_id=cat, bbox=[x0, y0, x1 - x0, y1 - y0], area=(x1 - x0) * (y1 - y0), iscrowd=0))
        if coco["images"]:
            coco["categories"] = [dict(id=v, name=k) for k, v in categories.items()]
            z.writestr("images/annotations_coco.json", json.dumps(coco, indent=2))
        if include_sqlite:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "dataset.sqlite3"
                db = sqlite3.connect(path)
                for name, rows in tables.items():
                    rows = public_rows(rows)
                    if not rows:
                        continue
                    fields = list(dict.fromkeys(k for r in rows for k in r))
                    db.execute(f'CREATE TABLE "{name}" ({", ".join(chr(34) + f + chr(34) for f in fields)})')
                    db.executemany(
                        f'INSERT INTO "{name}" VALUES ({", ".join("?" for _ in fields)})',
                        [[json.dumps(r.get(f)) if isinstance(r.get(f), (dict, list)) else r.get(f) for f in fields] for r in rows],
                    )
                db.commit()
                db.close()
                z.writestr("dataset.sqlite3", path.read_bytes())
    return buf.getvalue()


# ------------------------------------------------------------------ recommendations
def _entity_columns(template):
    cols = []
    for name, spec in (template or {}).items():
        if isinstance(spec, str) and spec in SHARED_KINDS:
            cols.append(dict(name=name, type="shared", kind=spec, description=f"Shared {spec} used across scenarios"))
        elif isinstance(spec, str) and spec.startswith("seq:"):
            cols.append(dict(name=name, type="id", prefix=spec[4:]))
        elif isinstance(spec, list) and len(spec) == 2 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in spec):
            if all(isinstance(v, int) for v in spec):
                cols.append(dict(name=name, type="int", min=spec[0], max=spec[1]))
            else:
                cols.append(dict(name=name, type="float", min=spec[0], max=spec[1], decimals=2))
        elif isinstance(spec, list):
            cols.append(dict(name=name, type="category", values=[str(v) for v in spec]))
    return cols


def recommend(spec):
    """Recommended datasets for a world, derived from its systems' evidence modalities."""
    nodes = spec["nodes"]
    ids = [n["id"] for n in nodes]
    by_modality = {}
    for n in nodes:
        by_modality.setdefault(n.get("modality", "log"), []).append(n)
    unit = re.sub(r"[^a-z0-9]+", "_", spec.get("unit", "tasks").lower()).strip("_") or "tasks"
    if unit in {"systems", "sensor_readings", "logs", "transactions", "messages", "inspection_images", "relationships", "locations", "documents"}:
        unit = f"{unit}_population"
    reserved = {"id", "entity_id", "region", "arrival", "current_system", "late"}
    entity_cols = [c for c in _entity_columns(spec.get("entity")) if c["name"] not in reserved]
    tables = [
        dict(
            name="systems",
            purpose="Reference list of the systems in the causal graph. Join other tables on `system`.",
            data=[dict(system=n["id"], label=n["label"], owner_role=n["role"], capacity=n["capacity"], evidence=n.get("modality", "log"), source=n.get("source", "")) for n in nodes],
            columns=[],
        ),
        dict(
            name=unit,
            rows=500,
            purpose=f"The population of {spec.get('unit', 'work items')} flowing through the world; use for segmentation, SLA and impact analysis.",
            columns=[dict(name="entity_id", type="id", prefix=unit[:3].upper()), dict(name="region", type="category", values=["North", "South", "East", "West"])]
            + entity_cols
            + [
                dict(name="arrival", type="datetime", start="2026-09-28T09:00", end="2026-09-28T10:00"),
                dict(name="current_system", type="category", values=ids),
                dict(name="late", type="bool", p=0.1),
            ],
        ),
    ]
    anomalies = []
    root = spec["incident"]["node"]
    if "sensor" in by_modality:
        sensors = by_modality["sensor"]
        metric, unit_name, base, slope = sensor_profile(sensors[0])
        tables.append(
            dict(
                name="sensor_readings",
                rows=min(4000, 600 * len(sensors)),
                purpose="Telemetry for anomaly detection and forecasting. Ground truth marks the injected drift on the failing system.",
                columns=[
                    dict(name="reading_id", type="id", prefix="R"),
                    dict(name="system", type="category", values=[n["id"] for n in sensors]),
                    dict(name="timestamp", type="datetime", start="2026-09-28T00:00", step_minutes=1, per_step=len(sensors)),
                    dict(name="value", type="series", base=base, amplitude=abs(slope) * 8 + abs(base) * 0.02, period=240, noise=abs(slope) * 3 + abs(base) * 0.01),
                    dict(name="unit", type="category", values=[unit_name]),
                    dict(name="quality", type="category", values=["good", "uncertain", "bad"], weights=[0.96, 0.03, 0.01]),
                ],
            )
        )
        target = root if root in [n["id"] for n in sensors] else sensors[0]["id"]
        anomalies.append(dict(type="drift", table="sensor_readings", column="value", start_fraction=0.7, shift=round(abs(slope) * 40 + abs(base) * 0.15, 3), where=dict(system=target), note="Degradation of the failing system"))
        anomalies.append(dict(type="stuck", table="sensor_readings", column="value", start_fraction=0.85, where=dict(system=sensors[-1]["id"]), note="Stuck sensor distractor"))
    if "log" in by_modality:
        tables.append(
            dict(
                name="logs",
                rows=2000,
                purpose="Application and security logs for root-cause investigation and log analytics.",
                columns=[
                    dict(name="log_id", type="id", prefix="L"),
                    dict(name="timestamp", type="datetime", start="2026-09-28T09:00", end="2026-09-28T10:00"),
                    dict(name="system", type="category", values=[n["id"] for n in by_modality["log"]]),
                    dict(name="level", type="category", values=["INFO", "WARN", "ERROR"], weights=[0.82, 0.14, 0.04]),
                    dict(name="latency_ms", type="float", dist="lognormal", mean=3.8, sigma=0.5, decimals=1),
                    dict(name="message", type="text", template="{system} {choice:request completed|retry scheduled|connection reset|permission denied|timeout}"),
                ],
            )
        )
        anomalies.append(dict(type="outliers", table="logs", column="latency_ms", rate=0.03, factor=8, note="Latency spikes"))
    if "transaction" in by_modality:
        tables.append(
            dict(
                name="transactions",
                rows=3000,
                purpose="Transactions for fraud, anomaly and reconciliation exercises. `is_suspicious` is a learnable label.",
                columns=[
                    dict(name="txn_id", type="id", prefix="T"),
                    dict(name="entity_id", type="ref", table=unit, column="entity_id"),
                    dict(name="timestamp", type="datetime", start="2026-09-01T00:00", end="2026-09-28T10:00"),
                    dict(name="amount", type="float", dist="lognormal", mean=4.2, sigma=0.9, decimals=2),
                    dict(name="channel", type="category", values=["web", "mobile", "api", "branch"], weights=[0.4, 0.35, 0.2, 0.05]),
                    dict(name="velocity_1h", type="int", dist="poisson", lam=2),
                    dict(name="is_suspicious", type="label", weights=dict(amount=0.002, velocity_1h=0.45), bias=-4.2),
                ],
            )
        )
        anomalies.append(dict(type="fraud_ring", table="transactions", column="entity_id", size=6, label="is_suspicious", note="Coordinated ring sharing one entity"))
        anomalies.append(dict(type="label_flip", table="transactions", column="is_suspicious", rate=0.03, note="Noisy labels"))
    if "ticket" in by_modality or "email" in by_modality or "chat" in by_modality:
        tables.append(
            dict(
                name="messages",
                rows=600,
                purpose="Tickets, emails and chat for text classification, triage and summarisation.",
                columns=[
                    dict(name="message_id", type="id", prefix="M"),
                    dict(name="timestamp", type="datetime", start="2026-09-28T09:00", end="2026-09-28T10:00"),
                    dict(name="channel", type="category", values=["ticket", "email", "chat"]),
                    dict(name="system", type="category", values=ids),
                    dict(name="sender", type="faker", provider="name"),
                    dict(name="priority", type="category", values=["P1", "P2", "P3", "P4"], weights=[0.05, 0.2, 0.45, 0.3]),
                    dict(name="text", type="text", template="{choice:Users report|Monitoring shows|Customer says} {choice:slow responses|errors|missing data|unexpected behaviour} on {system}"),
                ],
            )
        )
        anomalies.append(dict(type="duplicates", table="messages", rate=0.02, note="Duplicate tickets"))
    visual_nodes = by_modality.get("image", []) + by_modality.get("video", [])
    if visual_nodes:
        kind = spec.get("visual") or "aerial"
        tables.append(
            dict(
                name="inspection_images",
                rows=40,
                purpose=f"Labelled {vision.KINDS[kind].lower()} images with COCO boxes for computer-vision detection and QA.",
                columns=[
                    dict(name="image_id", type="id", prefix="IMG"),
                    dict(name="system", type="category", values=[n["id"] for n in visual_nodes]),
                    dict(name="captured_at", type="datetime", start="2026-09-28T09:00", end="2026-09-28T10:00"),
                    dict(name="image", type="image", kind=kind, defect_rate=0.35, lighting=1.0),
                ],
            )
        )
    if "graph" in by_modality:
        tables.append(
            dict(
                name="relationships",
                rows=800,
                purpose="Entity relationships for graph analytics (rings, communities, blast radius).",
                columns=[
                    dict(name="edge_id", type="id", prefix="E"),
                    dict(name="source", type="ref", table=unit, column="entity_id"),
                    dict(name="target", type="ref", table=unit, column="entity_id"),
                    dict(name="relation", type="category", values=["shares_device", "transfers_to", "depends_on", "communicates_with"]),
                    dict(name="weight", type="float", dist="exponential", mean=1.0, decimals=3),
                ],
            )
        )
    if "map" in by_modality:
        tables.append(
            dict(
                name="locations",
                rows=300,
                purpose="Geospatial observations for routing, coverage and map layers.",
                columns=[
                    dict(name="point_id", type="id", prefix="P"),
                    dict(name="system", type="category", values=[n["id"] for n in by_modality["map"]]),
                    dict(name="lat", type="float", dist="normal", mean=51.5, std=0.05, decimals=5),
                    dict(name="lon", type="float", dist="normal", mean=-0.12, std=0.08, decimals=5),
                    dict(name="status", type="category", values=["ok", "degraded", "blocked"], weights=[0.8, 0.15, 0.05]),
                ],
            )
        )
    if "document" in by_modality:
        tables.append(
            dict(
                name="documents",
                rows=60,
                purpose="Synthetic documents (reports, contracts, procedures) for RAG and extraction exercises.",
                columns=[
                    dict(name="doc_id", type="id", prefix="DOC"),
                    dict(name="system", type="category", values=[n["id"] for n in by_modality["document"]]),
                    dict(name="title", type="text", template="{choice:Situation report|Procedure|Contract extract|Review notes} for {system}"),
                    dict(name="body", type="faker", provider="paragraph"),
                ],
            )
        )
    kinds_used = {c["kind"] for c in entity_cols if c["type"] == "shared"}
    for kind in sorted(kinds_used):
        tables.insert(1, dict(name=f"master_{kind.lower()}", purpose=f"Shared {kind} master data. The same IDs appear in every scenario that references {kind}.", data=registry()[kind], columns=[]))
    return dict(
        name=f"{spec['title']} dataset",
        description=f"Synthetic multi-table dataset for the '{spec['title']}' scenario. {spec['summary']}",
        seed=2026,
        tables=tables,
        anomalies=anomalies,
        guide=guidance(spec, tables, anomalies),
    )


def guidance(spec, tables, anomalies):
    tasks = []
    names = {t["name"] for t in tables}
    if "sensor_readings" in names:
        tasks.append("Anomaly detection / predictive maintenance on sensor_readings (label = ground_truth drift rows)")
        tasks.append("Forecasting: predict the next hour of each system's signal")
    if "transactions" in names:
        tasks.append("Fraud classification with is_suspicious; graph features from shared entity_id")
    if "logs" in names:
        tasks.append("Root-cause analysis: correlate ERROR spikes and latency outliers by system")
    if "messages" in names:
        tasks.append("Ticket triage: classify priority and route by system; detect duplicates")
    if "inspection_images" in names:
        tasks.append("Computer vision: detect defects using COCO boxes; test robustness to lighting")
    if "relationships" in names:
        tasks.append("Graph analytics: communities, rings and blast radius")
    return dict(
        what=f"Generate the tables below to practise the '{spec['title']}' investigation outside the live simulation.",
        steps=[
            "Review each recommended table and its purpose.",
            "Edit the schema: add or remove columns, change distributions, row counts or anomalies.",
            "Validate. Errors point to the exact table/column to fix.",
            "Preview 25 rows per table and check the column charts.",
            "Export CSV/JSONL/SQLite (+ images and COCO boxes). ground_truth.json lists every injected anomaly.",
        ],
        tasks=tasks,
        column_types=COLUMN_TYPES,
        anomaly_types=ANOMALY_TYPES,
    )


TEMPLATES = {
    "blank": dict(
        name="Blank dataset",
        description="Start from one table and add columns.",
        seed=2026,
        tables=[dict(name="records", rows=200, columns=[dict(name="record_id", type="id", prefix="REC"), dict(name="value", type="float", dist="normal", mean=100, std=15)])],
        anomalies=[],
    ),
    "retail_crm": dict(
        name="Retail orders & CRM",
        description="Customers, products and orders with a formula for order value.",
        seed=2026,
        tables=[
            dict(name="customers", rows=300, purpose="Customer master", columns=[dict(name="customer_id", type="id", prefix="C"), dict(name="name", type="faker", provider="company"), dict(name="segment", type="category", values=["SMB", "Mid-Market", "Enterprise"], weights=[0.6, 0.3, 0.1]), dict(name="region", type="category", values=["North", "South", "East", "West"])]),
            dict(name="products", rows=40, purpose="Product catalogue", columns=[dict(name="product_id", type="id", prefix="P", width=3), dict(name="category", type="category", values=["A", "B", "C"]), dict(name="unit_price", type="float", dist="lognormal", mean=4.5, sigma=0.6, decimals=2)]),
            dict(name="orders", rows=3000, purpose="Order lines", columns=[dict(name="order_id", type="id", prefix="O"), dict(name="customer_id", type="ref", table="customers", column="customer_id"), dict(name="product_id", type="ref", table="products", column="product_id"), dict(name="quantity", type="int", min=1, max=12), dict(name="unit_price", type="float", min=5, max=900, decimals=2), dict(name="order_value", type="formula", expr="quantity * unit_price", decimals=2), dict(name="order_date", type="date", start="2026-01-01", end="2026-09-28"), dict(name="status", type="category", values=["delivered", "delayed", "cancelled"], weights=[0.9, 0.07, 0.03])]),
        ],
        anomalies=[dict(type="duplicates", table="customers", rate=0.03), dict(type="unit_change", table="orders", column="order_value", start_fraction=0.9, factor=100)],
    ),
    "fraud_transactions": dict(
        name="Fraud transactions",
        description="Card transactions with a logistic fraud label and a collusion ring.",
        seed=2026,
        tables=[
            dict(name="cards", rows=400, columns=[dict(name="card_id", type="id", prefix="CARD"), dict(name="account", type="shared", kind="Account"), dict(name="home_country", type="category", values=["GB", "IN", "US", "DE", "BR"])]),
            dict(name="transactions", rows=5000, columns=[dict(name="txn_id", type="id", prefix="T"), dict(name="card_id", type="ref", table="cards", column="card_id"), dict(name="merchant", type="text", template="M-{choice:001|002|003|004|005|006|007|008|009|010}"), dict(name="amount", type="float", dist="lognormal", mean=3.6, sigma=1.0, decimals=2), dict(name="distance_km", type="float", dist="exponential", mean=12, decimals=1), dict(name="velocity_1h", type="int", dist="poisson", lam=1), dict(name="hour", type="int", min=0, max=23), dict(name="is_fraud", type="label", weights=dict(amount=0.004, distance_km=0.02, velocity_1h=0.6), bias=-5.5)]),
        ],
        anomalies=[dict(type="fraud_ring", table="transactions", column="merchant", size=8, label="is_fraud"), dict(type="label_flip", table="transactions", column="is_fraud", rate=0.02)],
    ),
    "iot_telemetry": dict(
        name="IoT telemetry",
        description="Machines and sensor time series with drift and stuck sensors.",
        seed=2026,
        tables=[
            dict(name="machines", rows=12, columns=[dict(name="machine_id", type="shared", kind="Machine"), dict(name="line", type="category", values=["L1", "L2", "L3"])]),
            dict(name="readings", rows=6000, columns=[dict(name="reading_id", type="id", prefix="R"), dict(name="machine_id", type="ref", table="machines", column="machine_id"), dict(name="timestamp", type="datetime", start="2026-09-01T00:00", step_minutes=5, per_step=12), dict(name="temperature_c", type="series", base=62, amplitude=4, period=288, noise=0.8), dict(name="vibration_mm_s", type="float", dist="normal", mean=2.2, std=0.3, min=0)]),
        ],
        anomalies=[dict(type="drift", table="readings", column="vibration_mm_s", start_fraction=0.75, shift=1.6), dict(type="stuck", table="readings", column="temperature_c", start_fraction=0.9)],
    ),
    "patient_encounters": dict(
        name="Patient encounters (Synthea-style)",
        description="Synthetic patients, encounters, labs and medications. Not real clinical data.",
        seed=2026,
        tables=[
            dict(name="patients", rows=400, columns=[dict(name="patient_id", type="id", prefix="PT"), dict(name="birth_year", type="int", min=1930, max=2024), dict(name="sex", type="category", values=["F", "M"]), dict(name="city", type="faker", provider="city")]),
            dict(name="encounters", rows=2000, columns=[dict(name="encounter_id", type="id", prefix="EN"), dict(name="patient_id", type="ref", table="patients", column="patient_id"), dict(name="start", type="datetime", start="2026-01-01T00:00", end="2026-09-28T00:00"), dict(name="type", type="category", values=["ambulatory", "emergency", "inpatient"], weights=[0.7, 0.2, 0.1]), dict(name="los_hours", type="float", dist="lognormal", mean=1.5, sigma=1.0, decimals=1)]),
            dict(name="labs", rows=4000, columns=[dict(name="lab_id", type="id", prefix="LAB"), dict(name="encounter_id", type="ref", table="encounters", column="encounter_id"), dict(name="test", type="category", values=["CRP", "HbA1c", "Troponin", "WBC"]), dict(name="value", type="float", dist="lognormal", mean=1.2, sigma=0.7, decimals=2), dict(name="turnaround_min", type="int", dist="normal", mean=55, std=15, min=5)]),
        ],
        anomalies=[dict(type="delay", table="encounters", column="start", rate=0.05, minutes=240), dict(type="outliers", table="labs", column="turnaround_min", rate=0.05, factor=4)],
    ),
    "genomic_variants": dict(
        name="Genomic variants (VCF-style)",
        description="Samples and variant calls with quality scores. Research synthetic only.",
        seed=2026,
        tables=[
            dict(name="samples", rows=120, columns=[dict(name="sample_id", type="id", prefix="SMP"), dict(name="population", type="category", values=["POP-A", "POP-B", "POP-C"]), dict(name="lane", type="int", min=1, max=4)]),
            dict(name="variants", rows=8000, columns=[dict(name="variant_id", type="id", prefix="VAR"), dict(name="sample_id", type="ref", table="samples", column="sample_id"), dict(name="chrom", type="category", values=[f"chr{i}" for i in range(1, 23)]), dict(name="pos", type="int", min=10000, max=150000000), dict(name="ref", type="category", values=["A", "C", "G", "T"]), dict(name="alt", type="category", values=["A", "C", "G", "T"]), dict(name="qual", type="float", dist="normal", mean=45, std=12, min=0, decimals=1), dict(name="depth", type="int", dist="poisson", lam=30)]),
        ],
        anomalies=[dict(type="drift", table="variants", column="qual", start_fraction=0.8, shift=-20)],
    ),
    "compound_library": dict(
        name="Compound library (RDKit-style descriptors)",
        description="Compounds with descriptors and an activity label for property-prediction exercises.",
        seed=2026,
        tables=[
            dict(name="compounds", rows=2000, columns=[dict(name="compound_id", type="id", prefix="CMP"), dict(name="scaffold", type="category", values=["indole", "piperazine", "pyrimidine", "benzimidazole"]), dict(name="mol_weight", type="float", dist="normal", mean=380, std=80, min=120, decimals=1), dict(name="logp", type="float", dist="normal", mean=2.8, std=1.3, decimals=2), dict(name="hbd", type="int", min=0, max=6), dict(name="tpsa", type="float", dist="normal", mean=85, std=25, min=10, decimals=1), dict(name="active", type="label", weights=dict(logp=0.5, hbd=-0.3), bias=-2.0)]),
        ],
        anomalies=[dict(type="label_flip", table="compounds", column="active", rate=0.05)],
    ),
    "drone_inspection": dict(
        name="Drone inspection images",
        description="Power-line and turbine inspection images with defects and COCO boxes.",
        seed=2026,
        tables=[
            dict(name="towers", rows=30, columns=[dict(name="tower_id", type="shared", kind="Asset"), dict(name="line", type="category", values=["L-110", "L-220", "L-400"])]),
            dict(name="images", rows=60, columns=[dict(name="image_id", type="id", prefix="IMG"), dict(name="tower_id", type="ref", table="towers", column="tower_id"), dict(name="photo", type="image", kind="tower", defect_rate=0.4, lighting=1.0)]),
        ],
        anomalies=[],
    ),
    "traffic_camera": dict(
        name="Traffic camera events",
        description="Junction camera frames with red-light and wrong-way violations.",
        seed=2026,
        tables=[
            dict(name="frames", rows=50, columns=[dict(name="frame_id", type="id", prefix="FR"), dict(name="junction", type="shared", kind="Location"), dict(name="captured_at", type="datetime", start="2026-09-28T18:00", step_minutes=1), dict(name="frame", type="image", kind="traffic", defect_rate=0.3, lighting=0.7)]),
        ],
        anomalies=[],
    ),
}
