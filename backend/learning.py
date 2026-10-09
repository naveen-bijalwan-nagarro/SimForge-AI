"""Objective, CPU-scored learning checks; not a competence certification.

Separate learning evidence from simulated operational impact. The learner alone
answers three pre- and three post-run multiple-choice questions. Practice
scoring additionally uses logged investigation, diagnosis and repair actions.
"""

import time

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from . import store

VERSION = "objective-learning-v3"

# Parallel questions: compare reasoning rather than repeat an identical quiz.
QUESTIONS = {
    "before": [
        ("Orders are late. Dispatch queues grow while downstream systems are healthy. What do you inspect first?",
         ["The customer dashboard only", "Dispatch records and the next handoff", "Every system at once"], 1),
        ("Before committing a response, what should you check?",
         ["Evidence, target, cost and delay", "Only the fastest-looking button", "Only the final score"], 0),
        ("Which comparison best isolates the effect of your decisions?",
         ["A different workload", "Another learner's best run", "The same seed and workload with no action"], 2),
    ],
    "after": [
        ("In a new warehouse incident, receiving is normal, packing queues grow and carrier capacity is healthy. Where do you investigate first?",
         ["Carrier capacity", "Customer email", "Packing records and the next handoff"], 2),
        ("Evidence points to a failed validation step. Which response is best justified?",
         ["Restart every system", "Repair that step after checking its delay and budget", "Ignore the evidence and reroute everything"], 1),
        ("Your run beats the identical no-action workload. What can you conclude?",
         ["The response helped under these simulated assumptions", "It proves real customer savings", "It proves permanent job competence"], 0),
    ],
}


class Answers(BaseModel):
    model_config = {"extra": "forbid"}
    choices: list[int] = Field(min_length=3, max_length=3)


def question_set(phase, p=None):
    """Workflow-specific objective checks for admin-generated exercises.

    Prompts never quote the hidden fault/cause or privileged authoring content.
    """
    spec = (p or {}).get("spec", {})
    if not str(spec.get("key", "")).startswith("custom_"):
        return QUESTIONS[phase]
    nodes = [n.get("label") or n.get("id", "system") for n in spec.get("nodes", [])]
    first = nodes[0] if nodes else "the first handoff"
    later = nodes[-2] if len(nodes) >= 2 else "a downstream handoff"
    if phase == "before":
        return [
            (f"Hypothetical check: work is delayed near {first}. What should you inspect first?",
             ["Only the final dashboard", "Source records and the adjacent handoff", "Change every system"], 1),
            ("What must you compare before intervening?",
             ["Evidence, risk, response delay and cost", "Only the shortest action", "Only the final score"], 0),
            ("What is a fair way to measure the impact of a response?",
             ["Different work volumes", "Another learner's result", "The same seeded workload with no intervention"], 2),
        ]
    return [
        (f"In a different exercise, queues grow near {later} while upstream processing is healthy. What should you inspect?",
         ["Change every capacity", "Only customer complaints", "This handoff's records and downstream processing"], 2),
        ("Evidence reveals a faulty workflow rule. Which action is safest?",
         ["Restart everything", "Verify and repair the targeted rule, checking cost", "Ignore the cause and reroute all work"], 1),
        ("Your response beats the same-workload no-action run. What is supported?",
         ["Better results under these simulation assumptions", "Guaranteed real financial savings", "Certified job competence"], 0),
    ]


def questions(phase, p=None):
    return [dict(id=i, prompt=q[0], options=q[1]) for i, q in enumerate(question_set(phase, p))]


def evidence(p):
    actions = {a["id"]: a for a in p["spec"]["actions"]}
    valid = [(d, actions[d["action_id"]]) for d in p["decisions"] if d["action_id"] in actions]
    kinds = [a["effect"] for d, a in valid]
    first_response = next((i for i, kind in enumerate(kinds) if kind != "inspect"), None)
    diagnosis = p.get("diagnosis") or {}
    incident = p["spec"]["incident"]
    timely = incident["tick"] <= diagnosis.get("tick", p["horizon"]) < p["horizon"]
    inspection = next((i for i, (d, a) in enumerate(valid)
                       if a["effect"] == "inspect" and incident["tick"] <= d["tick"] < p["horizon"]), None)
    return dict(
        inspected_before_response=bool(inspection is not None and first_response is not None
                                       and inspection < first_response),
        diagnosis_before_debrief=bool(timely),
        diagnosis_correct=bool(timely and diagnosis.get("root_node") == incident["node"]
                               and diagnosis.get("cause") == incident["cause"]),
        targeted_repair=any(a and a["effect"] == "repair" and a["target"] == incident["node"]
                            and incident["tick"] <= d["tick"] and d["tick"] + a["duration"] <= p["horizon"]
                            for d, a in valid),
        action_count=len(kinds),
    )


def objective_result(p):
    """No model/keyword grader or manually assigned score.

    50 knowledge + 25 diagnosis + 15 evidence-first + 10 targeted repair.
    No score until the post-run check is submitted. Knowledge gain is distinct.
    """
    data = p.get("learning_check", {})
    after = data.get("after")
    if not after or p["tick"] < p["horizon"]:
        return None
    observed = evidence(p)
    components = {
        "knowledge": round(50 * after["correct"] / max(1, after["total"]), 1),
        "diagnosis": 25 if observed["diagnosis_correct"] else 0,
        "evidence": 15 if observed["inspected_before_response"] else 0,
        "decision": 10 if observed["targeted_repair"] else 0,
    }
    return dict(score=round(sum(components.values()), 1), components=components,
                max_points=dict(knowledge=50, diagnosis=25, evidence=15, decision=10))


def learning_journey(p):
    data = p.get("learning_check", {})
    before, after = data.get("before"), data.get("after")
    complete = p["tick"] >= p["horizon"]
    observed = evidence(p) if complete else {}
    strengths, next_steps = [], []
    if not complete:
        next_steps.append("Inspect records, diagnose the cause, then choose a response.")
    else:
        if observed["inspected_before_response"]:
            strengths.append("Investigated before acting.")
        else:
            next_steps.append("Review evidence before committing a response.")
        if observed["diagnosis_correct"]:
            strengths.append("Diagnosed the incident correctly.")
        else:
            next_steps.append("Practise identifying the first failing handoff.")
        if observed["targeted_repair"]:
            strengths.append("Used a targeted repair.")
        else:
            next_steps.append("Compare targeted repair with wider interventions.")
    if after:
        if after["correct"] == 3:
            strengths.append("Answered all post-run questions correctly.")
        else:
            next_steps.append("Review missed questions and try an unseen variation.")
    elif complete:
        next_steps.append("Complete the objective post-run knowledge check.")
    if not before and complete:
        next_steps.append("Take the baseline on the next exercise to measure knowledge change.")
    if complete and after and not next_steps:
        next_steps.append("Try an unseen variation later to check independent transfer and retention.")
    return dict(status="complete" if complete and after else "post_check_due" if complete else "in_progress",
                strengths=strengths, next_steps=next_steps[:4],
                note="Scores show performance in this practice exercise, not workplace competence or retention.")


def view(row):
    p = row["payload"]
    data = p.get("learning_check", {})
    before, after = data.get("before"), data.get("after")
    complete = p["tick"] >= p["horizon"]
    eligible = (p["tick"] == 0 and not p.get("clock", {}).get("running")
                and not p.get("clock", {}).get("started_at") and not p["decisions"]
                and not p.get("diagnosis") and not p.get("parent"))
    objective = objective_result(p)
    return dict(
        version=VERSION, before=before, after=after,
        baseline_open=eligible and not before,
        post_open=complete and not after,
        before_questions=questions("before", p) if eligible else [],
        after_questions=(after.get("questions") or questions("after", p)) if after else questions("after", p) if complete else [],
        gain_pp=round(after["score"] - before["score"], 1) if before and after else None,
        evidence=evidence(p) if complete else None,
        learning_score=objective["score"] if objective else None,
        score_components=objective["components"] if objective else None,
        max_points=objective["max_points"] if objective else dict(knowledge=50, diagnosis=25, evidence=15, decision=10),
        learning_journey=learning_journey(p),
        answer_keys={phase: [q[2] for q in question_set(phase, p)] for phase in QUESTIONS} if after else None,
        note="Objective training evidence only. Measure transfer and retention with an unseen exercise.",
    )


def install(app, user, admin, resource):
    from . import main

    @app.get("/api/runs/{rid}/learning-check")
    def get_check(rid: str, current=Depends(user)):
        return view(main.sync_clock(resource(rid, "run", current)))

    @app.post("/api/runs/{rid}/learning-check/{phase}")
    def submit(rid: str, phase: str, body: Answers, current=Depends(user)):
        if phase not in QUESTIONS:
            raise HTTPException(404, "Unknown learning-check phase")
        row = main.writable_run(rid, current)
        main.clock_tick(row)
        p = row["payload"]
        state = view(row)
        if not state["baseline_open" if phase == "before" else "post_open"]:
            raise HTTPException(409, "This check is closed or already submitted")
        if any(c < 0 or c >= len(q[1]) for c, q in zip(body.choices, question_set(phase, p))):
            raise HTTPException(422, "Select one listed answer for each question")
        correct = sum(c == q[2] for c, q in zip(body.choices, question_set(phase, p)))
        p.setdefault("learning_check", {})[phase] = dict(
            choices=body.choices, correct=correct, total=3,
            score=round(100 * correct / 3, 1), questions=questions(phase, p),
            submitted_at=time.time(), tick=p["tick"], assessment_version=VERSION,
        )
        main.save_run(row, current, "learning." + phase)
        return view(store.get(rid, "run"))
