"""Lab orchestration: challenges, pipeline stages, investigation probes, scoring and an
auto-investigator agent. The injected failures are the hidden ``ground_truth.json``."""

import json
import random
from collections import OrderedDict

import numpy as np
from sklearn.metrics import roc_auc_score

from . import catalog
from . import classification as C
from . import forecasting as F

_LABS = OrderedDict()
INVESTIGATION_BUDGET = 60


# ------------------------------------------------------------------ creation
def choose_failures(profile_key, count, rng):
    fam = catalog.family(profile_key)
    avoid = set(catalog.profile(profile_key).get("avoid", []))
    options = [k for k, v in catalog.FAILURES.items() if fam in v["families"] and k not in avoid]
    chosen = []
    for f in rng.sample(options, len(options)):
        if len(chosen) >= count:
            break
        if any({f, c} <= group for group in catalog.EXCLUSIVE for c in chosen):
            continue
        chosen.append(f)
    return chosen


def create_config(scenario_key=None, profile_key=None, failures=None, count=None, seed=2026, handoff=None):
    scen = next((s for s in catalog.scenarios() if s["key"] == scenario_key), None) if scenario_key else None
    if scenario_key and not scen:
        raise ValueError("Unknown lab scenario")
    profile_key = scen["profile"] if scen else profile_key
    if profile_key not in catalog.CLASSIFICATION and profile_key not in catalog.FORECASTING:
        raise ValueError("Unknown profile")
    rng = random.Random(f"{profile_key}:{seed}")
    fam = catalog.family(profile_key)
    if failures:
        bad = [f for f in failures if f not in catalog.FAILURES or fam not in catalog.FAILURES[f]["families"]]
        if bad:
            raise ValueError(f"Failures not applicable to {fam}: {', '.join(bad)}")
    elif scen and scen["failures"] != "random":
        failures = list(scen["failures"])
    else:
        default = 2 if (scen and scen["group"] in {"Fraud detection", "Forecasting"}) else rng.randint(1, 3)
        failures = choose_failures(profile_key, max(1, min(5, count or default)), rng)
    if handoff:
        extra = "data_drift" if "data_drift" not in failures else "concept_drift"
        if extra not in failures and not any({extra, c} <= g for g in catalog.EXCLUSIVE for c in failures):
            failures.append(extra)
    prof = catalog.profile(profile_key)
    return dict(
        scenario=scenario_key,
        title=scen["title"] if scen else prof["title"],
        group=scen["group"] if scen else "Custom challenge",
        story=(scen or {}).get("story", "A model that looked fine offline is misbehaving in production."),
        profile=profile_key,
        family=fam,
        failures=failures,
        params=(scen or {}).get("params", {}),
        seed=seed,
        handoff=handoff,
    )


def build(config):
    key = json.dumps({k: config[k] for k in ("profile", "failures", "params", "seed")}, sort_keys=True)
    if key in _LABS:
        _LABS.move_to_end(key)
        return _LABS[key]
    prof = catalog.profile(config["profile"])
    cls = F.ForecastLab if config["family"] == "forecasting" else C.ClassificationLab
    lab = cls(prof, config["failures"], config["seed"], config.get("params"))
    _LABS[key] = lab
    while len(_LABS) > 12:
        _LABS.popitem(last=False)
    return lab


# ------------------------------------------------------------------ helpers
def _num(x):
    if isinstance(x, (np.floating, float)):
        return None if not np.isfinite(x) else round(float(x), 4)
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


def clean(obj):
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [clean(v) for v in obj.tolist()]
    return _num(obj)


def psi(a, b, bins=10):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) == 0 or len(b) == 0:
        return 0.0
    distinct = np.unique(a)
    if len(distinct) <= 12:
        vals = np.unique(np.concatenate([a, b]))[:30]
        pa = np.array([(a == v).mean() for v in vals])
        pb = np.array([(b == v).mean() for v in vals])
    else:
        edges = np.unique(np.quantile(a, np.linspace(0, 1, bins + 1)))
        edges[0], edges[-1] = -np.inf, np.inf
        pa = np.histogram(a, edges)[0] / len(a)
        pb = np.histogram(b, edges)[0] / len(b)
    pa, pb = np.clip(pa, 1e-4, None), np.clip(pb, 1e-4, None)
    return float(np.sum((pb - pa) * np.log(pb / pa)))


def hist(a, b, bins=14):
    both = np.concatenate([a, b])
    lo, hi = np.quantile(both, 0.01), np.quantile(both, 0.99)
    if hi <= lo:
        hi = lo + 1
    edges = np.linspace(lo, hi, bins + 1)
    ha = np.histogram(np.clip(a, lo, hi), edges)[0] / max(1, len(a))
    hb = np.histogram(np.clip(b, lo, hi), edges)[0] / max(1, len(b))
    return dict(edges=edges.tolist(), train=ha.tolist(), production=hb.tolist())


def stats(v):
    v = np.asarray(v, float)
    return dict(mean=float(np.mean(v)), std=float(np.std(v)), min=float(np.min(v)), max=float(np.max(v)), zeros_pct=float((v == 0).mean() * 100))


def availability(lab, f):
    if lab.family == "forecasting":
        return {
            "same_day_drawdown": "Inventory drawdown for the forecast day (end-of-day batch, backfilled)",
            "event": "Holiday & event calendar (known in advance)",
        }.get(f, "Known at forecast time")
    p = lab.p
    if f == p["leak"][0]:
        return f"{p['leak'][1]} - source: case management, updated when the case closes"
    if f == p["future"][0]:
        return f"{p['future'][1]} - rolling window backfilled nightly"
    if f.startswith("noise_"):
        return "Engineered embedding component (no documented meaning)"
    return "Captured at decision time"


# ------------------------------------------------------------------ classification probes
def _c_all_scores(lab, fixes=()):
    ev = lab.evaluate(fixes)
    pipe = ev["pipe"]
    X = lab.served(pipe)
    p = lab.scores(pipe, ev["served_model"], lab.matrix(X, ev["served_model"]["features"]))
    y_mon = lab.prod["y"].copy()
    if pipe["label_delay"]:
        y_mon[lab.prod["day"] >= C.PROD_END - pipe["label_delay"]] = 0
    return ev, pipe, X, p, y_mon


def _c_features(lab, pipe):
    feats = [f for f in pipe["features"] if not f.startswith("noise_")]
    noise = [f for f in pipe["features"] if f.startswith("noise_")]
    return feats + noise[:3]


def c_raw(lab):
    ev = lab.evaluate()
    pipe = ev["pipe"]
    X = lab.served(pipe)
    feats = _c_features(lab, pipe)
    tr_idx = lab._training_rows(pipe)[:10]
    pr_idx = np.where(lab.prod["day"] >= C.ONSET)[0][:10]
    rows_t = [dict(day=int(lab.train["day"][i]), segment=lab.train["seg"][i], entity=f"E-{lab.train['entity'][i]:03d}", **{f: round(float(lab.train["X"][f][i]), 3) for f in feats}, label=int(lab.train["y_obs"][i])) for i in tr_idx]
    rows_p = [dict(day=int(lab.prod["day"][i]), segment=lab.prod["seg"][i], entity=f"E-{lab.prod['entity'][i]:03d}", **{f: round(float(X[f][i]), 3) for f in feats}) for i in pr_idx]
    return dict(training=rows_t, production=rows_p, target=lab.p["target"])


def c_eda(lab):
    ev = lab.evaluate()
    pipe = ev["pipe"]
    X = lab.served(pipe)
    idx = lab._training_rows(pipe)
    out = []
    segment_drift = []
    for f in _c_features(lab, pipe):
        a, b = lab.train["X"][f][idx], X[f]
        out.append(dict(feature=f, unit=lab.meta.get(f, {}).get("unit", ""), train=stats(a), production=stats(b), psi=psi(a, b), histogram=hist(a, b)))
        if f == "segment_code" or f.startswith("noise_"):
            continue
        for s_ in lab.segments:
            ta = a[lab.train["seg"][idx] == s_]
            pb = b[lab.prod["seg"] == s_]
            if len(ta) > 50 and len(pb) > 50:
                segment_drift.append(dict(segment=s_, feature=f, psi=psi(ta, pb)))
    segment_drift = sorted(segment_drift, key=lambda r: -r["psi"])[:6]
    return dict(features=sorted(out, key=lambda r: -r["psi"]), segment_drift=segment_drift, note="Production = features as served to the model (days 180-240).")


def c_features(lab):
    ev = lab.evaluate()
    return dict(
        features=[
            dict(feature=f, description=lab.meta.get(f, {}).get("description", "Segment code" if f == "segment_code" else f.replace("_", " ")), unit=lab.meta.get(f, {}).get("unit", ""), availability=availability(lab, f))
            for f in ev["pipe"]["features"]
            if not f.startswith("noise_")
        ]
        + ([dict(feature="noise_01..noise_20", description="Engineered embedding components", unit="", availability=availability(lab, "noise_01"))] if any(f.startswith("noise_") for f in ev["pipe"]["features"]) else []),
        target=lab.p["target"],
        segment=lab.p["segment"][0],
    )


def c_training(lab):
    ev = lab.evaluate()
    pipe = ev["pipe"]
    idx = lab._training_rows(pipe)
    y = lab.train["y_obs"][idx]
    curve = []
    for share in (0.25, 0.5, 1.0):
        sub = dict(pipe, subsample=max(200, int(len(idx) * share)))
        f = lab.fit(sub)
        tr_auc = roc_auc_score(f["fit_y"], f["fit_raw"]) if 0 < f["fit_y"].sum() < len(f["fit_y"]) else None
        va_auc = roc_auc_score(f["val_y"], f["val_raw"]) if 0 < f["val_y"].sum() < len(f["val_y"]) else None
        curve.append(dict(rows=int(f["rows"]), train_auc=tr_auc, validation_auc=va_auc))
    segs = {s: int((lab.train["seg"][idx] == s).sum()) for s in lab.segments}
    return dict(
        model=dict(gbm="Gradient boosting", gbm_reg="Regularized gradient boosting", tree_deep="Decision tree (unlimited depth)", logistic="Logistic regression")[pipe["model"]],
        features=len(pipe["features"]),
        training_window_days=list(pipe["train_days"]),
        rows=int(len(idx)),
        positive_rate=float(y.mean()),
        segment_rows=segs,
        learning_curve=curve,
    )


def c_offline(lab):
    ev = lab.evaluate()
    return dict(validation=ev["offline"], threshold=ev["threshold"])


def c_registry(lab, config=None):
    ev = lab.evaluate()
    pipe = ev["pipe"]
    approved = ev["fitted"]
    models = [dict(version="v3", status="approved", train_days=list(pipe["train_days"]), features=len(approved["features"]), validation_auc=ev["offline"]["auc"], artifact="sha256:7f3a…c21")]
    served = pipe["served_version"]
    if served != "v3":
        v2 = lab.fit(pipe, "v2")
        models.append(dict(version="v2", status="serving", train_days=list(v2["train_days"]), features=len(v2["features"]), artifact="sha256:1b9e…04d"))
    if config and config.get("scenario") == "advanced:model_a_vs_b":
        b_pipe = lab.apply_fixes([dict(fix="drop_feature", feature=lab.p["leak"][0])])
        b = lab.evaluate([dict(fix="drop_feature", feature=lab.p["leak"][0])])
        models.append(dict(version="candidate-B", status="rejected", train_days=list(b_pipe["train_days"]), features=len(b_pipe["features"]), validation_auc=b["offline"]["auc"], artifact="sha256:9a0c…e71"))
        models[0]["version"] = "candidate-A (v3)"
    age = C.PROD_END - pipe["train_days"][1]
    return dict(models=models, approved_version="v3", serving_version=served, serving_artifact=models[-1]["artifact"] if served != "v3" else models[0]["artifact"], model_age_days=age, deployed_day=C.TRAIN_END)


def c_timeline(lab):
    ev, pipe, X, p, y_mon = _c_all_scores(lab)
    thr = ev["threshold"]
    value = lab.prod["X"][lab.p["value_feature"]] if lab.p.get("value_feature") else None
    out = []
    top = [f for f in lab.names[:3]]
    for lo in range(C.TRAIN_END, C.PROD_END, 10):
        m = (lab.prod["day"] >= lo) & (lab.prod["day"] < lo + 10)
        met = lab.metrics(y_mon[m], p[m], thr, None if value is None else value[m])
        matured = 100.0 if not pipe["label_delay"] else float(100 * (lab.prod["day"][m] < C.PROD_END - pipe["label_delay"]).mean())
        out.append(dict(days=f"{lo}-{lo + 9}", alert_rate=met["alert_rate"], precision=met["precision"], recall=met["recall"], cost_per_1k=met["cost_per_1k"], observed_positive_rate=met["positive_rate"], labels_matured_pct=matured, **{f"mean_{f}": float(X[f][m].mean()) for f in top}))
    return dict(buckets=out, offline_cost_per_1k=ev["offline"]["cost_per_1k"], deployed_day=C.TRAIN_END, note="Monitored metrics use labels as they arrive.")


def c_segments(lab):
    ev, pipe, X, p, y_mon = _c_all_scores(lab)
    idx = lab._training_rows(pipe)
    thr = ev["threshold"]
    out = []
    segments = list(dict.fromkeys(list(lab.segments) + [str(x) for x in np.unique(lab.prod["seg"])]))
    for s in segments:
        m = lab.prod["seg"] == s
        if not m.any():
            continue
        met = lab.metrics(y_mon[m], p[m], thr, None)
        out.append(dict(segment=s, seen_before_deployment=bool((lab.train["seg"] == s).any()), training_share=float((lab.train["seg"][idx] == s).mean()), production_share=float(m.mean()), precision=met["precision"], recall=met["recall"], alert_rate=met["alert_rate"], cost_per_1k=met["cost_per_1k"]))
    return dict(segment=lab.p["segment"][0], rows=out)


def c_importance(lab):
    ev = lab.evaluate()
    fitted = ev["fitted"]
    X, y = fitted["val_X"], fitted["val_y"]
    if y.min() == y.max():
        return dict(features=[])
    base = roc_auc_score(y, fitted["model"].predict_proba(X)[:, 1])
    r = np.random.default_rng(lab.seed)
    out = []
    for j, f in enumerate(fitted["features"]):
        if f.startswith("noise_") and f not in {"noise_01", "noise_02", "noise_03"}:
            continue
        Xp = X.copy()
        Xp[:, j] = r.permutation(Xp[:, j])
        drop = base - roc_auc_score(y, fitted["model"].predict_proba(Xp)[:, 1])
        out.append(dict(feature=f, auc_drop=float(drop), availability=availability(lab, f)))
    total = sum(max(0, o["auc_drop"]) for o in out) or 1
    for o in out:
        o["share"] = max(0, o["auc_drop"]) / total
    return dict(baseline_auc=float(base), features=sorted(out, key=lambda o: -o["auc_drop"]))


def _reliability(p, y):
    bins = []
    for lo in np.linspace(0, 0.9, 10):
        m = (p >= lo) & (p < lo + 0.1 + (1e-9 if lo >= 0.9 else 0))
        if m.any():
            bins.append(dict(bin=f"{lo:.1f}-{lo + 0.1:.1f}", predicted=float(p[m].mean()), observed=float(y[m].mean()), count=int(m.sum())))
    ece = sum(abs(b["predicted"] - b["observed"]) * b["count"] for b in bins) / max(1, len(p))
    return bins, ece


def c_calibration(lab):
    ev, pipe, X, p, y_mon = _c_all_scores(lab)
    fitted = ev["fitted"]
    val_p = lab.scores(pipe, fitted, fitted["val_X"])
    vb, vece = _reliability(val_p, fitted["val_y"])
    matured = lab.prod["day"] < C.PROD_END - (pipe["label_delay"] or 0)
    pb, pece = _reliability(p[matured], y_mon[matured])
    return dict(validation=vb, validation_ece=vece, production=pb, production_ece=pece)


def c_threshold(lab):
    ev = lab.evaluate()
    pipe, fitted = ev["pipe"], ev["fitted"]
    val_p = lab.scores(pipe, fitted, fitted["val_X"])
    curve = []
    for t in np.concatenate([np.linspace(0.01, 0.05, 5), np.linspace(0.1, 0.95, 18)]):
        m = lab.metrics(fitted["val_y"], val_p, t, None)
        curve.append(dict(threshold=float(t), precision=m["precision"], recall=m["recall"], cost_per_1k=m["cost_per_1k"]))
    best = min(curve, key=lambda c: c["cost_per_1k"])
    deployed_cost = lab.metrics(fitted["val_y"], val_p, ev["threshold"], None)["cost_per_1k"]
    return dict(curve=curve, deployed=ev["threshold"], deployed_cost=deployed_cost, optimal_cost=best["cost_per_1k"], cost_optimal=best["threshold"], costs=dict(false_positive=lab.p["fp_cost"], false_negative="transaction value × loss share" if lab.p.get("value_feature") else lab.p.get("fn_cost")))


def c_label_audit(lab):
    ev = lab.evaluate()
    pipe = ev["pipe"]
    r = np.random.default_rng(lab.seed + 11)
    rows = []
    for s in lab.segments:
        idx = np.where(lab.train["seg"] == s)[0]
        pick = r.choice(idx, min(150, len(idx)), replace=False)
        rows.append(dict(segment=s, audited=int(len(pick)), mismatches=int((lab.train["y_obs"][pick] != lab.train["y"][pick]).sum())))
    maturity = []
    delay = pipe["label_delay"]
    for age in (0, 7, 14, 21, 28, 35):
        maturity.append(dict(age_days=age, labels_arrived_pct=100.0 if not delay else float(100 * min(1.0, max(0.0, (age - delay + 7) / 7)))))
    return dict(audit=rows, maturity=maturity, note="Audit compares recorded training labels with an independent gold review.")


def c_pipeline_trace(lab):
    ev = lab.evaluate()
    pipe = ev["pipe"]
    X = lab.served(pipe)
    idx = np.where(lab.prod["day"] >= C.ONSET)[0][::97][:8]
    feats = [f for f in pipe["features"] if not f.startswith("noise_") and f != "segment_code"]
    rows = []
    for i in idx:
        for f in feats:
            expected = float(lab.prod["X"][f][i])
            served = float(X[f][i])
            if f == lab.p["leak"][0]:
                expected_text = "not yet available at scoring time"
            else:
                expected_text = round(expected, 3)
            rows.append(dict(event=f"EVT-{i:05d}", day=int(lab.prod["day"][i]), feature=f, training_logic=expected_text, served=round(served, 3), ratio=None if expected == 0 else round(served / expected, 3), match=bool(abs(served - expected) <= 1e-6 * max(1, abs(expected)))))
    return dict(rows=rows, note="training_logic recomputes each feature from the raw event with the offline feature code.")


def c_schema(lab):
    ev = lab.evaluate()
    pipe = ev["pipe"]
    out = []
    for f in lab.names:
        versions = [dict(version="v1", from_day=0, unit=lab.meta[f]["unit"], nullable=False)]
        if f in pipe["serve"]["scale"]:
            versions.append(dict(version="v2", from_day=C.ONSET, unit=f"minor units (1/{int(pipe['serve']['scale'][f]['factor'])} {lab.meta[f]['unit']})", nullable=False))
        if f in pipe["serve"]["missing"]:
            versions.append(dict(version="v2", from_day=C.ONSET, unit=lab.meta[f]["unit"], nullable=True, note="Field made optional by producer"))
        out.append(dict(field=f, versions=versions))
    return dict(fields=out)


def c_entity_graph(lab):
    if not lab.p.get("ring"):
        return dict(entities=[], nodes=[], edges=[], note="This profile has no entity network.")
    tr = lab.train
    ent, y = tr["entity"], tr["y_obs"]
    base = y.mean()
    rows = []
    for e in np.unique(ent):
        m = ent == e
        if m.sum() >= 12:
            rows.append(dict(entity=f"{lab.p['entity'][0][:3].upper()}-{e:03d}", id=int(e), transactions=int(m.sum()), fraud_rate=float(y[m].mean()), lift=float(y[m].mean() / max(base, 1e-9))))
    top = sorted(rows, key=lambda r: -r["lift"])[:14]
    nodes, edges = [], []
    for r in top:
        nodes.append(dict(id=r["entity"], type="entity", fraud_rate=r["fraud_rate"]))
        m = ent == r["id"]
        clusters, counts = np.unique(tr["cluster"][m].astype(str), return_counts=True)
        for c, n in zip(clusters, counts):
            if n >= 3:
                cid = f"DEVICE-{c}"
                if not any(nd["id"] == cid for nd in nodes):
                    nodes.append(dict(id=cid, type="device_cluster"))
                edges.append(dict(source=r["entity"], target=cid, weight=int(n)))
    return dict(entities=top, nodes=nodes, edges=edges, entity_type=lab.p["entity"][0])


CLASSIFICATION_PROBES = OrderedDict(
    raw=(2, "Raw data sample", c_raw),
    eda=(5, "EDA: train vs production", c_eda),
    features=(2, "Feature catalogue", c_features),
    training=(6, "Training & learning curve", c_training),
    offline=(3, "Offline evaluation", c_offline),
    registry=(2, "Model registry", c_registry),
    timeline=(4, "Production monitoring", c_timeline),
    segments=(4, "Segment performance", c_segments),
    importance=(6, "Permutation importance", c_importance),
    calibration=(4, "Calibration", c_calibration),
    threshold=(4, "Threshold & cost curve", c_threshold),
    label_audit=(8, "Label audit & maturity", c_label_audit),
    pipeline_trace=(6, "Serving pipeline trace", c_pipeline_trace),
    schema=(3, "Producer schema registry", c_schema),
    entity_graph=(6, "Entity network (rings)", c_entity_graph),
)


# ------------------------------------------------------------------ forecasting probes
def _f_all(lab, fixes=()):
    ev = lab.evaluate(fixes)
    pipe = ev["pipe"]
    days = list(range(F.TRAIN_END, F.PROD_END))
    pred, meta, feats = lab.predict(pipe, ev["served_model"], lab.data["series"], days)
    rec = lab.recorded(pipe)
    recorded = np.array([rec[s][d] for s, d, _, _ in meta])
    if pipe["label_delay"]:
        young = np.array([d >= F.PROD_END - pipe["label_delay"] for _, d, _, _ in meta])
        recorded[young] *= 0.55
    return ev, pipe, pred, meta, feats, recorded


def f_raw(lab):
    ev, pipe, pred, meta, feats, recorded = _f_all(lab)
    rows = []
    for (s, d, dow, _), f, y, p in list(zip(meta, feats, recorded, pred))[::37][:14]:
        rows.append(dict(series=s, day=d, weekday=dow, actual_recorded=round(float(y), 2), forecast=round(float(p), 2), **{k: round(float(v), 3) for k, v in f.items() if k in ev["pipe"]["features"]}))
    return dict(production=rows, unit=lab.p["unit"])


def f_timeline(lab):
    ev, pipe, pred, meta, feats, recorded = _f_all(lab)
    series = {}
    for (s, d, _, _), y, p in zip(meta, recorded, pred):
        series.setdefault(s, []).append(dict(day=d, actual=float(y), forecast=float(p)))
    return dict(series=series, onset=F.ONSET, unit=lab.p["unit"], events=[d for d in lab.world["events"] if d >= F.TRAIN_END])


def f_series(lab):
    ev, pipe, pred, meta, feats, recorded = _f_all(lab)
    out = []
    history = {s: int(np.sum(~np.isnan(lab.data["y"][s][: F.TRAIN_END]))) for s in lab.data["series"]}
    train_series = pipe["train_series"] or lab.series
    for s in lab.data["series"]:
        m = np.array([ss == s and d >= F.EVAL[0] for ss, d, _, _ in meta])
        met = lab.metrics(recorded[m], pred[m])
        out.append(dict(series=s, wape=met["wape"], bias=met["bias"], history_days=history[s], in_training=s in train_series))
    return dict(rows=out)


def f_residual_dow(lab):
    ev, pipe, pred, meta, feats, recorded = _f_all(lab)
    out = []
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for k in range(7):
        m = np.array([d % 7 == k and d >= F.EVAL[0] for _, d, _, _ in meta])
        out.append(dict(weekday=names[k], mean_error_pct=float(np.sum(pred[m] - recorded[m]) / max(1e-9, np.sum(recorded[m])) * 100)))
    return dict(rows=out)


def f_events(lab):
    ev, pipe, pred, meta, feats, recorded = _f_all(lab)
    event_days = set(lab.world["events"])
    is_event = np.array([d in event_days for _, d, _, _ in meta])
    ev_m = lab.metrics(recorded[is_event], pred[is_event]) if is_event.any() else None
    normal = lab.metrics(recorded[~is_event], pred[~is_event])
    drv = np.array([f[lab.driver] > 0 for f in feats])
    driver_days = lab.metrics(recorded[drv], pred[drv]) if drv.any() else None
    return dict(calendar=sorted(d for d in event_days if d >= F.TRAIN_END), event_days=ev_m, normal_days=normal, driver=lab.driver, driver_days=driver_days)


def f_eda(lab):
    ev, pipe, pred, meta, feats, recorded = _f_all(lab)
    train_feats, _ = lab._rows(pipe, pipe["train_series"] or lab.series, list(range(300, F.TRAIN_END)), serving=False)
    out = []
    for f in ["lag7", "roll28", lab.driver, "event"] + (["same_day_drawdown"] if "same_day_drawdown" in pipe["features"] else []):
        a = np.array([r[f] for r in train_feats])
        b = np.array([r[f] for r in feats])
        out.append(dict(feature=f, train=stats(a), production=stats(b), psi=psi(a, b), histogram=hist(a, b)))
    by_series = []
    for s in lab.data["series"]:
        a = np.array([r[lab.driver] for r, (ss, *_rest) in zip(feats, meta) if ss == s])
        by_series.append(dict(series=s, driver_active_pct=float((a > 0).mean() * 100) if len(a) else 0, driver_mean_when_active=float(a[a > 0].mean()) if (a > 0).any() else 0))
    return dict(features=out, driver_by_series=by_series)


def f_training(lab):
    ev = lab.evaluate()
    pipe, fitted = ev["pipe"], ev["fitted"]
    tr_true, tr_pred = fitted["fit"]
    va_true, va_pred = fitted["val"]
    return dict(
        model=dict(ridge="Ridge regression on log demand", ridge_overfit="Ridge with 60 lag features and no regularization", mean="Per-series average")[pipe["model"]],
        training_days=list(pipe["train_days"]),
        series=pipe["train_series"] or lab.series,
        features=pipe["features"] + (["dow", "series×dow"] if pipe["seasonality"] else []),
        train_wape=lab.metrics(tr_true, tr_pred)["wape"],
        validation_wape=lab.metrics(va_true, va_pred)["wape"],
    )


def f_registry(lab, config=None):
    ev = lab.evaluate()
    pipe = ev["pipe"]
    models = [dict(version="v3", status="approved", train_days=list(pipe["train_days"]), features=pipe["features"] + (["dow"] if pipe["seasonality"] else []), validation_wape=ev["offline"]["wape"], artifact="sha256:5d2e…a90")]
    if pipe["served_version"] != "v3":
        v2 = lab.fit(pipe, "v2")
        models.append(dict(version="v2", status="serving", train_days=list(pipe["train_days"]), features=v2["features"], artifact="sha256:c40b…17f"))
    return dict(models=models, approved_version="v3", serving_version=pipe["served_version"], model_age_days=F.PROD_END - pipe["train_days"][1], deployed_day=F.TRAIN_END)


def f_pipeline_trace(lab):
    ev = lab.evaluate()
    pipe = ev["pipe"]
    pick = [(s, d) for s in lab.series[:2] for d in (F.ONSET + 3, F.ONSET + 17)]
    rows = []
    for s, d in pick:
        served, meta_s = lab._rows(pipe, [s], [d], serving=True)
        offline, _ = lab._rows(pipe, [s], [d], serving=False)
        for f in ["roll28", lab.driver, "lag7"]:
            a, b = offline[0][f], served[0][f]
            rows.append(dict(series=s, day=d, feature=f, training_logic=round(float(a), 3), served=round(float(b), 3), match=bool(abs(a - b) < 1e-6)))
        rows.append(dict(series=s, day=d, feature="dow", training_logic=d % 7, served=meta_s[0][2], match=d % 7 == meta_s[0][2]))
    return dict(rows=rows)


def f_schema(lab):
    ev = lab.evaluate()
    pipe = ev["pipe"]
    out = []
    for s in lab.data["series"]:
        versions = [dict(version="v1", from_day=0, unit=lab.p["unit"])]
        if s in pipe["serve"]["units"]:
            versions.append(dict(version="v2", from_day=F.ONSET - F.HORIZON, unit=f"cases of {int(pipe['serve']['units'][s])}"))
        out.append(dict(series=s, versions=versions))
    feed = [dict(field=lab.driver, status="stopped" if lab.driver in pipe["serve"]["missing"] else "ok", since=pipe["serve"]["missing"].get(lab.driver))]
    return dict(series=out, feeds=feed)


def f_label_audit(lab):
    ev = lab.evaluate()
    pipe = ev["pipe"]
    rec = lab.recorded(pipe)
    rows = []
    for s in lab.series:
        days = np.arange(F.TRAIN_END - 120, F.TRAIN_END)
        truth = lab.data["y"][s][days]
        diff = np.abs(rec[s][days] - truth) > 0.05 * np.maximum(1, truth)
        rows.append(dict(series=s, audited_days=int(len(days)), mismatches=int(diff.sum())))
    completeness = []
    for age in (0, 3, 7, 10, 14, 21):
        completeness.append(dict(age_days=age, reported_pct=100.0 if not pipe["label_delay"] or age >= pipe["label_delay"] else 55.0))
    return dict(audit=rows, completeness=completeness)


def f_importance(lab):
    ev = lab.evaluate()
    fitted = ev["fitted"]
    coef = np.abs(np.array(fitted["coef"]))
    k = len(fitted["features"])
    out = [dict(feature=f, weight=float(coef[i]), availability=availability(lab, f)) for i, f in enumerate(fitted["features"][:k])]
    rest = coef[k:]
    if len(rest):
        out.append(dict(feature="series & weekday effects", weight=float(rest.mean()), availability="Known at forecast time"))
    total = sum(o["weight"] for o in out) or 1
    for o in out:
        o["share"] = o["weight"] / total
    return dict(features=sorted(out, key=lambda o: -o["weight"]))


FORECAST_PROBES = OrderedDict(
    raw=(2, "Raw data sample", f_raw),
    eda=(5, "EDA: train vs production", f_eda),
    training=(5, "Training fit", f_training),
    registry=(2, "Model registry", f_registry),
    timeline=(4, "Forecast vs actual", f_timeline),
    series=(4, "Per-series accuracy", f_series),
    residual_dow=(3, "Error by weekday", f_residual_dow),
    events=(3, "Events & driver days", f_events),
    importance=(4, "Model weights", f_importance),
    label_audit=(6, "Actuals audit & completeness", f_label_audit),
    pipeline_trace=(6, "Serving pipeline trace", f_pipeline_trace),
    schema=(3, "Producer schema & feeds", f_schema),
)


def probes_for(lab):
    return FORECAST_PROBES if lab.family == "forecasting" else CLASSIFICATION_PROBES


def run_probe(lab, name, config=None):
    probes = probes_for(lab)
    if name not in probes:
        raise ValueError("Unknown probe")
    minutes, label, fn = probes[name]
    data = fn(lab, config) if name == "registry" else fn(lab)
    return dict(probe=name, label=label, minutes=minutes, data=clean(data))


# ------------------------------------------------------------------ stages, scoring, agent
def overview(lab, config):
    ev = lab.evaluate()
    probes = probes_for(lab)
    monitor = run_probe(lab, "timeline")["data"]
    stages = [
        dict(key="raw", title="Raw data", summary="Synthetic records generated from a causal model; production data arrives daily."),
        dict(key="eda", title="EDA", summary="Compare training and production distributions."),
        dict(key="features", title="Feature engineering", summary=f"{len(ev['pipe']['features'])} model features."),
        dict(key="train", title="Train", summary=f"Model trained on days {ev['pipe']['train_days'][0]}-{ev['pipe']['train_days'][1]}."),
        dict(key="evaluate", title="Evaluate", summary="Offline validation looked acceptable, so the model was approved."),
        dict(key="deploy", title="Deploy", summary="Deployed to production on day " + str(C.TRAIN_END if lab.family == "classification" else F.TRAIN_END) + "."),
        dict(key="production", title="Simulated production", summary="Monitoring shows the behaviour below."),
        dict(key="investigate", title="Investigate", summary="Run probes; each costs investigation minutes."),
        dict(key="fix", title="Fix", summary="Choose failure types and fixes."),
        dict(key="rescore", title="Rescore", summary="Retrain, redeploy and compare with the hidden ground truth."),
    ]
    return clean(
        dict(
            config={k: v for k, v in config.items() if k != "failures"},
            family=lab.family,
            profile=dict(key=lab.p["key"], title=lab.p["title"], target=lab.p.get("target"), unit=lab.p.get("unit"), group=lab.p.get("group", "Forecasting"), visual=lab.p.get("visual")),
            stages=stages,
            offline=ev["offline"],
            monitored=ev["monitored"],
            primary=ev["primary"],
            monitoring=monitor,
            probes=[dict(name=k, label=v[1], minutes=v[0]) for k, v in probes.items() if not (k == "entity_graph" and not lab.p.get("ring"))],
            failure_types=[dict(key=k, label=v["label"], explain=v["explain"]) for k, v in catalog.FAILURES.items() if lab.family in v["families"]],
            fixes=[dict(key=k, **v) for k, v in catalog.FIXES.items()],
            fix_features=lab.fix_choices(),
            budget_minutes=INVESTIGATION_BUDGET,
            ring_entity=lab.p.get("entity", [None])[0] if lab.p.get("ring") else None,
        )
    )


def _fix_matches(user, correct):
    if user.get("fix") != correct["fix"]:
        return False
    if not catalog.FIXES[correct["fix"]]["needs_feature"]:
        return True
    return user.get("feature") in [correct.get("feature")] + correct.get("alternatives", [])


ALTERNATIVE_FIXES = {"class_imbalance": {"tune_threshold"}, "poor_calibration": {"tune_threshold"}}


def ground_truth(lab, config):
    targets = getattr(lab, "targets", {})
    return clean(
        dict(
            failures=[dict(key=f, label=catalog.FAILURES[f]["label"], explain=catalog.FAILURES[f]["explain"]) for f in lab.failures],
            correct_fixes=lab.correct_fixes(),
            targets=targets,
            ring=[f"{lab.p['entity'][0][:3].upper()}-{e:03d}" for e in lab.world.get("ring_ids", [])] if lab.family == "classification" else [],
            seed=config["seed"],
        )
    )


def score(lab, config, diagnosis):
    chosen = set(diagnosis.get("failures", []))
    actual = set(lab.failures)
    tp = len(chosen & actual)
    f1 = 2 * tp / max(1, len(chosen) + len(actual))
    fixes = [f for f in diagnosis.get("fixes", []) if f.get("fix") in catalog.FIXES]
    correct = lab.correct_fixes()
    unnecessary = [
        f
        for f in fixes
        if not any(_fix_matches(f, c) for c in correct)
        and not any(f.get("fix") in ALTERNATIVE_FIXES.get(a, set()) for a in actual)
    ]
    before, after, oracle = lab.evaluate(), lab.evaluate(fixes), lab.evaluate(correct)
    key = before["primary"]
    parts = []
    b, a, o = before["true"][key], after["true"][key], oracle["true"][key]
    if b - o > 0.03 * max(1e-9, abs(b)):
        parts.append(max(0.0, min(1.0, (b - a) / (b - o))))

    def monitoring_error(r):
        return abs(r["monitored"][key] - r["true"][key]) / max(1e-9, abs(r["true"][key]))

    mb, ma, mo = monitoring_error(before), monitoring_error(after), monitoring_error(oracle)
    if mb - mo > 0.1:
        parts.append(max(0.0, min(1.0, (mb - ma) / (mb - mo))))
    applied = sum(any(_fix_matches(f, c) for f in fixes) for c in correct)
    recovery = float(np.mean(parts)) if parts else applied / max(1, len(correct))
    used = diagnosis.get("probes_used", [])
    minutes = sum(probes_for(lab)[p][0] for p in used if p in probes_for(lab))
    efficiency = max(0.0, 1 - max(0, minutes - INVESTIGATION_BUDGET * 0.5) / INVESTIGATION_BUDGET)
    precision_fixes = 1 - len(unnecessary) / max(1, len(fixes)) if fixes else 0.0
    ring_score = None
    truth = ground_truth(lab, config)
    if truth["ring"] and diagnosis.get("ring"):
        guess = {g.strip().upper() for g in diagnosis["ring"] if g.strip()}
        ring_score = len(guess & set(truth["ring"])) / max(1, len(guess | set(truth["ring"])))
    total = 45 * f1 + 35 * recovery + 10 * precision_fixes + 10 * efficiency
    return clean(
        dict(
            score=round(total, 1),
            parts=dict(diagnosis_f1=f1, recovery=recovery, fix_precision=precision_fixes, efficiency=efficiency, ring_jaccard=ring_score),
            metric=key,
            before=dict(true=before["true"], monitored=before["monitored"]),
            after=dict(true=after["true"], monitored=after["monitored"]),
            oracle=dict(true=oracle["true"], monitored=oracle["monitored"]),
            unnecessary_fixes=unnecessary,
            minutes_used=minutes,
            ground_truth=truth,
        )
    )


def auto_investigate(lab, config=None):
    """Deterministic agent: run every probe, apply heuristics, propose diagnosis and fixes."""
    ev = lab.evaluate()
    results = {k: run_probe(lab, k, config)["data"] for k in probes_for(lab) if not (k == "entity_graph" and not getattr(lab, "p", {}).get("ring"))}
    found, fixes, rationale = [], [], []

    def add(failure, fix, why):
        if failure not in found:
            found.append(failure)
            rationale.append(dict(failure=failure, evidence=why))
        if fix and not any(f == fix for f in fixes):
            fixes.append(fix)

    reg = results["registry"]
    if reg["serving_version"] != reg["approved_version"]:
        add("version_mismatch", dict(fix="redeploy_version"), f"Serving {reg['serving_version']} while {reg['approved_version']} is approved")
    if lab.family == "classification":
        trace = results["pipeline_trace"]["rows"]
        by_feature = {}
        for r in trace:
            by_feature.setdefault(r["feature"], []).append(r)
        for f, rows in by_feature.items():
            ratios = [r["ratio"] for r in rows if r["ratio"] is not None]
            if f == lab.p["leak"][0]:
                continue
            if ratios and all(abs(x - 100) < 1 for x in ratios):
                add("schema_change", dict(fix="fix_units", feature=f), f"{f} served at 100x the training value")
            elif rows and all(r["served"] == 0 and r["training_logic"] not in (0, 0.0) for r in rows):
                add("missing_feature", dict(fix="restore_feature", feature=f), f"{f} served as 0 for every traced event")
            elif ratios and np.median(ratios) < 0.6 and not all(r["match"] for r in rows):
                others = [g for g in by_feature if g != f]
                swapped = next((g for g in others if all(abs(r["served"] - s["training_logic"]) < 1e-3 for r, s in zip(rows, by_feature[g]) if isinstance(s["training_logic"], float))), None)
                if swapped:
                    add("pipeline_bug", dict(fix="fix_pipeline", feature=f), f"{f} carries the value of {swapped}")
                else:
                    add("training_serving_skew", dict(fix="fix_pipeline", feature=f), f"{f} served at ~{np.median(ratios):.2f}x the offline value")
        imp = results["importance"]["features"]
        for row in imp[:2]:
            if row["share"] > 0.35 and row["feature"] == lab.p["leak"][0]:
                add("label_leakage", dict(fix="drop_feature", feature=row["feature"]), f"{row['feature']} dominates importance and is only known after the outcome")
            if row["share"] > 0.3 and row["feature"] == lab.p["future"][0]:
                add("feature_leakage", dict(fix="drop_feature", feature=row["feature"]), f"{row['feature']} dominates and uses future information")
        for row in results["label_audit"]["audit"]:
            if row["mismatches"] / max(1, row["audited"]) > 0.03:
                add("wrong_labels", dict(fix="clean_labels"), f"{row['mismatches']} of {row['audited']} audited labels wrong in {row['segment']}")
        if results["label_audit"]["maturity"][2]["labels_arrived_pct"] < 60:
            add("delayed_labels", dict(fix="label_lag_eval"), "Labels younger than ~3 weeks have not arrived")
        tr = results["training"]
        if tr["positive_rate"] < 0.02 and ev["monitored"]["recall"] < 0.4:
            add("class_imbalance", dict(fix="rebalance"), f"Only {tr['positive_rate']:.1%} positives; monitored recall {ev['monitored']['recall']:.0%}")
        seg = results["segments"]["rows"]
        if any(r["training_share"] == 0 and r["seen_before_deployment"] and r["production_share"] > 0.1 for r in seg):
            add("biased_sample", dict(fix="resample_representative"), "Segments that existed at training time were left out of the training sample")
        new_segments = [r for r in seg if not r["seen_before_deployment"] and r["production_share"] > 0.1]
        if new_segments:
            add("data_drift", dict(fix="retrain_recent"), f"New population '{new_segments[0]['segment']}' appeared after deployment ({new_segments[0]['production_share']:.0%} of traffic)")
        curve = tr["learning_curve"][-1]
        if curve["train_auc"] and curve["validation_auc"] and curve["train_auc"] - curve["validation_auc"] > 0.2:
            add("overfitting", dict(fix="regularize"), f"Train AUC {curve['train_auc']:.2f} vs validation {curve['validation_auc']:.2f}")
        elif curve["train_auc"] and curve["train_auc"] < 0.72:
            add("underfitting", dict(fix="increase_capacity"), f"Train AUC only {curve['train_auc']:.2f}")
        th = results["threshold"]
        if th["deployed_cost"] > 1.15 * th["optimal_cost"] and abs(th["deployed"] - th["cost_optimal"]) > 0.02 and "class_imbalance" not in found:
            add("bad_threshold", dict(fix="tune_threshold"), f"Deployed threshold {th['deployed']:.2f} vs cost-optimal {th['cost_optimal']:.2f}")
        if results["calibration"]["validation_ece"] > 0.08:
            add("poor_calibration", dict(fix="recalibrate"), f"Validation ECE {results['calibration']['validation_ece']:.2f}")
        if reg["model_age_days"] > 150:
            add("stale_model", dict(fix="retrain_recent"), f"Model trained {reg['model_age_days']} days before the end of the window")
        eda = results["eda"]["features"]
        drifted = [r for r in eda if r["psi"] > 0.25 and r["feature"] not in {lab.p["leak"][0], lab.p["future"][0], "segment_code"}]
        drifted += [dict(feature=r["feature"], psi=r["psi"], segment=r["segment"]) for r in results["eda"]["segment_drift"] if r["psi"] > 0.6]
        explained = {r.get("feature") for r in fixes}
        if any(r["feature"] not in explained for r in drifted) and not {"schema_change", "missing_feature", "pipeline_bug", "training_serving_skew"} & set(found):
            add("data_drift", dict(fix="retrain_recent"), f"PSI {drifted[0]['psi']:.2f} on {drifted[0]['feature']}")
        buckets = results["timeline"]["buckets"]
        rising = buckets[-2]["cost_per_1k"] > 1.3 * max(1e-9, buckets[0]["cost_per_1k"]) if len(buckets) > 2 else False
        if not found and (rising or ev["monitored"]["cost_per_1k"] > 1.25 * ev["offline"]["cost_per_1k"]):
            add("concept_drift", dict(fix="retrain_recent"), "Inputs look stable but production cost keeps rising")
    else:
        reg_features = results["registry"]["models"][0]["features"]
        if "dow" not in reg_features:
            add("seasonality_failure", dict(fix="add_seasonality"), "No weekday features; errors swing by weekday")
        if "event" not in reg_features:
            add("holiday_event", dict(fix="add_event_feature"), "Event days are not in the feature set")
        for row in results["series"]["rows"]:
            if row["history_days"] == 0:
                add("cold_start", dict(fix="pooled_fallback"), f"{row['series']} has no training history")
            elif not row["in_training"]:
                add("biased_sample", dict(fix="resample_representative"), f"{row['series']} absent from training")
        for row in results["schema"]["series"]:
            if len(row["versions"]) > 1:
                add("schema_change", dict(fix="fix_units", feature="actuals"), f"{row['series']} now reported in {row['versions'][-1]['unit']}")
        for feed in results["schema"]["feeds"]:
            if feed["status"] == "stopped":
                add("missing_feature", dict(fix="restore_feature", feature=feed["field"]), f"{feed['field']} feed stopped on day {feed['since']}")
        for r in results["pipeline_trace"]["rows"]:
            if not r["match"] and r["feature"] == "dow":
                add("pipeline_bug", dict(fix="fix_pipeline", feature="dow"), "Serving weekday differs from the calendar")
            if not r["match"] and r["feature"] == lab.driver and r["day"] < F.ONSET + 30:
                add("training_serving_skew", dict(fix="fix_pipeline", feature=lab.driver), f"{lab.driver} served as a flag instead of its intensity")
        if results["label_audit"]["completeness"][1]["reported_pct"] < 80:
            add("delayed_labels", dict(fix="label_lag_eval"), "Recent actuals are incomplete")
        for row in results["label_audit"]["audit"]:
            if row["mismatches"] / max(1, row["audited_days"]) > 0.1:
                add("wrong_labels", dict(fix="clean_labels"), f"{row['mismatches']} audited days differ in {row['series']}")
        tr = results["training"]
        if tr["validation_wape"] > 1.5 * max(tr["train_wape"], 1e-6) and tr["validation_wape"] > 0.12:
            add("overfitting", dict(fix="regularize"), f"Train WAPE {tr['train_wape']:.2f} vs validation {tr['validation_wape']:.2f}")
        if tr["model"] == "Per-series average":
            add("underfitting", dict(fix="increase_capacity"), "Model ignores lags, weekdays and drivers")
        for row in results["importance"]["features"][:2]:
            if row["feature"] == "same_day_drawdown" and row["share"] > 0.25:
                add("feature_leakage", dict(fix="drop_feature", feature="same_day_drawdown"), "End-of-day drawdown dominates the model")
        if results["registry"]["model_age_days"] > 200:
            add("stale_model", dict(fix="retrain_recent"), f"Model is {results['registry']['model_age_days']} days old")
        drv = results["eda"]["driver_by_series"]
        means = [r["driver_mean_when_active"] for r in drv if r["driver_mean_when_active"]]
        if means and max(means) > 2 * np.median(means):
            add("data_drift", dict(fix="retrain_recent"), f"{lab.driver} intensity far above training range for one series")
        dd = results["events"]["driver_days"]
        if dd and dd["bias"] > 0.2 and "data_drift" not in found:
            add("concept_drift", dict(fix="retrain_recent"), f"Forecasts {dd['bias']:.0%} too high on {lab.driver} days")
    probes_used = list(results)
    return clean(dict(agent="Auto-investigator (deterministic heuristics)", failures=found, fixes=fixes, rationale=rationale, probes_used=probes_used))
