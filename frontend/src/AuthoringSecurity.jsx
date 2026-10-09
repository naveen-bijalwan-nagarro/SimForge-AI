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

export function SecurityLog({ events = [], documents = [] }) {
  if (!events.length) return null;
  const documentNames = new Map(
    (documents || []).filter((document) => document?.id).map((document) => [
      document.id,
      document.name,
    ]),
  );
  return (
    <section className="security-log" aria-label="Security screening log">
      <h4>Security review</h4>
      <ol>
        {events.map((event, index) => {
          const screened = /\bscreened\b/i.test(event.stage || "");
          const total = event.total || 0;
          return (
            <li key={index}>
              <strong>{event.stage}</strong> · {event.status}
              {screened && (
                <>
                  {" "}· {total > 0
                    ? `${total} recognized match${total === 1 ? "" : "es"} redacted`
                    : "no recognized matches"}
                </>
              )}
              <small>
                {Number.isFinite(event.timestamp) &&
                  new Date(event.timestamp * 1000).toLocaleString()}
                {event.actor && <> · Admin {event.actor}</>}
                {event.document_id && (
                  <>
                    {" "}· Reference {documentNames.get(event.document_id) || event.document_id.slice(0, 8)}
                  </>
                )}
                {screened && event.engine && <> · Detector: {event.engine}</>}
              </small>
              {screened &&
                Object.entries(event.entities || {}).map(([type, count]) => (
                  <span className="badge" key={type}>
                    {type} → &lt;{type}&gt; × {count}
                  </span>
                ))}
            </li>
          );
        })}
      </ol>
      <p className="tiny">
        Local pattern screening covers extracted text, reviewed image
        descriptions, the brief and generated text. Image pixels and scanned
        pages are not checked. These receipts contain no matched values; review
        for missed or indirect identifiers. Zero matches does not mean PII-free.
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
