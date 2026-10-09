"""Forecasting labs: daily demand/volume series with hidden production failures.

Series follow level × weekly pattern × yearly cycle × trend × driver effect × calendar
events with noise. The model is a 7-day-ahead Ridge regression on log demand with lag,
rolling, driver, calendar and seasonality features, so each failure has a mechanical cause.
"""

import copy
import json

import numpy as np
from sklearn.linear_model import Ridge

from .catalog import WEEKLY

TRAIN_END, RETRAIN_END, PROD_END, ONSET = 420, 440, 480, 440
EVAL = (440, 480)
HOLIDAYS = [40, 41, 120, 205, 206, 300, 360, 361, 400]
PROD_EVENTS = [446, 447, 461, 472]
HORIZON = 7


class ForecastLab:
    family = "forecasting"

    def __init__(self, profile, failures, seed, params=None):
        self.p, self.failures, self.seed = profile, list(failures), seed
        self.params = params or {}
        self.driver = profile["driver"][0]
        rng = np.random.default_rng(seed)
        self.series = list(profile["series"])
        lo, hi = profile["level"]
        self.level = {s: float(rng.uniform(lo, hi)) for s in self.series}
        base = np.array(WEEKLY[profile["weekly"]])
        # The last two series have a shifted weekly shape (matters for biased samples).
        self.weekly = {s: (base if i < 2 else np.roll(base, 2)) for i, s in enumerate(self.series)}
        self.world = dict(beta={s: profile["driver"][2] for s in self.series}, level_shift={}, ramp=False, events=list(HOLIDAYS + PROD_EVENTS), driver_scale={s: 1.0 for s in self.series})
        self.pipe = dict(
            model="ridge",
            alpha=1.0,
            seasonality=True,
            event_feature=True,
            cold_fallback=False,
            features=["lag7", "lag14", "roll28", self.driver, "event", "yearly"],
            all_features=["lag7", "lag14", "roll28", self.driver, "event", "yearly"],
            train_days=(35, TRAIN_END),
            train_series=None,
            serve=dict(missing={}, units={}, dow_shift=0, roll_sum=False, driver_flag=False),
            label_delay=0,
            approved_version="v3",
            served_version="v3",
            extra_features=[],
            label_noise=None,
        )
        self.new_series = None
        prod_world = copy.deepcopy(self.world)
        for f in self.failures:
            self._inject(f, prod_world)
        self.prod_world = prod_world
        self.data = self._simulate(np.random.default_rng(seed + 1))
        self._cache = {}

    # ------------------------------------------------------------ world
    def _inject(self, failure, prod):
        pipe, s2 = self.pipe, self.series[2]
        if failure == "data_drift":
            prod["driver_scale"][s2] = 3.0
        elif failure == "concept_drift":
            prod["beta"] = {s: self.p["driver"][2] * -0.2 for s in self.series}
        elif failure == "feature_leakage":
            pipe["features"].append("same_day_drawdown")
            pipe["all_features"].append("same_day_drawdown")
            pipe["extra_features"].append("same_day_drawdown")
        elif failure == "wrong_labels":
            pipe["label_noise"] = dict(series=self.series[0], share=0.25, factor=0.25)
        elif failure == "biased_sample":
            pipe["train_series"] = self.series[:2]
        elif failure == "missing_feature":
            pipe["serve"]["missing"][self.driver] = ONSET
        elif failure == "schema_change":
            pipe["serve"]["units"][self.series[1]] = 12.0
        elif failure == "pipeline_bug":
            pipe["serve"]["dow_shift"] = 1
        elif failure == "training_serving_skew":
            pipe["serve"]["driver_flag"] = True
        elif failure == "overfitting":
            pipe["model"] = "ridge_overfit"
            pipe["alpha"] = 1e-6
            pipe["train_days"] = (TRAIN_END - 56, TRAIN_END)
        elif failure == "underfitting":
            pipe["model"] = "mean"
        elif failure == "seasonality_failure":
            pipe["seasonality"] = False
        elif failure == "holiday_event":
            pipe["event_feature"] = False
            pipe["features"].remove("event")
        elif failure == "cold_start":
            self.new_series = "New site"
        elif failure == "delayed_labels":
            pipe["label_delay"] = 14
        elif failure == "version_mismatch":
            pipe["served_version"] = "v2"
        elif failure == "stale_model":
            self.world["ramp"] = True
            prod["ramp"] = True
            pipe["train_days"] = (35, 180)

    def _simulate(self, rng):
        series = self.series + ([self.new_series] if self.new_series else [])
        days = np.arange(PROD_END)
        y, driver, event = {}, {}, np.isin(days, self.world["events"]).astype(float)
        for i, s in enumerate(series):
            new = s == self.new_series
            level = np.mean(list(self.level.values())) * 0.8 if new else self.level[s]
            weekly = self.weekly[self.series[i % len(self.series)]] if not new else np.array(WEEKLY[self.p["weekly"]])
            dvals = (rng.random(PROD_END) < self.p["driver"][1]) * rng.uniform(0.1, 0.4, PROD_END)
            prod_mask = days >= TRAIN_END
            if s in self.prod_world["driver_scale"]:
                dvals[prod_mask] = np.minimum(1.0, dvals[prod_mask] * self.prod_world["driver_scale"][s] + (dvals[prod_mask] > 0) * 0.25 * (self.prod_world["driver_scale"][s] > 1))
            driver[s] = dvals
            beta = np.where(prod_mask, self.prod_world["beta"].get(s, self.p["driver"][2]), self.world["beta"].get(s, self.p["driver"][2]))
            sat = (1 - np.exp(-4 * dvals)) / (1 - np.exp(-1.6))
            dow = days % 7
            w = weekly[dow]
            if self.world["ramp"]:
                shifted = np.roll(weekly, 3)
                mix = days / PROD_END
                w = (1 - mix) * weekly[dow] + mix * shifted[dow]
            mean = (
                level
                * w
                * (1 + self.p["yearly"] * np.sin(2 * np.pi * days / 365))
                * (1 + self.p["trend"] * days / 365)
                * np.maximum(0.05, 1 + beta * sat)
                * (1 + 1.3 * event)
            )
            if self.p.get("count"):
                values = rng.poisson(np.maximum(mean, 0.1)).astype(float)
            else:
                values = mean * np.exp(rng.normal(0, self.p["noise"], PROD_END))
            if new:
                values[days < ONSET] = np.nan
            y[s] = values
        return dict(series=series, y=y, driver=driver, event=event)

    # ------------------------------------------------------------ features
    def recorded(self, pipe):
        """Actuals as recorded in the data platform (may be corrupted by failures)."""
        rec = {s: v.copy() for s, v in self.data["y"].items()}
        for s, factor in pipe["serve"]["units"].items():
            rec[s][np.arange(PROD_END) >= ONSET - HORIZON] /= factor
        noise = pipe.get("label_noise")
        if noise:
            r = np.random.default_rng(self.seed + 5)
            days = np.arange(PROD_END)
            mask = (r.random(PROD_END) < noise["share"]) & (days < TRAIN_END)
            rec[noise["series"]][mask] *= noise["factor"]
        return rec

    def _rows(self, pipe, series, days, serving):
        rec = self.recorded(pipe)
        feats, meta = [], []
        s_index = {s: i for i, s in enumerate(self.series)}
        pooled = {d: np.nanmean([rec[s][d] for s in self.series]) for d in range(PROD_END)}
        for s in series:
            yv = rec[s]
            for d in days:
                def lag(k):
                    v = yv[d - k] if d - k >= 0 else np.nan
                    if np.isnan(v):
                        return pooled.get(d - k, 0.0) if (pipe.get("cold_fallback") and d - k >= 0) else 0.0
                    return v

                window = [yv[d - k] for k in range(7, 35) if d - k >= 0]
                window = [v for v in window if not np.isnan(v)]
                if not window and pipe.get("cold_fallback"):
                    window = [pooled[d - k] for k in range(7, 35) if d - k >= 0]
                roll = float(np.mean(window)) if window else 0.0
                if serving and pipe["serve"]["roll_sum"]:
                    recent = [v for v in (yv[d - k] for k in range(7, 14) if d - k >= 0) if not np.isnan(v)]
                    roll = float(np.sum(recent)) if recent else 0.0
                drv = self.data["driver"][s][d]
                if serving and pipe["serve"].get("driver_flag") and drv > 0:
                    # Serving reads the campaign flag (1.0) instead of its planned intensity.
                    drv = 1.0
                if serving and self.driver in pipe["serve"]["missing"] and d >= pipe["serve"]["missing"][self.driver]:
                    drv = 0.0
                dow = (d + (pipe["serve"]["dow_shift"] if serving and d >= ONSET else 0)) % 7
                row = dict(lag7=np.log1p(lag(7)), lag14=np.log1p(lag(14)), roll28=np.log1p(roll))
                row[self.driver] = drv
                row["event"] = self.data["event"][d]
                row["yearly"] = np.sin(2 * np.pi * d / 365)
                truth = self.data["y"][s][d]
                if serving:
                    prev = yv[d - 1] if d >= 1 and not np.isnan(yv[d - 1]) else 0.0
                    row["same_day_drawdown"] = np.log1p(prev) + 0.3
                else:
                    row["same_day_drawdown"] = np.log1p(truth if not np.isnan(truth) else 0.0) + 0.3
                for k in range(8, 61) if pipe["model"] == "ridge_overfit" else []:
                    row[f"lag{k}"] = np.log1p(lag(k))
                feats.append(row)
                meta.append((s, d, dow, s_index.get(s, -1)))
        return feats, meta

    def _design(self, pipe, feats, meta, features):
        cols = []
        extra = [f"lag{k}" for k in range(8, 61)] if pipe["model"] == "ridge_overfit" else []
        for row in feats:
            cols.append([row[f] for f in features + extra])
        X = np.array(cols, dtype=float) if cols else np.zeros((0, len(features) + len(extra)))
        n_series = len(self.series)
        onehot = np.zeros((len(meta), n_series))
        for i, (_, _, _, si) in enumerate(meta):
            if si >= 0:
                onehot[i, si] = 1
            elif pipe.get("cold_fallback"):
                onehot[i, :] = 1 / n_series  # pooled: average of known series effects
        parts = [X, onehot]
        if pipe["seasonality"] and pipe["model"] != "mean":
            dow = np.zeros((len(meta), 7))
            inter = np.zeros((len(meta), 7 * n_series))
            for i, (_, _, d7, si) in enumerate(meta):
                dow[i, d7] = 1
                if si >= 0:
                    inter[i, si * 7 + d7] = 1
                elif pipe.get("cold_fallback"):
                    for k in range(n_series):
                        inter[i, k * 7 + d7] = 1 / n_series
            parts += [dow, inter]
        if pipe["model"] == "mean":
            return onehot
        return np.hstack(parts)

    # ------------------------------------------------------------ pipeline
    def fix_choices(self):
        return ["lag7", "lag14", "roll28", self.driver, "event", "dow", "actuals", "same_day_drawdown"]

    def correct_fixes(self):
        fixes = []
        mapping = dict(
            data_drift=dict(fix="retrain_recent"),
            concept_drift=dict(fix="retrain_recent"),
            stale_model=dict(fix="retrain_recent"),
            feature_leakage=dict(fix="drop_feature", feature="same_day_drawdown"),
            wrong_labels=dict(fix="clean_labels"),
            biased_sample=dict(fix="resample_representative"),
            missing_feature=dict(fix="restore_feature", feature=self.driver),
            schema_change=dict(fix="fix_units", feature="actuals"),
            pipeline_bug=dict(fix="fix_pipeline", feature="dow"),
            training_serving_skew=dict(fix="fix_pipeline", feature=self.driver),
            overfitting=dict(fix="regularize"),
            underfitting=dict(fix="increase_capacity"),
            seasonality_failure=dict(fix="add_seasonality"),
            holiday_event=dict(fix="add_event_feature"),
            cold_start=dict(fix="pooled_fallback"),
            delayed_labels=dict(fix="label_lag_eval"),
            version_mismatch=dict(fix="redeploy_version"),
        )
        for f in self.failures:
            fx = mapping.get(f)
            if fx and fx not in fixes:
                fixes.append(fx)
        return fixes

    def apply_fixes(self, fixes):
        pipe = copy.deepcopy(self.pipe)
        pipe.update(recent=False, matured_only=False)
        for fx in fixes or []:
            kind, feature = fx.get("fix"), fx.get("feature")
            if kind == "retrain_recent":
                pipe["recent"] = True
            elif kind == "drop_feature" and feature in pipe["features"]:
                pipe["features"].remove(feature)
                pipe["all_features"] = [f for f in pipe["all_features"] if f != feature]
            elif kind == "clean_labels":
                pipe["label_noise"] = None
            elif kind == "resample_representative":
                pipe["train_series"] = None
            elif kind == "restore_feature":
                pipe["serve"]["missing"].pop(feature, None)
            elif kind == "fix_units" and feature in {"actuals", "lag7", "lag14", "roll28"}:
                pipe["serve"]["units"] = {}
            elif kind == "fix_pipeline":
                if feature == "dow":
                    pipe["serve"]["dow_shift"] = 0
                if feature == "roll28":
                    pipe["serve"]["roll_sum"] = False
                if feature == self.driver:
                    pipe["serve"]["driver_flag"] = False
            elif kind == "regularize":
                pipe.update(model="ridge", alpha=3.0, train_days=(35, TRAIN_END))
            elif kind == "increase_capacity":
                pipe["model"] = "ridge"
                pipe["features"] = list(pipe["all_features"])
            elif kind == "add_seasonality":
                pipe["seasonality"] = True
            elif kind == "add_event_feature":
                pipe["event_feature"] = True
                if "event" not in pipe["features"]:
                    pipe["features"].append("event")
            elif kind == "pooled_fallback":
                pipe["cold_fallback"] = True
            elif kind == "label_lag_eval":
                pipe["matured_only"] = True
            elif kind == "redeploy_version":
                pipe["served_version"] = pipe["approved_version"]
        return pipe

    def fit(self, pipe, version="approved"):
        key = (version, json.dumps(pipe, sort_keys=True, default=str))
        if key in self._cache:
            return self._cache[key]
        features = list(pipe["features"])
        lo, hi = pipe["train_days"]
        if version == "v2":
            features = [f for f in features if f not in {self.driver, "event"}]
            pipe = dict(pipe, seasonality=False)
        series = pipe["train_series"] or self.series
        days = list(range(lo, hi))
        if pipe.get("recent"):
            days = list(range(35, RETRAIN_END))
        feats, meta = self._rows(pipe, series, days, serving=False)
        rec = self.recorded(pipe)
        target = np.array([np.log1p(max(0.0, rec[s][d])) for s, d, _, _ in meta])
        X = self._design(pipe, feats, meta, features)
        if pipe.get("recent"):
            # Exponential recency weighting keeps seasonal structure but follows the new regime.
            weights = np.array([np.exp((d - RETRAIN_END) / 45) for _, d, _, _ in meta])
            weights = weights / weights.mean()
        else:
            weights = np.ones(len(meta))
        cut = np.quantile([d for _, d, _, _ in meta], 0.85)
        fit_mask = np.array([d < cut for _, d, _, _ in meta])
        model = Ridge(alpha=pipe["alpha"]).fit(X[fit_mask], target[fit_mask], sample_weight=weights[fit_mask])
        val_pred = np.expm1(model.predict(X[~fit_mask]))
        fit_pred = np.expm1(model.predict(X[fit_mask]))
        val_true = np.expm1(target[~fit_mask])
        fit_true = np.expm1(target[fit_mask])
        result = dict(model=model, features=features, pipe=pipe, val=(val_true, val_pred), fit=(fit_true, fit_pred), rows=int(fit_mask.sum()), coef=model.coef_.tolist())
        self._cache[key] = result
        return result

    def predict(self, pipe, fitted, series, days):
        feats, meta = self._rows(pipe, series, days, serving=True)
        use_pipe = fitted["pipe"]
        X = self._design(dict(pipe, seasonality=use_pipe["seasonality"], model=use_pipe["model"]), feats, meta, fitted["features"])
        pred = np.maximum(0.0, np.expm1(fitted["model"].predict(X)))
        if not pipe.get("cold_fallback"):
            # No model key exists for an unseen series, so the service returns its default of 0.
            pred[np.array([si < 0 for *_rest, si in meta], dtype=bool)] = 0.0
        return pred, meta, feats

    @staticmethod
    def metrics(actual, pred):
        err = np.abs(actual - pred)
        denom = max(1e-9, float(np.sum(np.abs(actual))))
        return dict(
            wape=round(float(err.sum() / denom), 4),
            bias=round(float((pred - actual).sum() / denom), 4),
            mae=round(float(err.mean()), 3),
            under_cost=round(float(np.maximum(0, actual - pred).sum() * 2 / denom * 1000), 2),
            rows=int(len(actual)),
        )

    def evaluate(self, fixes=()):
        pipe = self.apply_fixes(fixes)
        approved = self.fit(pipe)
        served = approved if pipe["served_version"] == pipe["approved_version"] else self.fit(pipe, "v2")
        days = list(range(*EVAL))
        pred, meta, _ = self.predict(pipe, served, self.data["series"], days)
        actual = np.array([self.data["y"][s][d] for s, d, _, _ in meta])
        rec = self.recorded(pipe)
        recorded = np.array([rec[s][d] for s, d, _, _ in meta])
        mon_actual = recorded.copy()
        matured = np.ones(len(meta), bool)
        if pipe["label_delay"]:
            young = np.array([d >= PROD_END - pipe["label_delay"] for _, d, _, _ in meta])
            mon_actual[young] *= 0.55
            matured = ~young
        true = self.metrics(actual, pred)
        monitored = self.metrics(mon_actual[matured], pred[matured]) if pipe.get("matured_only") else self.metrics(mon_actual, pred)
        offline = self.metrics(*approved["val"])
        return dict(true=true, monitored=monitored, offline=offline, primary="wape", pipe=pipe, pred=pred, meta=meta, actual=actual, recorded=mon_actual, fitted=approved, served_model=served)
