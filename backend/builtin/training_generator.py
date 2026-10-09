from __future__ import annotations
import json, math, random
from datetime import datetime, timedelta
from pathlib import Path
from faker import Faker

REGIONS = ["North", "South", "East", "West"]
SEGMENTS = ["SMB", "Mid-Market", "Enterprise", "Retail"]
CATEGORIES = ["Category-A", "Category-B", "Category-C", "Category-D"]
DEPARTMENTS = ["Sales", "Marketing", "Operations", "Finance", "Engineering", "IT"]


def _money(v):
    return round(float(v), 2)


def generate_bundle(scenario: dict, seed: int, scale: int = 1) -> dict:
    rnd = random.Random(seed)
    fake = Faker("en_IN")
    Faker.seed(seed)
    scale = max(1, min(int(scale), 5))

    n_customers, n_orders, n_tickets = 160 * scale, 900 * scale, 260 * scale
    today = datetime(2026, 9, 1)

    customers = []
    for i in range(1, n_customers + 1):
        segment = rnd.choices(SEGMENTS, weights=[45, 25, 15, 15])[0]
        region = rnd.choice(REGIONS)
        customers.append({
            "customer_id": f"C-{i:04d}", "name": fake.company(), "segment": segment,
            "region": region, "status": rnd.choices(["Active", "At Risk", "Churned"], [82, 12, 6])[0],
            "email": f"contact{i}@example.invalid", "tenure_months": rnd.randint(2, 120),
            "lifetime_value": _money(rnd.uniform(3000, 180000))
        })

    products = []
    for i in range(1, 31):
        products.append({
            "product_id": f"P-{i:03d}", "product_name": f"Product {i}",
            "category": CATEGORIES[(i - 1) % len(CATEGORIES)], "unit_price": _money(rnd.uniform(80, 2200)),
            "inventory": rnd.randint(40, 600), "supplier_id": f"S-{((i - 1) % 8)+1:02d}"
        })

    suppliers = []
    for i in range(1, 9):
        suppliers.append({
            "supplier_id": f"S-{i:02d}", "supplier_name": f"Supplier {i}",
            "on_time_pct": round(rnd.uniform(91, 99), 1), "lead_time_days": rnd.randint(5, 16),
            "risk": rnd.choice(["Low", "Low", "Medium"])
        })

    orders = []
    for i in range(1, n_orders + 1):
        c = rnd.choice(customers); p = rnd.choice(products)
        qty = rnd.randint(1, 12); days_ago = rnd.randint(0, 179)
        orders.append({
            "order_id": f"O-{i:06d}", "customer_id": c["customer_id"], "product_id": p["product_id"],
            "region": c["region"], "order_date": (today - timedelta(days=days_ago)).date().isoformat(),
            "quantity": qty, "amount": _money(qty * p["unit_price"] * rnd.uniform(.94, 1.05)),
            "status": rnd.choices(["Delivered", "Open", "Delayed", "Cancelled"], [78, 10, 8, 4])[0],
            "payment_method": rnd.choice(["card", "bank", "wallet", "invoice"])
        })

    tickets = []
    for i in range(1, n_tickets + 1):
        c = rnd.choice(customers)
        tickets.append({
            "ticket_id": f"T-{i:05d}", "customer_id": c["customer_id"], "segment": c["segment"],
            "queue": rnd.choice(["Tier-1", "Tier-2", "Billing", "Product"]),
            "issue_type": rnd.choice(["access", "billing", "how-to", "defect", "delivery"]),
            "priority": rnd.choice(["Low", "Medium", "High"]), "response_hours": round(rnd.uniform(.3, 18), 1),
            "sla_breached": rnd.random() < .12, "status": rnd.choice(["Open", "Resolved", "Escalated"])
        })

    invoices = []
    for i in range(1, 220 * scale + 1):
        dept = rnd.choice(DEPARTMENTS)
        cat = rnd.choice(["Software", "Contractor", "Travel", "Facilities", "Marketing", "Training"])
        invoices.append({
            "invoice_id": f"INV-{i:05d}", "department": dept, "category": cat,
            "amount": _money(rnd.uniform(300, 22000)), "budget_amount": _money(rnd.uniform(500, 18000)),
            "status": rnd.choice(["Approved", "Paid", "Pending"])
        })

    employees = []
    for i in range(1, 140 * scale + 1):
        dept = rnd.choice(DEPARTMENTS)
        employees.append({
            "employee_id": f"E-{i:04d}", "department": dept,
            "shift": rnd.choice(["day", "day", "night"]), "overtime_hours": rnd.randint(0, 35),
            "tenure_years": round(rnd.uniform(.2, 14), 1), "attrition_risk": rnd.choice(["Low", "Low", "Medium", "High"]),
            "training_complete": rnd.random() < .82
        })

    alerts = []
    for i in range(1, 120 * scale + 1):
        alerts.append({
            "alert_id": f"A-{i:05d}", "region": rnd.choice(REGIONS),
            "type": rnd.choice(["failed_login", "malware", "payment_velocity", "impossible_travel", "privileged_change"]),
            "severity": rnd.choice(["Low", "Medium", "High", "Critical"]),
            "channel": rnd.choice(["card", "bank", "wallet", "identity"]),
            "value": _money(rnd.uniform(0, 20000)), "status": rnd.choice(["New", "Investigating", "Closed"])
        })

    claims = []
    for i in range(1, 180 * scale + 1):
        claims.append({
            "claim_id": f"CL-{i:05d}", "provider_id": f"P-{rnd.randint(1,20):02d}",
            "claim_type": rnd.choice(["auto", "property", "health", "travel"]),
            "amount": _money(rnd.uniform(200, 18000)), "repeat_flag": rnd.random() < .06,
            "status": rnd.choice(["Open", "Paid", "Review"])
        })

    quality = []
    for i in range(1, 180 * scale + 1):
        quality.append({
            "inspection_id": f"Q-{i:05d}", "line": rnd.choice(["L1", "L2", "L3"]),
            "supplier_id": f"S-{rnd.randint(1,8):02d}", "lot": f"LOT-{rnd.randint(100,999)}",
            "units": rnd.randint(100, 1200), "defects": rnd.randint(0, 10)
        })

    bundle = {
        "customers": customers, "products": products, "orders": orders, "tickets": tickets,
        "suppliers": suppliers, "invoices": invoices, "employees": employees, "alerts": alerts,
        "claims": claims, "quality": quality,
    }
    inject_pattern(bundle, scenario.get("inject"), rnd)
    bundle["meta"] = {
        "scenario": scenario["key"], "seed": seed, "scale": scale,
        "generated_at": datetime.utcnow().isoformat() + "Z", "synthetic": True,
        "notice": "All records were generated for training. No production records are included."
    }
    return bundle


def inject_pattern(b, key, rnd):
    if key == "sales_decline":
        for p in b["products"]:
            if p["product_id"] == "P-007": p["inventory"] = 0
        candidates = [o for o in b["orders"] if o["region"] == "West"][:160]
        for o in candidates:
            o["product_id"] = "P-007"; o["status"] = rnd.choice(["Cancelled", "Delayed", "Cancelled"])
    elif key == "customer_churn":
        smb_ids = {c["customer_id"] for c in b["customers"] if c["segment"] == "SMB"}
        for c in b["customers"]:
            if c["customer_id"] in smb_ids and rnd.random() < .28: c["status"] = "Churned"
        for t in b["tickets"]:
            if t["customer_id"] in smb_ids:
                t["response_hours"] = round(rnd.uniform(18, 55), 1); t["sla_breached"] = True
                if rnd.random() < .35: t["status"] = "Escalated"
    elif key == "payment_fraud":
        for a in b["alerts"][:45]:
            a.update({"region":"East","channel":"wallet","type":"payment_velocity","severity":"Critical","value":_money(rnd.uniform(12000,48000)),"status":"New"})
    elif key == "supplier_risk":
        for s in b["suppliers"]:
            if s["supplier_id"] == "S-03": s.update({"on_time_pct": 62.5, "lead_time_days": 29, "risk":"High"})
        for p in b["products"]:
            if p["supplier_id"] == "S-03": p["inventory"] = rnd.randint(0, 25)
    elif key == "budget_overrun":
        for inv in b["invoices"][:75]:
            inv.update({"department":"Marketing","category":"Contractor","amount":_money(rnd.uniform(15000,32000)),"budget_amount":_money(rnd.uniform(5000,11000))})
    elif key == "service_sla":
        for t in b["tickets"][:100]:
            t.update({"queue":"Tier-1","issue_type":"access","response_hours":round(rnd.uniform(22,60),1),"sla_breached":True,"status":rnd.choice(["Open","Escalated"])})
    elif key == "workforce_attrition":
        for e in b["employees"][:55]:
            e.update({"department":"Operations","shift":"night","overtime_hours":rnd.randint(28,60),"attrition_risk":"High"})
    elif key == "quality_defect":
        for q in b["quality"][:65]:
            q.update({"line":"L2","supplier_id":"S-05","lot":f"LOT-BAD-{rnd.randint(1,6)}","defects":rnd.randint(18,55)})
    elif key == "cyber_incident":
        for a in b["alerts"][:50]:
            a.update({"type":"impossible_travel","channel":"identity","severity":"Critical","status":"New"})
    elif key == "claims_leakage":
        for c in b["claims"][:60]:
            c.update({"provider_id":"P-14","repeat_flag":True,"amount":_money(rnd.uniform(14000,42000)),"status":"Review"})
    elif key == "retail_demand":
        cat_products = [p["product_id"] for p in b["products"] if p["category"] == "Category-C"]
        for p in b["products"]:
            if p["product_id"] in cat_products: p["inventory"] = rnd.randint(0, 18)
        for o in b["orders"][:220]:
            o.update({"region":"South","product_id":rnd.choice(cat_products),"quantity":rnd.randint(8,22)})
    elif key == "data_quality":
        dupes = []
        for c in b["customers"][:35]:
            x = dict(c); x["customer_id"] = f"DUP-{c['customer_id']}"; x["email"] = c["email"]
            dupes.append(x)
        b["customers"].extend(dupes)


def save_bundle(bundle: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2)


def load_bundle(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)
