"""Small, bounded standard-library data tools. No model downloads or dataframe runtime."""

import csv
import io
import json
import math
import random
import re
import sqlite3
import zipfile
from . import settings


def dataset_quality(bundle):
    checks = []
    if "customers" in bundle:
        customers = {x["customer_id"] for x in bundle["customers"]}
        products = {x["product_id"] for x in bundle["products"]}
        orders = bundle.get("orders", [])
        checks.extend(
            [
                dict(
                    name="Order/customer references",
                    passed=all(o["customer_id"] in customers for o in orders),
                ),
                dict(
                    name="Order/product references",
                    passed=all(o["product_id"] in products for o in orders),
                ),
            ]
        )
    checks.append(
        dict(name="Synthetic origin marker", passed=bundle.get("meta", {}).get("synthetic") is True)
    )
    return dict(
        checks=checks,
        score=round(100 * sum(c["passed"] for c in checks) / len(checks), 1),
        note="Structural checks and an origin marker do not establish formal privacy guarantees.",
    )


def csv_text(rows):
    out = io.StringIO(newline="")
    if not rows:
        return ""
    fields = list(dict.fromkeys(k for row in rows for k in row))
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        # Prevent formulas when CSV exports are opened in a spreadsheet.
        safe = {
            k: (
                "'" + v
                if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r"))
                else v
            )
            for k, v in row.items()
        }
        writer.writerow(safe)
    return out.getvalue()


def bundle_zip(bundle):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("bundle.json", json.dumps(bundle, indent=2))
        for name, rows in bundle.items():
            if isinstance(rows, list) and (not rows or isinstance(rows[0], dict)):
                z.writestr(re.sub(r"[^a-zA-Z0-9_-]", "_", name) + ".csv", csv_text(rows))
    return data.getvalue()


def synthesize(source, rows, seed, method):
    parsed = list(csv.DictReader(io.StringIO(source)))
    if not parsed or len(parsed) > 2000 or len(parsed[0]) > 30:
        raise ValueError("Provide 1–2,000 CSV rows with at most 30 columns")
    if any(None in row or any(v is None for v in row.values()) for row in parsed):
        raise ValueError("CSV rows must have the same number of fields as the header")
    rng = random.Random(seed)
    result = []
    for _ in range(rows):
        if method == "bootstrap":
            result.append(dict(rng.choice(parsed)))
        else:
            row = {}
            for col in parsed[0]:
                values = [r[col] for r in parsed]
                chosen = rng.choice(values)
                try:
                    numbers = [float(v) for v in values]
                    if not all(math.isfinite(v) for v in numbers):
                        raise ValueError("Nonfinite source values are treated as text")
                    span = max(numbers) - min(numbers)
                    row[col] = round(float(chosen) + rng.uniform(-0.02, 0.02) * span, 4)
                except (ValueError, TypeError):
                    row[col] = chosen
            result.append(row)
    originals = {tuple(str(v) for v in r.values()) for r in parsed}
    overlap = sum(tuple(str(v) for v in r.values()) in originals for r in result)
    return dict(
        rows=result,
        source_rows=len(parsed),
        exact_overlap=overlap,
        method=method,
        note="Bootstrap may reproduce input records. Independent sampling does not preserve all relationships. Use synthetic or approved non-sensitive inputs; this is not anonymization.",
    )


def push_local(profile, bundle, resource_id):
    destination = settings.DATA / "exports" / resource_id
    destination.mkdir(parents=True, exist_ok=True)
    if profile["type"] == "file":
        target = destination / "dataset.zip"
        target.write_bytes(bundle_zip(bundle))
        return dict(
            status="completed",
            destination=str(target),
            tables=sum(isinstance(v, list) for v in bundle.values()),
        )
    target = destination / "sandbox.sqlite3"
    with sqlite3.connect(str(target)) as db:
        count = 0
        for name, rows in bundle.items():
            if not isinstance(rows, list) or not rows:
                continue
            table = re.sub(r"[^a-zA-Z0-9_]", "_", name)
            db.execute(
                f'CREATE TABLE IF NOT EXISTS "{table}" (row_id INTEGER PRIMARY KEY, record TEXT NOT NULL)'
            )
            db.execute(f'DELETE FROM "{table}"')
            db.executemany(
                f'INSERT INTO "{table}"(record) VALUES(?)', [(json.dumps(row),) for row in rows]
            )
            count += 1
    return dict(status="completed", destination=str(target), tables=count)
