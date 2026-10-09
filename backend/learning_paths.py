"""Objective knowledge checks for historical cases and ML labs.

The quizzes measure short-form reasoning. Their before/after change is separate
from each exercise's existing, illustrative practice score.
"""

import hashlib
import time

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from . import store
from .mllab import catalog as ml_catalog

VERSION = "objective-learning-paths-v1"


class Answers(BaseModel):
    model_config = {"extra": "forbid"}
    choices: list[int] = Field(min_length=3, max_length=3)


def initial_state():
    return {"version": VERSION, "evidence_started": False}


def mark_evidence_started(row, current):
    """Close a new learner's optional starting check on first evidence access."""
    if row["owner"] != current["id"]:
        return row
    for _ in range(3):
        state = row["payload"].get("learning_check")
        if not state or state.get("evidence_started"):
            return row
        state["evidence_started"] = True
        if store.update(row["id"], row["payload"], row["version"]):
            store.audit(current["id"], "learning.evidence_start", row["id"])
            return store.get(row["id"])
        row = store.get(row["id"])
        if not row:
            raise HTTPException(404, "Exercise not found")
    raise HTTPException(409, "Exercise changed; refresh and try again")


def _module_label(value):
    labels = {"bi": "business intelligence", "crm": "CRM", "hr": "HR", "aml": "AML"}
    return labels.get(value, value.replace("_", " "))


def _case_questions(phase, spec):
    title = spec.get("title", "business case")
    domain = spec.get("domain", "business")
    mission = spec.get("objective") or "identify the root cause and support a response"
    modules = [_module_label(str(x)) for x in spec.get("modules", [])]
    source = modules[0] if modules else "source records"
    related = modules[1] if len(modules) > 1 else "related records"
    if phase == "before":
        return [
            (f"In a {title} case, how would you locate where an unusual pattern begins across {source} and {related}?",
             ["Choose the most dramatic summary chart", "Link source records and compare segments and time windows", "Pick a cause from the case title"], 1),
            (f"For the {title} mission ({mission[:160].rstrip('.')}), what would best support a proposed root cause?",
             ["A repeated pattern in related records that rules out alternatives", "One memorable anecdote", "The final score alone"], 0),
            ("How should you describe the impact of a proposed response?",
             ["As guaranteed real-world savings", "By comparing unrelated cases", "As a result under stated synthetic assumptions and trade-offs"], 2),
        ]
    return [
        (f"In a new {domain} case, {related} exceptions rise while {source} totals look stable. What do you examine first?",
         ["Only the executive total", "An unrelated department", "Linked records, timing and segment-level exceptions across the handoff"], 2),
        ("A proposed intervention improves one metric but adds cost and delay. What is the strongest recommendation?",
         ["Ignore the new costs", "Cite the supporting records and explain benefits, costs and uncertainty", "Claim the result proves workplace competence"], 1),
        ("A revised action improves the same synthetic case. What conclusion is justified?",
         ["It performed better in this practice model", "It guarantees the same customer outcome", "It certifies the learner for independent work"], 0),
    ]


def _ml_questions(phase, config):
    profile = ml_catalog.profile(config["profile"])
    title = profile["title"]
    group = config.get("group", profile.get("group", "model"))
    if config.get("family") == "forecasting":
        unit = profile.get("unit", "outcomes")
        series = (profile.get("series") or ["one group"])[0]
        if phase == "before":
            return [
                (f"A {title} forecast of {unit} degrades after deployment. Which comparison should begin the investigation?",
                 ["Only the original training loss", "Errors by time and segment against actuals and available drivers", "A different model's best score"], 1),
                ("A field was recorded after prediction time. How should it be handled when evaluating a forecast?",
                 ["Exclude it from prediction-time features and re-evaluate", "Keep it because it improves offline accuracy", "Hide it only in the report"], 0),
                ("Before applying a forecasting fix, what trade-off should be checked?",
                 ["Only the quickest retraining option", "Only a single aggregate error", "Error reduction, operational cost and performance across periods"], 2),
            ]
        return [
            (f"In an unseen {title} variation, errors spike for {series} in a few unusual periods while aggregate error stays steady. What should you inspect?",
             ["Only last month's overall mean", "Unrelated model logs", "Errors for those days and whether their drivers were available at prediction time"], 2),
            ("A new feed changes the unit of a forecasting input. Which response is best supported?",
             ["Retrain blindly", "Verify the unit change, correct the pipeline and compare held-out results", "Ignore it if the chart looks smooth"], 1),
            ("A synthetic rerun improves forecast error. What does that establish?",
             ["Better performance under these simulated assumptions", "Guaranteed production performance", "Permanent forecasting competence"], 0),
        ]
    target = str(profile.get("target", "predicted outcome")).replace("_", " ")
    if phase == "before":
        return [
            (f"A {title} model predicting {target} looks strong offline but weak in production. What should you compare first?",
             ["Only training accuracy", "Training and production features, label timing and segment performance", "Algorithms without checking the data"], 1),
            (f"For a {group} model, what most strongly supports a suspected failure mechanism?",
             ["A repeatable pattern across relevant probes and segments", "One surprising prediction", "The model's title"], 0),
            ("Before selecting a model fix, which outcome should be compared?",
             ["Only the fastest option", "Only one overall metric", "Recovered quality, false positives and investigation cost"], 2),
        ]
    return [
        (f"In a new {group} model, errors rise only for one monitored segment. What do you inspect?",
         ["Only the global average", "An unrelated model", "Segment inputs, labels and production-versus-training performance"], 2),
        ("A probe suggests an upstream feature-feed change. Which response is best justified?",
         ["Raise every threshold", "Verify and repair the feed, then compare held-out and production metrics", "Ignore the probe and redeploy"], 1),
        ("A synthetic rerun improves model quality. What conclusion is supported?",
         ["The change helped under these simulated assumptions", "Real customer savings are proven", "The learner is certified"], 0),
    ]


def question_set(kind, phase, row):
    p = row["payload"]
    raw = _case_questions(phase, p["scenario"]) if kind == "dataset" else _ml_questions(phase, p["config"])
    key = p["scenario"]["key"] if kind == "dataset" else p["config"].get("scenario") or p["config"]["profile"]
    result = []
    for index, (prompt, options, correct) in enumerate(raw):
        digest = hashlib.sha256(f"{VERSION}:{kind}:{key}:{phase}:{index}".encode()).digest()
        shift = digest[0] % len(options)
        result.append((prompt, options[shift:] + options[:shift], (correct - shift) % len(options)))
    return result


def questions(kind, phase, row):
    return [dict(id=i, prompt=q[0], options=q[1]) for i, q in enumerate(question_set(kind, phase, row))]


def _primary(kind, p):
    # A historical case can be retried, but its first assessment remains the
    # stable learning observation. Later attempts stay in its existing history.
    return (p.get("assessments") or [None])[0] if kind == "dataset" else p.get("submission")


def _score(kind, primary):
    if not primary:
        return None, None, None, None
    if kind == "dataset":
        maximum = dict(root=55, evidence=25, recommendation=20)
        labels = dict(root="Root-cause finding", evidence="Evidence interpretation", recommendation="Recommendation quality")
        components = {key: round(float(primary.get(key, 0)), 1) for key in maximum}
    else:
        maximum = dict(diagnosis=45, recovery=35, fix_precision=10, efficiency=10)
        labels = dict(diagnosis="Failure diagnosis", recovery="Recovery after fix", fix_precision="Fix precision", efficiency="Investigation efficiency")
        parts = primary.get("parts") or {}
        components = {"diagnosis": round(45 * float(parts.get("diagnosis_f1", 0)), 1),
                      "recovery": round(35 * float(parts.get("recovery", 0)), 1),
                      "fix_precision": round(10 * float(parts.get("fix_precision", 0)), 1),
                      "efficiency": round(10 * float(parts.get("efficiency", 0)), 1)}
    return primary.get("score"), components, maximum, labels


def _public_submission(record):
    if not record:
        return None
    return {k: v for k, v in record.items() if k != "answer_key"}


def _journey(primary, after, before, components, maximum, labels):
    strengths, next_steps = [], []
    if not primary:
        next_steps.append("Inspect the evidence and submit your case or model diagnosis.")
    else:
        for key, maximum_points in maximum.items():
            earned = components[key]
            if earned >= 0.8 * maximum_points:
                strengths.append(f"Strong {labels[key].lower()} in this practice task.")
            elif earned < 0.5 * maximum_points:
                next_steps.append(f"Revisit {labels[key].lower()} using the available evidence.")
        if not after:
            next_steps.append("Complete the post-practice knowledge check.")
        elif after["correct"] < after["total"]:
            next_steps.append("Review missed answers and try an unseen variation.")
        if not before:
            next_steps.append("Take the starting check on your next exercise to measure knowledge change.")
        if after and not next_steps:
            next_steps.append("Try an unseen exercise later to check transfer and retention.")
    return dict(status="complete" if primary and after else "post_check_due" if primary else "in_progress",
                strengths=strengths[:4], next_steps=next_steps[:4],
                note="Practice evidence only; this does not establish workplace competence or retention.")


def view(kind, row):
    p = row["payload"]
    state = p.get("learning_check") or {}
    before, after = state.get("before"), state.get("after")
    primary = _primary(kind, p)
    score, components, maximum, labels = _score(kind, primary)
    if not maximum:
        _, _, maximum, labels = _score(kind, {"score": None})
    eligible = state.get("version") == VERSION and not state.get("evidence_started") and not primary
    baseline_open = bool(eligible and not before)
    post_open = bool(primary and not after)
    if before:
        baseline_note = None
    elif not state.get("version"):
        baseline_note = "This older exercise has no starting check; knowledge change is unavailable."
    elif not baseline_open:
        baseline_note = "The starting check closed when practice evidence was opened; knowledge change is unavailable."
    else:
        baseline_note = None
    result = dict(
        version=VERSION,
        before=_public_submission(before),
        after=_public_submission(after),
        baseline_open=baseline_open,
        post_open=post_open,
        before_questions=(before.get("questions") if before else questions(kind, "before", row) if baseline_open else []),
        after_questions=(after.get("questions") if after else questions(kind, "after", row) if primary else []),
        gain_pp=round(after["score"] - before["score"], 1) if before and after else None,
        learning_score=score,
        score_components=components,
        max_points=maximum,
        component_labels=labels,
        practice_score_basis="First historical case assessment" if kind == "dataset" else "ML diagnosis submission",
        baseline_note=baseline_note,
        learning_journey=_journey(primary, after, before, components, maximum, labels),
        note="Objective knowledge change is separate from the existing illustrative practice score.",
    )
    if after:
        result["answer_keys"] = {"before": before.get("answer_key", []) if before else [],
                                 "after": after.get("answer_key", [])}
    return result


def _submit(kind, rid, phase, body, current, resource):
    if phase not in {"before", "after"}:
        raise HTTPException(404, "Unknown learning-check phase")
    row = resource(rid, kind, current)
    if row["owner"] != current["id"]:
        raise HTTPException(403, "Observers cannot answer a learner's knowledge check")
    current_view = view(kind, row)
    if not current_view["baseline_open" if phase == "before" else "post_open"]:
        raise HTTPException(409, "This check is closed or already submitted")
    quiz = question_set(kind, phase, row)
    if any(choice < 0 or choice >= len(question[1]) for choice, question in zip(body.choices, quiz)):
        raise HTTPException(422, "Select one listed answer for each question")
    correct = sum(choice == question[2] for choice, question in zip(body.choices, quiz))
    state = row["payload"].setdefault("learning_check", initial_state())
    state[phase] = dict(choices=body.choices, correct=correct, total=len(quiz),
                        score=round(100 * correct / len(quiz), 1),
                        questions=questions(kind, phase, row),
                        answer_key=[q[2] for q in quiz],
                        submitted_at=time.time(), assessment_version=VERSION)
    if not store.update(rid, row["payload"], row["version"]):
        raise HTTPException(409, "Exercise changed; refresh and try again")
    store.audit(current["id"], "learning." + kind + "." + phase, rid)
    return view(kind, store.get(rid, kind))


def install(app, user, resource):
    @app.get("/api/datasets/{rid}/learning-check")
    def case_check(rid: str, current=Depends(user)):
        return view("dataset", resource(rid, "dataset", current))

    @app.post("/api/datasets/{rid}/learning-check/skip")
    def case_skip(rid: str, current=Depends(user)):
        row = resource(rid, "dataset", current)
        if row["owner"] != current["id"]:
            raise HTTPException(403, "Observers cannot change a learner's knowledge check")
        if not view("dataset", row)["baseline_open"]:
            raise HTTPException(409, "The starting check is already closed")
        return view("dataset", mark_evidence_started(row, current))

    @app.post("/api/datasets/{rid}/learning-check/{phase}")
    def case_submit(rid: str, phase: str, body: Answers, current=Depends(user)):
        return _submit("dataset", rid, phase, body, current, resource)

    @app.get("/api/mllab/labs/{rid}/learning-check")
    def lab_check(rid: str, current=Depends(user)):
        return view("ml_lab", resource(rid, "ml_lab", current))

    @app.post("/api/mllab/labs/{rid}/learning-check/skip")
    def lab_skip(rid: str, current=Depends(user)):
        row = resource(rid, "ml_lab", current)
        if row["owner"] != current["id"]:
            raise HTTPException(403, "Observers cannot change a learner's knowledge check")
        if not view("ml_lab", row)["baseline_open"]:
            raise HTTPException(409, "The starting check is already closed")
        return view("ml_lab", mark_evidence_started(row, current))

    @app.post("/api/mllab/labs/{rid}/learning-check/{phase}")
    def lab_submit(rid: str, phase: str, body: Answers, current=Depends(user)):
        return _submit("ml_lab", rid, phase, body, current, resource)
