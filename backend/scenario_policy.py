"""Shared authoring policy and local privacy boundary; never execute model output."""

from . import settings
from .factory import pii

POLICY_VERSION = "scenario-lab-2026-10-09"


def system_prompt():
    return (settings.ROOT / "config" / "scenario_authoring_system.txt").read_text(encoding="utf-8").strip()


def clean(value):
    if isinstance(value, str):
        return pii.sanitize(value)[0]
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value


def privacy_summary(value):
    import json
    return pii.sanitize(json.dumps(value, ensure_ascii=False))[1]


def review_checks(spec):
    from .factory.compiler import INJECTION
    import json
    text = json.dumps(spec, ensure_ascii=False)
    leak = pii.residual(text)
    # Text is never executable, but reject authoring instructions in learner material too.
    injection = bool(INJECTION.search(text))
    return [
        dict(name="Privacy screening completed", category="privacy", passed=not leak,
             detail="Common PII and secret patterns screened locally; administrator review is still required."),
        dict(name="No embedded authoring override", category="governance", passed=not injection,
             detail="Remove instructions to bypass review, reveal prompts or change authoring rules." if injection
             else "No known instruction-override pattern in the scenario."),
    ]


def security_event(stage, findings=None, status="passed", actor=None):
    """A value-free security receipt: never log matched text or source excerpts."""
    import time
    findings = findings or {}
    event = dict(stage=stage, status=status, timestamp=time.time(),
                 total=findings.get("total", 0), entities=findings.get("entities", {}),
                 engine=findings.get("engine", "Built-in recognizers"))
    if actor:
        event["actor"] = actor
    return event


def input_log(findings, documents):
    return [security_event("Brief screened before model access", findings)] + [
        dict(security_event("Reference screened before model access", d.get("redactions")),
             document_id=d["id"]) for d in documents
    ]


def draft_governance(findings, checks, previous=None):
    previous = previous or {}
    events = list(previous.get("events", [])) + [
        security_event("Scenario text screened", findings),
        security_event("Privacy and instruction-override checks",
                       status="passed" if all(c["passed"] for c in checks
                                              if c["category"] in {"privacy", "governance"}) else "blocked"),
        security_event("Administrator publication approval", status="pending"),
    ]
    return dict(previous, policy_version=POLICY_VERSION, output_privacy=findings, events=events)
