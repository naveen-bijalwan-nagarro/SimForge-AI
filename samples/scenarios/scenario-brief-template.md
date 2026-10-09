# Scenario brief template

Use this as a reference document or copy its sections into a Scenario Lab description. Replace every bracketed field and remove sections that do not apply. Keep the learner-facing mission separate from the author-only hidden cause.

## Scenario identity

- **Title:** [short, specific title]
- **Domain:** [industry or workflow]
- **Environment style:** [workflow, service_app, or voxel]
- **Learner role:** [job role and decision authority]
- **Intended demo length:** [minutes]

## Problem and learning mission

- **Operational problem:** [what can go wrong and who is affected]
- **Why it matters:** [supported impact measure or clearly marked training assumption]
- **Learner-facing mission:** [what the learner needs to achieve without revealing the hidden cause]
- **Learning objectives:** [skills or decisions to practice]

## System and flow

List 4–8 systems or teams, then describe how work and impact flow between them. Name any parallel paths and where they rejoin.

| System or team | Role in the workflow | Capacity or constraint | Evidence available |
|---|---|---|---|
| [system] | [responsibility] | [capacity/limit] | [log, sensor, transaction, ticket, map, chat, KPI] |

**Dependencies:** [system A → system B → system C; describe branches]

## Author-only incident design

- **Hidden root cause:** [one concrete fault; do not put it in the learner briefing]
- **Affected system:** [system]
- **Start time or trigger:** [time/event]
- **Initial learner-visible symptoms:** [what is observable first]
- **Evidence that distinguishes the cause:** [specific facts available through investigation]
- **Plausible decoys:** [at least two distinct but incorrect explanations]

## Learner choices and consequences

| Action | Type | Target | Cost or delay | Dependency | Intended trade-off |
|---|---|---|---|---|---|
| [inspect evidence] | inspect | [system] | [cost/time] | [none or prerequisite] | [what uncertainty it reduces] |
| [fix root cause] | repair | [system] | [cost/time] | [evidence or prerequisite] | [benefit and residual risk] |
| [contain or workaround] | contain/reroute/boost | [system] | [cost/time] | [limit] | [temporary benefit and downside] |

Every response should have a meaningful consequence. Include a viable root-cause repair and an investigation action.

## Success and debrief

- **Metric 1:** [name, unit, target]
- **Metric 2:** [name, unit, target]
- **Budget or time limit:** [unit and limit]
- **Baseline comparison:** [what the no-intervention run should demonstrate]
- **Debrief:** [reveal the cause, connect evidence to diagnosis, compare decisions and outcomes]
- **Assumptions:** [what is synthetic or illustrative; what would need domain validation]

## Demo proof and safety

- **Repeatable demo path:** [role, starting view, steps, expected visible result]
- **Evidence to capture:** [before/after metric, evidence record, validation result, debrief]
- **Privacy:** use synthetic, non-sensitive information only.
- **Human review:** an Admin / Trainer checks the draft and validation results before publishing.
- **Out of scope:** [features the demo does not claim to implement]

## Prompt to paste into Scenario Lab

Create a [domain] training scenario for a [learner role]. The learner must [mission] while protecting [measurable outcomes]. Model [systems] with dependencies [workflow]. For the authoring draft, use this hidden incident: [cause at system/time]; keep it out of the learner briefing until the debrief. Make [symptoms] visible and provide inspectable evidence from [sources]. Include the plausible decoys [decoys]. Give the learner investigation, root-cause repair, and [containment/reroute/temporary capacity] actions with clear cost, delay, prerequisites, and consequences. Track [metrics and units], compare with the no-intervention baseline, and mark all generated costs and outcomes as illustrative. Use synthetic data, no executable code, and keep the scenario in draft for trainer review. The draft is done when it passes validation, the cause remains hidden until debrief, and the end-to-end demo path is repeatable.
