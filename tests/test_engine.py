import copy
import pytest
from backend.catalog import WORLDS, all_scenarios, legacy_generator
from backend.engine import simulate, agent_workflow
from backend.labs import dataset_quality, synthesize


@pytest.mark.parametrize("spec", WORLDS, ids=lambda s: s["key"])
def test_all_worlds_have_causal_disruptions_and_recover(spec):
    baseline = simulate(spec, 101, 80, 35, [])
    repair = next(a for a in spec["actions"] if a["effect"] == "repair")
    restored = simulate(spec, 101, 80, 35, [{"action_id": repair["id"], "tick": 6}])
    assert any(e["kind"] == "incident" for e in baseline["events"])
    assert any(
        e["kind"] == "degradation" and e["node"] != spec["incident"]["node"]
        for e in baseline["events"]
    )
    assert baseline["metrics"]["loss"] > restored["metrics"]["loss"]
    assert restored["metrics"]["service"] > baseline["metrics"]["service"]
    assert restored["metrics"]["spent"] == repair["cost"]
    assert len(baseline["entities"]) == 80


def test_replay_and_branch_determinism():
    s = WORLDS[0]
    decisions = [{"action_id": "patch_rewards", "tick": 7}]
    assert simulate(s, 8, 50, 30, decisions) == simulate(s, 8, 50, 30, decisions)
    first = simulate(s, 8, 50, 10, decisions)
    later = simulate(s, 8, 50, 30, decisions)
    assert first["history"] == later["history"][:11]
    assert simulate(s, 9, 50, 10, decisions)["entities"] != first["entities"]


def test_actions_have_delayed_effects_and_real_tradeoffs():
    s = WORLDS[0]
    decision = [{"action_id": "patch_rewards", "tick": 7}]
    early = simulate(s, 8, 50, 8, decision)
    late = simulate(s, 8, 50, 12, decision)
    assert late["nodes"][0]["health"] > early["nodes"][0]["health"]
    isolated = simulate(s, 8, 50, 9, [{"action_id": "freeze_auction", "tick": 7}])
    assert next(n for n in isolated["nodes"] if n["id"] == "auction")["health"] == 0


def test_agents_only_cite_visible_events_and_never_execute():
    spec = WORLDS[0]
    result = simulate(spec, 10, 50, 15, [])
    before = copy.deepcopy(result)
    for role in ("investigator", "operations", "finance"):
        agent = agent_workflow(spec, result, role)
        allowed = {e["id"] for e in result["events"] if e["role"] in {role, "all"}}
        assert set(agent["evidence_ids"]) <= allowed
        assert agent["workflow"][-1]["status"] == "waiting"
    assert result == before


@pytest.mark.parametrize(
    "spec", [s for s in all_scenarios() if s["kind"] == "training"], ids=lambda s: s["key"]
)
def test_legacy_training_generator_preserved(spec):
    bundle = legacy_generator().generate_bundle(spec, 123, 1)
    assert len([v for v in bundle.values() if isinstance(v, list)]) == 10
    assert dataset_quality(bundle)["score"] == 100


def test_sampler_is_seeded_and_reports_overlap():
    csv = "region,count\nA,10\nB,20\n"
    a = synthesize(csv, 10, 4, "bootstrap")
    assert a == synthesize(csv, 10, 4, "bootstrap")
    assert a["exact_overlap"] == 10
    with pytest.raises(ValueError):
        synthesize("a,b\n1,2,3", 10, 4, "bootstrap")


def test_nonfinite_csv_values_remain_text():
    result = synthesize("value\nNaN\nInfinity", 10, 4, "independent")
    assert all(isinstance(row["value"], str) for row in result["rows"])
