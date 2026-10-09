# Adding new use cases

The hackathon edition has one authoring page: **Scenario Lab**, available only to **Admin / Trainer**. Learners run published exercises. New scenarios are structured data, not executable code, and publication requires passing validation checks and an administrator's review.

| Route | Who | Best for |
|---|---|---|
| Scenario Lab: Codex CLI | Admin / Trainer | Describe the learning mission; signed-in local CLI produces a checked draft |
| Scenario Lab: OpenAI API | Admin / Trainer | Same workflow without a CLI installation; uses server-side API credentials |
| Scenario Lab: Offline template | Admin / Trainer | Edit Supplier disruption, Service application or Block-building world JSON without an external model |
| YAML pack file | Developer | Version-controlled packs in `scenario_packs/` or `backend/packs/` |

## Scenario Lab: the supported UI flow

1. Sign in as `admin` and open **Scenario Lab**.
2. Select **Codex CLI**, **OpenAI API** or **Offline template**. For CLI, enable authoring and sign in through the connection panel. For API, enter a key/model in the masked admin connection panel; saving does not make a billed generation request. See [README credential safety](../README.md#api-credential-safety).
3. Describe the learner's mission, systems, work units, branching dependencies, hidden incident, evidence and measurable success criteria. Use `service_app` for mock software and `voxel` for block-building worlds. The CLI/API paths create constrained JSON, not arbitrary applications or executed code.
4. Generate a draft, or edit the template JSON and **Validate & save draft**. Python runs schema and simulation checks.
5. On the same page, inspect **Check and publish**. Check the mission, workflow and all validation results, then **Publish & notify learners**. There is no separate SOP page, advanced builder, sandbox page or third-role approval.
6. The learner opens the notification, generates a seeded workload and inspects linked tables. The simulation uses those saved records. Prepared environments remain available in **Training datasets → Scenario-generated datasets**.

For procedure-based scenarios, translate a non-sensitive SOP into synthetic requirements in this same page. Automated document-upload/sanitization and the old SOP repair pipeline are not exposed in this simplified UI. Validate domain accuracy with a subject-matter expert before relying on an AI-generated exercise.

## Legacy developer tooling: terminal sandbox (not a demo page)

```powershell
.\scripts\codex-sandbox.ps1
.\scripts\codex-sandbox.ps1 -Prompt "Create a Minecraft-style mining village where a tunnel collapse starves crafting"
.\scripts\codex-sandbox.ps1 -DryRun     # print the exact codex command
```

Codex runs with `--sandbox workspace-write` in `codex_sandbox/`, reads `AGENTS.md`, asks a few
questions, writes `drafts/<key>.yaml`, calls `validate_scenario` and `run_scenario_tests` until
everything passes, previews the story with `generate_simulator`, then calls
`submit_for_approval`. It cannot publish.

## Legacy SOP engine (internal compatibility only)

The earlier factory backend is retained for compatibility and regression testing; its UI is not part of this edition. All management endpoints are now administrator-only. Existing factory outputs can still enter the shared publication queue, but a separate trainer role is not accepted. Tips for turning procedures into Scenario Lab requirements:

- Number the procedure steps (`1. Title: what happens…`) and name who performs each step.
- Put measurable thresholds in the text ("more than 24 hours", "less than 5 days", "exceeds 10%").
- List roles under a `## Roles` heading.
- Loops such as "return to step 2" are allowed; they become consequence rules, not cycles.

## Scenario Lab template JSON

Admin / Trainer → **Scenario Lab** → **Offline template**: start from *Supplier disruption*, *Service application* or *Block-building world*, edit the
JSON (systems, dependencies, incident node, cause, learner role, mission, success), **Validate &
save draft**, then publish.

## YAML scenario packs

A pack is a YAML list of worlds. Minimal example:

```yaml
- key: warehouse_blackout
  title: Warehouse Blackout
  category: Industrial & Energy
  summary: A power fault at the distribution centre stalls picking and delays customer orders.
  unit: orders
  impact: late orders
  budget: 7000
  environment_style: workflow          # workflow | voxel | service_app
  nodes:                               # [id, label, role, capacity, evidence modality, source system]
    - [power, Site power, engineering, 4, sensor, BMS]
    - [picking, Picking robots, operations, 5, log, WMS]
    - [dispatch, Dispatch, operations, 5, map, TMS]
    - [customers, Customer promises, finance, 6, kpi, Service dashboard]
  edges: [[power, picking], [picking, dispatch], [dispatch, customers]]
  incident: {node: power, cause: A failed UPS transfer switch drops half the racks., signal: rack voltage alarms}
  actions:                             # [id, label, target, effect, cost, duration, description]
    - [fix_ups, Replace transfer switch, power, repair, 2000, 4, Restore power.]
    - [inspect_power, Inspect power telemetry, power, inspect, 200, 0, Gather evidence.]
    - [manual_pick, Manual picking teams, picking, boost, 1100, 1, Temporary capacity.]
    - [split_ship, Ship from partner depot, dispatch, reroute, 1400, 2, Bypass local dispatch.]
  rules:
    - {name: late_wave, at: 14, when: ["power.intrinsic<60", "!picking.boosted"], target: customers, health: 45, message: Delivery promises missed.}
  decoys: [A carrier strike, A demand spike]
  agents: {engineering: Site engineer, operations: Shift manager, finance: Customer lead}
  entity: {order: Order, customer: Customer, value: [20, 900]}
  emits: [{signal: delayed_shipments, node: customers, below: 60}]
  consumes: [blackout]
```

Reference:

- **Roles**: investigator, operations, finance, security, safety, engineering, medical, legal, emergency, executive.
- **Evidence modalities**: log, email, sensor, image, video, map, ticket, document, transaction, graph, chat, kpi. Image/video nodes use `visual` (or per-node `visuals`): surface, tower, turbine, traffic, thermal, aerial, cells. `visual_lighting: {node: factor}` changes camera exposure after that node degrades.
- **Effects**: repair, contain, reroute, boost, inspect.
- **Rule conditions** (all must hold): `node.health<60`, `node.intrinsic>=40`, `node.isolated`, `!node.bypass`, `node.boosted`.
- **Compound crises**: `extra_incidents: [{node, tick, severity, cause, signal}]`.
- **Entity fields**: a shared kind (`Supplier`, `Machine`, …), `[min, max]`, a list of choices, or `'seq:PREFIX'`.
- **Connections**: `emits` fire when the node falls below `below`; any scenario with a matching `consumes` can be launched from the debrief.

Validate and test:

```powershell
.\.venv\Scripts\python.exe scripts\scenario_kit.py validate my_pack.yaml
.\.venv\Scripts\python.exe scripts\scenario_kit.py test my_pack.yaml
.\.venv\Scripts\python.exe scripts\scenario_kit.py submit my_pack.yaml     # draft for admin approval
.\.venv\Scripts\python.exe scripts\scenario_kit.py install my_pack.yaml    # developer route: scenario_packs/
```

Tests a world must pass: valid schema/acyclic connected graph, simulation executes, incident
injected, disruption propagates, root-cause repair exists and reduces impact, an inspect action
exists, deterministic replay, hidden cause never shown, ≥2 distractors; plus red-team checks
(no injected/destructive/governance-bypassing actions, bounded effects, every response consequential).

## Adding datasets for a use case

Open **Dataset studio**, pick the world, and start from its recommended schema, or pick a template.
Edit tables and columns, add anomalies for ground truth, validate, preview, and export. Save the
schema to reuse it; `schema.json` in the export regenerates the identical dataset.

## Adding ML investigations to Scenario library

Profiles live in `backend/mllab/catalog.py`:

- **Classification** profiles: features `(name, dist, a, b, coefficient, unit, description)`, base rate, costs, segment, optional collusion ring, and leak/future feature names.
- **Forecasting** profiles: series, weekly shape, yearly amplitude, trend, driver, unit and noise.

ML exercises appear under **Scenario library → ML investigations**, as well as searchable cards in **All exercises**. They retain their separate model/scoring engine. Add a profile and it appears in the catalogue for random challenges. Add an entry to `ADVANCED`
for a named multi-failure story. Run `pytest tests/test_mllab.py` to confirm every failure still
degrades and recovers.
