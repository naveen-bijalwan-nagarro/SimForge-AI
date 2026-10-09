# SimForge AI — one Scenario Lab, two roles, four minutes

Use the [FactoryPulse admin prompt](../samples/sample1/admin_prompt.txt) with the [operations brief](../samples/sample1/FactoryPulse_Operations_Brief.docx) and [sensor charts](../samples/sample1/FactoryPulse_Sensor_Charts.pdf); the [synthetic privacy examples](../samples/sample1/FactoryPulse_Privacy_Examples.docx) are optional for screening. These four files form an Admin / Trainer upload packet for one machine-failure exercise. The timed route below covers the recording. Baseline → observed decisions → post-check → automatic score breakdown is implemented, not just a proposed pilot measure.

## Promise and boundaries

We help staff move from passive slides or risky exploration of live tools to practising evidence-based decisions in a self-contained mock-data environment.

**Admin / Trainer** creates, checks and publishes. **Learner** runs the exercise and reviews the result. No third account, SOP factory page or advanced builder page is required.

Use the FactoryPulse exercise: sensors → machine → production → quality → shipments, with schedule → production. The environment is illustrative training, not an exact replica or validated physical twin. Synthetic delays and costs are not proven customer outcomes.

## Prepare

- Start the Python app with the built React UI; SQLite stores scenarios, data, runs and decisions.
- Open two independent browser profiles/private contexts: admin and learner. Tabs in the same profile share sign-in.
- In Scenario Lab, select Codex CLI and check the actual connection/model before the presentation.
- Codex is always primary. For an unavailable CLI/sign-in/quota, explicitly choose Use OpenAI API backup and configure the key/model, or provision the private file in [README](../README.md#persistent-api-backup-configuration). Only the Generate action invokes the backup; no automatic retry or charge occurs when switching. This is API authoring, not Codex CLI activity.
- Prepare a previously generated, labelled draft because live generation may exceed the presentation window. State when it was generated and with which engine.
- Before the demo, use Fresh demo: archive previous custom scenarios, review the preview and type ARCHIVE. Old custom publications/drafts are hidden, not deleted; do not archive your labelled fallback until you no longer need it. Built-in templates and learner records remain.
- Paste [the FactoryPulse prompt](../samples/sample1/admin_prompt.txt) and upload the [operations brief](../samples/sample1/FactoryPulse_Operations_Brief.docx) and [sensor charts](../samples/sample1/FactoryPulse_Sensor_Charts.pdf) through Scenario Lab. Review extracted previews. Upload the [synthetic privacy examples](../samples/sample1/FactoryPulse_Privacy_Examples.docx) only if demonstrating screening; they are not needed for the operational exercise. Voice input is optional and collapsed; typing is the dependable fallback.
- Use 60 work items, seed 2026 and a 35-minute simulated horizon. Playback at 3× advances simulated time; it is not a 35-minute wall-clock presentation.
- Pause while explaining data. Keep optional 3D/ML tools out of the main demo.

## 0:00–0:30 — problem and roles

Show Overview: “Staff need to practise real business decisions without touching live systems. The Admin / Trainer creates a safe exercise; the Learner investigates linked mock records and chooses a response.”

## 0:30–1:20 — one Scenario Lab

Select Scenario Lab. One page contains **1 · Create an exercise** and **2 · Check and publish**.

Show the selected references and their extracted previews. Optionally dictate one sentence, then stop and edit it. Upload/voice capture does not call Codex or publish anything; only Generate sends selected excerpts to the chosen engine. Keep this demonstration under 10 seconds by uploading before presenting.

Use a prompt such as:

> Create a synthetic FactoryPulse exercise for a plant supervisor. Connect sensors, machine condition, production schedule, quality inspection and shipments. A vibration-sensor calibration fault should hide bearing degradation and cause delays. Include evidence-led diagnosis, maintenance and production-reallocation decisions.

Generate with the selected engine. Show real job progress if ready. If it is still running, transparently inspect the previously generated, labelled draft and explain when and how it was generated.

Inspect the draft's source, mission, workflow and checks. Click Publish & notify learners. Explain that the output is a schema-constrained definition validated in Python, never executable generated code.

## 1:20–2:50 — learner generates, investigates and acts

Switch to Learner. Open Notifications → the new scenario.

Show the mission. Generate 60 work items. Inspect work_items/workflow_steps and relationship checks, then Enter simulation with these datasets.

Complete the visible three-MCQ starting check before playback. Starting knowledge, post-check knowledge, practice score and knowledge change stay above the simulator. After completion, use Learning review for three post-run MCQs and the automatic 100-point breakdown (knowledge 50, diagnosis 25, investigation before response 15, targeted repair 10). No subjective response or trainer-assigned mark is required. Missing baseline means no gain calculation; an unseen follow-up is needed to test retention.

Show a record flowing through the mock application. Start playback and pause near the incident. Inspect the record and Data & visual tools → Live datasets → live_telemetry/source_events. Compare available sensor, machine, quality and shipment evidence before diagnosing the fault.

Use Diagnose & act to identify the first failing system and an evidence-supported cause. In Diagnose & act → Decision desk, commit an appropriate repair. Explain its target, synthetic cost and delay. Resume or step to observe consequences, then Complete run.

These records were generated for this scenario and saved, not fetched from a live client system. Training datasets → Scenario-generated datasets can reopen them later.

## 2:50–3:35 — measurable, explainable outcome

Show the debrief's revealed cause, decision ledger and same-workload no-intervention comparison. Export the report if time permits.

Distinguish simulation evidence from customer validation. Propose a small pilot measuring diagnosis time, pre/post assessment improvement and trainer preparation minutes per approved exercise. Use comparable baselines and feedback; claim no unmeasured customer benefit.

## 3:35–4:00 — coaching and responsible engineering

Return to the same Admin / Trainer → Assignments & results. Assign guidance, or open the learner's completed run in Observation mode. Clock, diagnosis and decision controls cannot take over learner-owned work.

Close: “Codex helped build this application and can author checked scenarios. A deterministic CPU simulator generates linked mock evidence and executes consequences. Humans control publication and learners control their responses.”

The API route is a deployment fallback, not a claim that every runtime inference uses Codex. Show actual Codex-generated work if claiming Codex leverage.

## Production boundary

This is a production-minded pilot. It includes server-side role/ownership checks, logout, bounded inputs, versioned updates, publication transactions, source provenance, audit, retries and reproducible runs.

Before deployment, complete the HTTPS, identity, backup/restore, retention, monitoring/load and domain-validation work in [DEPLOYMENT.md](DEPLOYMENT.md). UI-entered API keys remain only in backend memory; use server secrets for persistence. No passing test suite constitutes production certification.

## Regression evidence

- Backend tests cover two-role publication/notification, owner-only decisions, admin previews, API structured outputs, no-CLI operation, secret-safe errors and migration.
- roles.spec.js covers the complete admin/learner handoff and supplier diagnosis/action/debrief.
- scenario-lab.spec.js covers one-page navigation, write-only API-key UI and unified ML discovery; it never requests real paid API generation.
- navigation.spec.js and training-navigation.spec.js cover durable routes, case files, slow/out-of-order requests and retries.
- API tests use a mocked provider. Real Codex generation remains opt-in. Respect unchanged login throttling when running large browser batches.
