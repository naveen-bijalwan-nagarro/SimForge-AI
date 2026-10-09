"""ML Failure Lab: every injected failure hurts, its fix recovers, scoring and roles work."""

import pytest
from fastapi.testclient import TestClient

from backend import settings
from backend.main import app
from backend.mllab import catalog
from backend.mllab import lab as ml

HEADERS = {"X-SimForge-Request": "1"}


@pytest.mark.parametrize("failure", list(catalog.FAILURE_DRILLS), ids=str)
def test_each_failure_degrades_and_its_fix_recovers(failure):
    cfg = ml.create_config(f"drill:{failure}")
    lab = ml.build(cfg)
    before, fixed = lab.evaluate(), lab.evaluate(lab.correct_fixes())
    key = before["primary"]
    business_gain = before["true"][key] - fixed["true"][key]

    def monitoring_error(r):
        return abs(r["monitored"][key] - r["true"][key]) / max(1e-9, abs(r["true"][key]))

    monitoring_gain = monitoring_error(before) - monitoring_error(fixed)
    assert business_gain > 0.03 * abs(before["true"][key]) or monitoring_gain > 0.1


def test_perfect_diagnosis_scores_full_marks_and_wrong_fixes_are_penalised():
    cfg = ml.create_config("advanced:accuracy_vs_loss")
    lab = ml.build(cfg)
    perfect = ml.score(lab, cfg, dict(failures=lab.failures, fixes=lab.correct_fixes(), probes_used=["timeline", "threshold"]))
    assert perfect["score"] == 100
    wrong = ml.score(lab, cfg, dict(failures=["overfitting"], fixes=[dict(fix="regularize")], probes_used=[]))
    assert wrong["score"] < 40 and wrong["unnecessary_fixes"]
    assert perfect["ground_truth"]["failures"][0]["key"] in lab.failures


def test_probes_return_evidence_for_the_injected_failure():
    cfg = ml.create_config("drill:pipeline_bug")
    lab = ml.build(cfg)
    trace = ml.run_probe(lab, "pipeline_trace")["data"]["rows"]
    assert any(not r["match"] for r in trace)
    for name in ml.probes_for(lab):
        assert ml.run_probe(lab, name, cfg)["data"] is not None
    fc = ml.create_config("drill:seasonality_failure")
    flab = ml.build(fc)
    for name in ml.probes_for(flab):
        assert ml.run_probe(flab, name, fc)["data"] is not None


def test_random_challenges_respect_exclusions_and_family():
    for seed in range(12):
        cfg = ml.create_config(profile_key="sales_forecast", count=5, seed=seed)
        assert all("forecasting" in catalog.FAILURES[f]["families"] for f in cfg["failures"])
        assert not any(group <= set(cfg["failures"]) for group in catalog.EXCLUSIVE)
    with pytest.raises(ValueError):
        ml.create_config(profile_key="credit_card_fraud", failures=["cold_start"])


def test_auto_investigator_finds_most_single_failures():
    found = 0
    drills = ["label_leakage", "schema_change", "missing_feature", "version_mismatch", "seasonality_failure", "cold_start"]
    for failure in drills:
        cfg = ml.create_config(f"drill:{failure}")
        found += failure in ml.auto_investigate(ml.build(cfg), cfg)["failures"]
    assert found >= 5


def test_lab_api_roles_probes_submission_and_hidden_truth(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA", tmp_path)
    with TestClient(app, headers=HEADERS) as c:
        c.post("/api/auth/login", json={"username": "learner", "password": "learner123"})
        assert c.post("/api/mllab/labs", json={"profile": "sales_forecast", "failures": ["cold_start"]}).status_code == 403
        lab = c.post("/api/mllab/labs", json={"scenario_key": "drill:missing_feature"}).json()
        assert "failures" not in lab["config"]
        assert c.get(f"/api/mllab/labs/{lab['id']}/ground_truth.json").status_code == 403
        c.post(f"/api/mllab/labs/{lab['id']}/probes/eda?record=false")
        c.post(f"/api/mllab/labs/{lab['id']}/probes/pipeline_trace")
        assert c.get(f"/api/mllab/labs/{lab['id']}").json()["probes_used"] == ["pipeline_trace"]
        hidden = c.post(f"/api/mllab/labs/{lab['id']}/agent").json()
        assert "failures" not in hidden
        truth_feature = ml.build(ml.create_config("drill:missing_feature")).targets["missing"]
        result = c.post(f"/api/mllab/labs/{lab['id']}/submit", json={"failures": ["missing_feature"], "fixes": [{"fix": "restore_feature", "feature": truth_feature}]}).json()
        assert result["score"] >= 95
        assert c.post(f"/api/mllab/labs/{lab['id']}/submit", json={"failures": []}).status_code == 409
        assert c.get(f"/api/mllab/labs/{lab['id']}/ground_truth.json").status_code == 200
        assert c.post(f"/api/mllab/labs/{lab['id']}/agent").json()["failures"]
