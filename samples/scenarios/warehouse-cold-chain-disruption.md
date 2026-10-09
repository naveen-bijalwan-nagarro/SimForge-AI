# Warehouse cold chain disruption

**Purpose:** Synthetic Scenario Lab demo brief. This example contains no real customer or employee data. Costs, quantities, and outcomes are training values, not a claim about a real warehouse.

## Learner-facing setup

You are the shift controller at a regional cold-chain distribution center. Several priority store orders are falling behind, while the warehouse dashboard still shows enough stock to meet demand. Investigate the linked records, decide what to protect first, and restore service before the response budget is exhausted. Explain which evidence supports your diagnosis and what risk remains after your response.

## Authoring prompt

Create a SimForge workflow scenario called **The Missing Pallets** for a cold-chain warehouse shift controller. The learner's mission is to protect priority store orders, identify the operational fault, and restore dispatch while limiting spoilage risk and response cost.

Model these systems and dependencies: supplier appointment feed → receiving scans → cold storage inventory → picking queue → dispatch planning → store orders. Add a quality-monitoring branch from cold storage that rejoins the order-impact path through picking. Use realistic labels and synthetic records only.

For the authoring draft, set the hidden root cause at receiving: a retry in the appointment-feed adapter marks a partial advance-shipping notice as fully received, so the system counts pallets that have not arrived. Keep that cause out of the learner briefing and initial evidence. The learner should first observe a growing pick backlog, repeated receipt events, and a mismatch between the inventory ledger and dock scans.

Make the following evidence inspectable: receipt-event timestamps and IDs, dock-scan counts, inventory adjustments, temperature-monitor readings, pick-queue age, dispatch cutoffs, and store-order priority. Include at least two plausible but incorrect explanations: a short-lived demand surge and a temperature-sensor calibration drift. Evidence should help distinguish these from the actual receiving fault without stating the answer.

Offer meaningful actions: inspect receipt and inventory evidence; repair the adapter's idempotency/receipt reconciliation at receiving; contain suspect inventory pending a physical count; reroute available stock from a nearby depot; and use temporary manual picking capacity. Give actions nonzero cost or time where appropriate, expose dependencies, and show trade-offs such as slower throughput, higher transport cost, or increased spoilage risk. Include a root-cause repair and an investigation action.

Track on-time priority orders, pick backlog, spoilage exposure, recovery time, and response spend. Compare the chosen response with a no-intervention baseline. Use an explicitly illustrative response budget and targets; do not state that the scenario proves real savings or customer outcomes. The generated learner debrief should reveal the root cause and connect it to the evidence and consequences.

Use synthetic data, do not generate executable code, and keep the scenario as a draft. The Admin / Trainer must inspect the mission, hidden cause, actions, and validation checks before publishing. The demo is ready when the draft passes the app's checks, the cause remains hidden until debrief, and a seeded run can show investigation, a consequential response, and a before/after comparison in a short repeatable path.

## Demo evidence to capture

- The initial backlog and conflicting receipt/inventory evidence.
- At least one inspection action and the evidence it returns.
- The selected response and its cost, time, and trade-off.
- The debrief showing the hidden cause and the chosen run compared with baseline.
- The trainer's validation/review state before publication.

Keep claims about user validation, production readiness, and impact tied to evidence collected outside this synthetic exercise.
