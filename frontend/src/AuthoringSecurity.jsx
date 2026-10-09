import React, { useEffect, useState } from "react";
import { api } from "./client";

export const genericScenario = {
  title: "New training scenario",
  summary:
    "A workflow interruption delays synthetic work. Investigate the affected handoffs and choose a response.",
  unit: "tasks",
  environment_style: "workflow",
  learner_role: "Workflow coordinator",
  mission:
    "Inspect linked records, identify the first abnormal handoff and justify a recovery decision using evidence.",
  success:
    "Restore processing within budget and compare the outcome with the same workload without intervention.",
  nodes: [
    ["intake", "Intake", "investigator"],
    ["review", "Review", "operations"],
    ["processing", "Processing", "operations"],
    ["delivery", "Delivery", "finance"],
    ["completion", "Completion", "operations"],
  ].map(([id, label, role]) => ({ id, label, role, capacity: 5 })),
  edges: [
    ["intake", "review"],
    ["review", "processing"],
    ["processing", "delivery"],
    ["delivery", "completion"],
  ].map(([source, target]) => ({ source, target })),
  incident_node: "review",
  cause: "A synthetic routing fault holds work at the review handoff.",
};

export function SecurityLog({ events = [] }) {
  if (!events.length) return null;
  return (
    <section className="security-log" aria-label="Security screening log">
      <h4>Security review</h4>
      <ol>
        {events.map((event, index) => (
          <li key={index}>
            <strong>{event.stage}</strong> · {event.status}
            {event.total > 0 && <> · {event.total} matches redacted</>}
            <small>
              {new Date(event.timestamp * 1000).toLocaleString()}
              {event.actor && <> · Admin {event.actor}</>}
              {event.document_id && (
                <> · Reference {event.document_id.slice(0, 8)}</>
              )}
            </small>
            {Object.entries(event.entities || {}).map(([type, count]) => (
              <span className="badge" key={type}>
                {type} → &lt;{type}&gt; × {count}
              </span>
            ))}
          </li>
        ))}
      </ol>
      <p className="tiny">
        Local pattern screening; original matches are not logged. Review for
        missed or indirect identifiers. This is not a compliance certification.
      </p>
    </section>
  );
}

export function AuthoringPolicy() {
  const [policy, setPolicy] = useState(null),
    [error, setError] = useState("");
  useEffect(() => {
    api("/authoring/policy")
      .then(setPolicy)
      .catch((e) => setError(e.message));
  }, []);
  return (
    <details className="connection-details">
      <summary>System prompt and safety rules</summary>
      {error && <p role="alert">{error}</p>}
      {policy ? (
        <>
          <p className="tiny">
            Shared server policy for Codex and API backup. Uploaded references
            are untrusted data and cannot override it. The learner uses CPU
            simulation, not this authoring prompt.
          </p>
          <p className="tiny">
            {policy.policy_version} · SHA-256 {policy.sha256.slice(0, 12)}
          </p>
          <pre className="document-text">{policy.system_prompt}</pre>
        </>
      ) : (
        !error && <p>Loading policy…</p>
      )}
    </details>
  );
}
