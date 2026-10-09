"""Classification labs: fraud, churn, maintenance, IoT, vision features, RAG and recommendation.

Data come from a latent causal model: each feature is a transform of a standard-normal
latent and the label is a logistic function of those latents. Failures change the world
that produced production data, the training sample, or the serving pipeline. Because the
true labels are known, every metric can be computed both as the business experiences it and
as the monitoring dashboard reports it.
"""

import copy
import json

import numpy as np
from scipy.stats import norm
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

TRAIN_END, RETRAIN_END, PROD_END, ONSET = 180, 200, 240, 205
EVAL = (200, 240)
N_TRAIN, N_PROD = 6000, 6000


def sigmoid(x):
    return 1 / (1 + np.exp(-np.clip(x, -30, 30)))


def transform(dist, a, b, z):
    if dist == "normal":
        return a + b * z
    if dist == "lognormal":
        return np.exp(a + b * z)
    if dist == "uniform":
        return a + (b - a) * norm.cdf(z)
    if dist == "binary":
        return (norm.cdf(z) > 1 - a).astype(float)
    return np.maximum(0.0, np.floor(a + np.sqrt(a) * z + 0.5))


class ClassificationLab:
    family = "classification"

    def __init__(self, profile, failures, seed, params=None):
        self.p, self.failures, self.seed = profile, list(failures), seed
        self.params = params or {}
        self.names = [f[0] for f in profile["features"]]
        self.meta = {f[0]: dict(dist=f[1], unit=f[5], description=f[6], coef=f[4]) for f in profile["features"]}
        rng = np.random.default_rng(seed)
        self.segments = profile["segment"][1]
        self._choose_targets()
        self.world = self._base_world(rng)
        self.pipe = self._base_pipe()
        prod_world = copy.deepcopy(self.world)
        for failure in self.failures:
            self._inject(failure, prod_world)
        self._tune_intercept(self.world)
        prod_world["intercept"] = self.world["intercept"]
        if prod_world.get("retune"):
            self._tune_intercept(prod_world)
        self.prod_world = prod_world
        self.train = self._sample(self.world, N_TRAIN, 0, TRAIN_END, np.random.default_rng(seed + 1), prod=False)
        self.prod = self._sample(prod_world, N_PROD, TRAIN_END, PROD_END, np.random.default_rng(seed + 2), prod=True)
        if "wrong_labels" in self.failures:
            r = np.random.default_rng(seed + 3)
            seg = np.isin(self.train["seg"], [self.targets["noisy_segment"], self.segments[2]])
            pos, neg = seg & (self.train["y"] == 1), seg & (self.train["y"] == 0)
            y_obs = self.train["y"].copy()
            y_obs[pos & (r.random(len(y_obs)) < 0.7)] = 0
            y_obs[neg & (r.random(len(y_obs)) < 0.05)] = 1
            self.train["y_obs"] = y_obs
        vf = profile.get("value_feature")
        pos = self.train["y"] == 1
        self.mean_value = float(self.train["X"][vf][pos].mean()) if vf and pos.any() else 0.0
        self._cache = {}

    # ------------------------------------------------------------ world construction
    def _choose_targets(self):
        order = sorted(self.names, key=lambda n: -abs(self.meta[n]["coef"]))
        continuous = [n for n in order if self.meta[n]["dist"] in {"normal", "lognormal", "uniform", "poisson"}]
        used = set()

        def take(candidates):
            for c in candidates:
                if c not in used:
                    used.add(c)
                    return c
            return candidates[0]

        value = self.p.get("value_feature")
        units = value or next((n for n in continuous if self.meta[n]["dist"] in {"lognormal", "normal"}), continuous[0])
        used.add(units)
        self.targets = dict(units=units, concept_strong=order[0], concept_weak=order[-1], noisy_segment=self.segments[1])
        # Injected failures claim the strongest remaining features first so each one matters.
        slots = [("pipeline_bug", "swap"), ("missing_feature", "missing"), ("training_serving_skew", "skew"), ("data_drift", "drift")]
        slots.sort(key=lambda s: s[0] not in self.failures)
        smooth = [n for n in continuous if self.meta[n]["dist"] != "poisson"] or continuous
        for _failure, slot in slots:
            if slot == "swap":
                self.targets["swap"] = (take(continuous), take(continuous))
            else:
                # Distribution shifts need a continuous feature; low counts are too coarse to drift.
                self.targets[slot] = take(smooth if slot == "drift" else continuous)

    def _base_world(self, rng):
        # Scale gives the healthy model enough signal for failures to be clearly measurable.
        coef = {n: 1.4 * self.meta[n]["coef"] for n in self.names}
        f0 = self.names[0]
        f3 = self.names[min(3, len(self.names) - 1)]
        seg_coef = {
            self.segments[2]: {f0: -1.3 * coef[f0] - 0.4, f3: 1.0},
            self.segments[3]: {f0: -1.1 * coef[f0] - 0.3, f3: 0.8},
        }
        ring = self.p.get("ring")
        ring_ids = sorted(rng.choice(self.p["entity"][1], size=ring["size"], replace=False).tolist()) if ring else []
        return dict(coef=coef, seg_coef=seg_coef, intercept=0.0, base_rate=self.p["base_rate"], decouple={}, ramp={}, ring_ids=ring_ids)

    def _base_pipe(self):
        features = self.names + ["segment_code"]
        return dict(
            model="gbm",
            features=features,
            all_features=list(features),
            threshold=None,
            class_weight=None,
            calibration=None,
            train_days=(0, TRAIN_END),
            train_segments=None,
            subsample=None,
            serve=dict(missing={}, scale={}, swap=None, skew={}, unavailable=[]),
            label_delay=0,
            approved_version="v3",
            served_version="v3",
            extra_features=[],
        )

    def _inject(self, failure, prod):
        t, pipe = self.targets, self.pipe
        if failure == "data_drift":
            if self.p.get("drift_mode") == "segment":
                prod["decouple"][t["drift"]] = (1.0, 2.0, self.segments[3])
            else:
                # A new market launches after deployment: shifted inputs, weaker link to risk.
                prod["new_segment"] = dict(name="New market", share=0.4, feature=t["drift"], shift=1.6, coef_scale=-1.0)
        elif failure == "concept_drift":
            strong = prod["coef"][t["concept_strong"]]
            prod["coef"][t["concept_strong"]] = -0.6 * strong
            prod["coef"][t["concept_weak"]] += 1.3 * abs(strong)
            prod["retune"] = True
        elif failure == "label_leakage":
            leak = self.p["leak"][0]
            pipe["features"].append(leak)
            pipe["all_features"].append(leak)
            pipe["serve"]["unavailable"].append(leak)
            pipe["extra_features"].append(leak)
        elif failure == "feature_leakage":
            fut = self.p["future"][0]
            pipe["features"].append(fut)
            pipe["all_features"].append(fut)
            pipe["extra_features"].append(fut)
        elif failure == "class_imbalance":
            # Rare cases are few but distinctive: stronger signal per case, far fewer cases.
            self.world["base_rate"] = 0.012
            for w in (self.world, prod):
                w["coef"] = {k: v * 1.7 for k, v in w["coef"].items()}
            pipe["threshold"] = 0.5
        elif failure == "biased_sample":
            pipe["train_segments"] = self.segments[:2]
        elif failure == "missing_feature":
            pipe["serve"]["missing"][t["missing"]] = dict(from_day=ONSET, fill=0.0)
        elif failure == "schema_change":
            pipe["serve"]["scale"][t["units"]] = dict(from_day=ONSET, factor=100.0)
        elif failure == "pipeline_bug":
            pipe["serve"]["swap"] = (t["swap"][0], t["swap"][1], ONSET)
        elif failure == "training_serving_skew":
            pipe["serve"]["skew"][t["skew"]] = dict(factor=0.3, noise=0.35)
        elif failure == "overfitting":
            pipe["model"] = "tree_deep"
            pipe["subsample"] = 700
            noise = [f"noise_{k:02d}" for k in range(1, 21)]
            pipe["features"] += noise
            pipe["all_features"] += noise
            pipe["extra_features"] += noise
        elif failure == "underfitting":
            weakest = sorted(self.names, key=lambda n: abs(self.meta[n]["coef"]))[:2]
            pipe["model"] = "logistic"
            pipe["features"] = weakest
        elif failure == "bad_threshold":
            pipe["threshold"] = self.params.get("threshold", 0.93)
        elif failure == "poor_calibration":
            pipe["calibration"] = dict(a=3.2, b=2.6)
        elif failure == "delayed_labels":
            pipe["label_delay"] = 24
        elif failure == "version_mismatch":
            pipe["served_version"] = "v2"
        elif failure == "stale_model":
            pipe["train_days"] = (0, 60)
            strong, weak = self.targets["concept_strong"], self.targets["concept_weak"]
            self.world["ramp"] = {strong: -1.6 * self.meta[strong]["coef"], weak: 1.4}
            prod["ramp"] = dict(self.world["ramp"])

    def _latent_logit(self, world, z, day, seg, entity_ring):
        logit = np.zeros(len(day))
        for j, name in enumerate(self.names):
            coef = np.full(len(day), world["coef"][name], dtype=float)
            for s, mods in world["seg_coef"].items():
                if name in mods:
                    coef[seg == s] += mods[name]
            if name in world["ramp"]:
                coef = coef + world["ramp"][name] * day / PROD_END
            logit += coef * z[:, j]
        if self.p.get("interaction"):
            a, b, c = self.p["interaction"]
            ia, ib = self.names.index(a), self.names.index(b)
            logit += c * ((z[:, ia] > 0.8) & (z[:, ib] > 0.3))
        if self.p.get("ring"):
            logit += self.p["ring"]["effect"] * entity_ring
        return logit

    def _tune_intercept(self, world):
        r = np.random.default_rng(self.seed + 99)
        n = 20000
        day = r.integers(0, TRAIN_END, n)
        seg = r.choice(self.segments, n)
        z = r.standard_normal((n, len(self.names)))
        ring = r.random(n) < (self.p["ring"]["share"] if self.p.get("ring") else 0)
        base = self._latent_logit(world, z, day, seg, ring)
        lo, hi = -15.0, 10.0
        for _ in range(50):
            mid = (lo + hi) / 2
            if sigmoid(base + mid).mean() > world["base_rate"]:
                hi = mid
            else:
                lo = mid
        world["intercept"] = (lo + hi) / 2

    def _sample(self, world, n, lo, hi, rng, prod):
        day = np.sort(rng.integers(lo, hi, n))
        seg = rng.choice(self.segments, n)
        z = rng.standard_normal((n, len(self.names)))
        entity = rng.integers(0, self.p["entity"][1], n)
        ring = np.zeros(n, bool)
        cluster = rng.integers(0, 300, n).astype(object)
        if world["ring_ids"]:
            ring = rng.random(n) < self.p["ring"]["share"]
            entity[ring] = rng.choice(world["ring_ids"], ring.sum())
            cluster[ring] = "RING"
        logit = world["intercept"] + self._latent_logit(world, z, day, seg, ring)
        xz = z.copy()
        new = world.get("new_segment")
        if new:
            j = self.names.index(new["feature"])
            mask = rng.random(n) < new["share"]
            seg = seg.astype(object)
            seg[mask] = new["name"]
            coef = world["coef"][new["feature"]]
            logit[mask] -= coef * (1 - new["coef_scale"]) * z[mask, j]
            xz[mask, j] += new["shift"]
        y = (rng.random(n) < sigmoid(logit)).astype(int)
        for name, (share, delta, seg_only) in world["decouple"].items():
            j = self.names.index(name)
            mask = (seg == seg_only) if seg_only else (rng.random(n) < share)
            xz[mask, j] += delta
        X = {}
        for j, (name, dist, a, b, *_rest) in enumerate(self.p["features"]):
            X[name] = transform(dist, a, b, xz[:, j])
        X["segment_code"] = np.array([self.segments.index(s) if s in self.segments else len(self.segments) for s in seg], dtype=float)
        leak, fut = self.p["leak"][0], self.p["future"][0]
        X[leak] = y + rng.normal(0, 0.15, n)
        X[fut] = (1.2 * y + rng.normal(0, 0.6, n)) if not prod else rng.normal(0, 0.6, n)
        for k in range(1, 21):
            X[f"noise_{k:02d}"] = rng.normal(0, 1, n)
        return dict(X=X, y=y, y_obs=y.copy(), day=day, seg=seg, entity=entity, ring=ring, cluster=cluster)

    # ------------------------------------------------------------ pipeline
    def fix_choices(self):
        return [n for n in self.names + [self.p["leak"][0], self.p["future"][0]] + ["segment_code"]]

    def correct_fixes(self):
        t, fixes = self.targets, []
        for f in self.failures:
            if f in {"data_drift", "concept_drift", "stale_model"}:
                fixes.append(dict(fix="retrain_recent"))
            elif f == "label_leakage":
                fixes.append(dict(fix="drop_feature", feature=self.p["leak"][0]))
            elif f == "feature_leakage":
                fixes.append(dict(fix="drop_feature", feature=self.p["future"][0]))
            elif f == "wrong_labels":
                fixes.append(dict(fix="clean_labels"))
            elif f == "class_imbalance":
                fixes.append(dict(fix="rebalance"))
            elif f == "biased_sample":
                fixes.append(dict(fix="resample_representative"))
            elif f == "missing_feature":
                fixes.append(dict(fix="restore_feature", feature=t["missing"]))
            elif f == "schema_change":
                fixes.append(dict(fix="fix_units", feature=t["units"]))
            elif f == "pipeline_bug":
                fixes.append(dict(fix="fix_pipeline", feature=t["swap"][0], alternatives=[t["swap"][1]]))
            elif f == "training_serving_skew":
                fixes.append(dict(fix="fix_pipeline", feature=t["skew"]))
            elif f == "overfitting":
                fixes.append(dict(fix="regularize"))
            elif f == "underfitting":
                fixes.append(dict(fix="increase_capacity"))
            elif f == "bad_threshold":
                fixes.append(dict(fix="tune_threshold"))
            elif f == "poor_calibration":
                fixes.append(dict(fix="recalibrate"))
            elif f == "delayed_labels":
                fixes.append(dict(fix="label_lag_eval"))
            elif f == "version_mismatch":
                fixes.append(dict(fix="redeploy_version"))
        unique = []
        for fx in fixes:
            if not any(u["fix"] == fx["fix"] and u.get("feature") == fx.get("feature") for u in unique):
                unique.append(fx)
        return unique

    def apply_fixes(self, fixes):
        pipe = copy.deepcopy(self.pipe)
        pipe.update(recent=False, clean=False, tune=False, recalibrate=False, matured_only=False)
        for fx in fixes or []:
            kind, feature = fx.get("fix"), fx.get("feature")
            if kind == "retrain_recent":
                pipe["recent"] = True
            elif kind == "drop_feature" and feature in pipe["features"]:
                pipe["features"].remove(feature)
                pipe["all_features"] = [f for f in pipe["all_features"] if f != feature]
            elif kind == "clean_labels":
                pipe["clean"] = True
            elif kind == "rebalance":
                # Reweight classes, then re-select the operating point on validation cost.
                pipe["class_weight"] = "balanced"
                pipe["tune"] = True
            elif kind == "resample_representative":
                pipe["train_segments"] = None
            elif kind == "restore_feature":
                pipe["serve"]["missing"].pop(feature, None)
            elif kind == "fix_units":
                pipe["serve"]["scale"].pop(feature, None)
            elif kind == "fix_pipeline":
                if pipe["serve"]["swap"] and feature in pipe["serve"]["swap"][:2]:
                    pipe["serve"]["swap"] = None
                pipe["serve"]["skew"].pop(feature, None)
            elif kind == "regularize":
                pipe["model"] = "gbm_reg"
            elif kind == "increase_capacity":
                pipe["model"] = "gbm"
                pipe["features"] = [f for f in pipe["all_features"]]
            elif kind == "tune_threshold":
                pipe["tune"] = True
            elif kind == "recalibrate":
                pipe["recalibrate"] = True
            elif kind == "label_lag_eval":
                pipe["matured_only"] = True
            elif kind == "redeploy_version":
                pipe["served_version"] = pipe["approved_version"]
        return pipe

    def _model(self, kind, cw):
        if kind == "gbm":
            return HistGradientBoostingClassifier(max_iter=160, learning_rate=0.08, max_leaf_nodes=15, min_samples_leaf=20, class_weight=cw, random_state=self.seed)
        if kind == "gbm_reg":
            return HistGradientBoostingClassifier(max_iter=140, learning_rate=0.06, max_depth=3, min_samples_leaf=30, l2_regularization=2.0, class_weight=cw, random_state=self.seed)
        if kind == "tree_deep":
            return DecisionTreeClassifier(random_state=self.seed, class_weight=cw)
        return make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, class_weight=cw))

    @staticmethod
    def matrix(X, features, idx=None):
        cols = [X[f] if idx is None else X[f][idx] for f in features]
        return np.column_stack(cols) if cols else np.zeros((0 if idx is None else len(idx), 0))

    def _training_rows(self, pipe):
        tr = self.train
        mask = (tr["day"] >= pipe["train_days"][0]) & (tr["day"] < pipe["train_days"][1])
        if pipe.get("recent"):
            mask = tr["day"] >= 90
        if pipe["train_segments"]:
            mask &= np.isin(tr["seg"], pipe["train_segments"])
        idx = np.where(mask)[0]
        if pipe["subsample"] and len(idx) > pipe["subsample"]:
            idx = idx[np.linspace(0, len(idx) - 1, pipe["subsample"]).astype(int)]
        return idx

    def fit(self, pipe, version="approved"):
        key = (version, json.dumps(pipe, sort_keys=True, default=str))
        if key in self._cache:
            return self._cache[key]
        features = list(pipe["features"])
        train_days = pipe["train_days"]
        if version == "v2":
            features = [f for f in features if f not in self.names[:2]]
            train_days = (0, 120)
            pipe = dict(pipe, train_days=train_days, recent=False)
        tr = self.train
        idx = self._training_rows(pipe)
        y = tr["y"] if pipe.get("clean") else tr["y_obs"]
        X = self.matrix(tr["X"], features, idx)
        yy = y[idx]
        days = tr["day"][idx]
        weights = np.ones(len(idx))
        if pipe.get("recent"):
            pr = self.prod
            recent = np.where(pr["day"] < RETRAIN_END)[0]
            X = np.vstack([X, self.matrix(self.served(pipe, recent_only=True), features)])
            yy = np.concatenate([yy, pr["y"][recent]])
            days = np.concatenate([days, pr["day"][recent]])
            weights = np.concatenate([weights, np.full(len(recent), 4.0)])
        cut = np.quantile(days, 0.83)
        fit_mask, val_mask = days < cut, days >= cut
        if yy[fit_mask].min() == yy[fit_mask].max():
            fit_mask = np.ones(len(yy), bool)
        model = self._model(pipe["model"], pipe["class_weight"])
        try:
            if pipe["model"] == "logistic":
                model.fit(X[fit_mask], yy[fit_mask], logisticregression__sample_weight=weights[fit_mask])
            else:
                model.fit(X[fit_mask], yy[fit_mask], sample_weight=weights[fit_mask])
        except ValueError:
            model.fit(X[fit_mask], yy[fit_mask])
        raw_val = model.predict_proba(X[val_mask])[:, 1]
        raw_fit = model.predict_proba(X[fit_mask])[:, 1]
        prior = float(np.average(yy[fit_mask], weights=weights[fit_mask]))
        result = dict(model=model, prior=prior, features=features, val_X=X[val_mask], val_y=yy[val_mask], val_raw=raw_val, fit_y=yy[fit_mask], fit_raw=raw_fit, train_days=train_days, rows=int(fit_mask.sum()))
        self._cache[key] = result
        return result

    def _calibrate(self, pipe, raw):
        c = pipe.get("calibration")
        if not c:
            return raw
        eps = 1e-6
        logit = np.log(np.clip(raw, eps, 1 - eps) / np.clip(1 - raw, eps, 1))
        return sigmoid(c["a"] * logit + c["b"])

    def scores(self, pipe, fitted, X):
        raw = fitted["model"].predict_proba(X)[:, 1] if len(X) else np.zeros(0)
        if pipe["class_weight"] == "balanced":
            # Balanced weights train as if classes were 50/50; restore the true prior odds.
            pi = min(max(fitted["prior"], 1e-6), 1 - 1e-6)
            odds = raw / np.clip(1 - raw, 1e-9, None) * pi / (1 - pi)
            raw = odds / (1 + odds)
        p = self._calibrate(pipe, raw)
        if pipe.get("recalibrate"):
            iso = IsotonicRegression(out_of_bounds="clip").fit(self._calibrate(pipe, fitted["val_raw"]), fitted["val_y"])
            p = iso.predict(p)
        return p

    def bayes_threshold(self):
        fn = self.mean_value * self.p.get("loss_fraction", 1.0) if self.p.get("value_feature") else self.p.get("fn_cost", 100)
        return float(self.p["fp_cost"] / (self.p["fp_cost"] + max(fn, 1e-9)))

    def threshold(self, pipe, fitted):
        if not pipe.get("tune"):
            return pipe["threshold"] if pipe["threshold"] is not None else self.bayes_threshold()
        val_p = self.scores(pipe, fitted, fitted["val_X"])
        value = None
        best = min(
            np.concatenate([np.linspace(0.005, 0.05, 10), np.linspace(0.06, 0.98, 47)]),
            key=lambda t: self.cost(fitted["val_y"], val_p >= t, value),
        )
        return float(best)

    def cost(self, y, pred, value):
        fn = (~pred) & (y == 1)
        fp = pred & (y == 0)
        loss = self.p.get("loss_fraction", 1.0)
        if self.p.get("value_feature") and value is not None:
            fn_cost = float(value[fn].sum()) * loss
        elif self.p.get("value_feature"):
            fn_cost = float(fn.sum()) * self.mean_value * loss
        else:
            fn_cost = float(fn.sum()) * self.p.get("fn_cost", 100)
        return (fn_cost + fp.sum() * self.p["fp_cost"]) / max(1, len(y)) * 1000

    def served(self, pipe, recent_only=False, idx=None):
        pr = self.prod
        X = {k: v.copy() for k, v in pr["X"].items()}
        day = pr["day"]
        s = pipe["serve"]
        for f, cfg in s["missing"].items():
            X[f][day >= cfg["from_day"]] = cfg["fill"]
        for f, cfg in s["scale"].items():
            X[f][day >= cfg["from_day"]] *= cfg["factor"]
        if s["swap"]:
            a, b, d0 = s["swap"]
            m = day >= d0
            X[a][m], X[b][m] = pr["X"][b][m], pr["X"][a][m]
        r = np.random.default_rng(self.seed + 7)
        for f, cfg in s["skew"].items():
            X[f] = X[f] * cfg["factor"] + r.normal(0, cfg["noise"] * max(1e-9, float(np.std(pr["X"][f]))), len(day))
        for f in s["unavailable"]:
            X[f] = np.zeros(len(day))
        if recent_only:
            mask = day < RETRAIN_END
            return {k: v[mask] for k, v in X.items()}
        if idx is not None:
            return {k: v[idx] for k, v in X.items()}
        return X

    def metrics(self, y, p, threshold, value):
        pred = p >= threshold
        tp = int((pred & (y == 1)).sum())
        fp = int((pred & (y == 0)).sum())
        fn = int((~pred & (y == 1)).sum())
        tn = int((~pred & (y == 0)).sum())
        auc = float(roc_auc_score(y, p)) if 0 < y.sum() < len(y) else None
        bins = np.clip((p * 10).astype(int), 0, 9)
        ece = sum(abs(p[bins == b].mean() - y[bins == b].mean()) * (bins == b).mean() for b in range(10) if (bins == b).any())
        return dict(
            auc=None if auc is None else round(auc, 4),
            precision=round(tp / max(1, tp + fp), 4),
            recall=round(tp / max(1, tp + fn), 4),
            f1=round(2 * tp / max(1, 2 * tp + fp + fn), 4),
            accuracy=round((tp + tn) / max(1, len(y)), 4),
            alert_rate=round(float(pred.mean()), 4),
            positive_rate=round(float(y.mean()), 4),
            cost_per_1k=round(self.cost(y, pred, value), 2),
            ece=round(float(ece), 4),
            confusion=dict(tp=tp, fp=fp, fn=fn, tn=tn),
            rows=int(len(y)),
        )

    def evaluate(self, fixes=()):
        pipe = self.apply_fixes(fixes)
        approved = self.fit(pipe)
        served_model = approved if pipe["served_version"] == pipe["approved_version"] else self.fit(pipe, "v2")
        pr = self.prod
        idx = np.where((pr["day"] >= EVAL[0]) & (pr["day"] < EVAL[1]))[0]
        Xs = self.served(pipe, idx=idx)
        p = self.scores(pipe, served_model, self.matrix(Xs, served_model["features"]))
        thr = self.threshold(pipe, approved)
        value = pr["X"][self.p["value_feature"]][idx] if self.p.get("value_feature") else None
        y = pr["y"][idx]
        true = self.metrics(y, p, thr, value)
        y_mon = y.copy()
        matured = np.ones(len(idx), bool)
        if pipe["label_delay"]:
            unmatured = pr["day"][idx] >= PROD_END - pipe["label_delay"]
            y_mon[unmatured] = 0
            matured = ~unmatured
        if pipe.get("matured_only"):
            monitored = self.metrics(y_mon[matured], p[matured], thr, None if value is None else value[matured])
        else:
            monitored = self.metrics(y_mon, p, thr, value)
        val_p = self.scores(pipe, approved, approved["val_X"])
        offline = self.metrics(approved["val_y"], val_p, thr, None)
        return dict(true=true, monitored=monitored, offline=offline, threshold=round(thr, 3), primary="cost_per_1k", pipe=pipe, p=p, idx=idx, y_mon=y_mon, fitted=approved, served_model=served_model)
