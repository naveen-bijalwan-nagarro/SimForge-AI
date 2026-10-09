import React, { useEffect, useState } from "react";
import { ArrowRight, ClipboardCheck } from "lucide-react";
import { api } from "./client";
import { AdminStudio, TrainingDesk } from "./Experience";

const roles = {
  admin: {
    title: "Create safe practice. Publish with confidence.",
    purpose:
      "You are the scenario creator and trainer: create a draft, inspect its checks, publish it, assign it and observe results. You do not need a separate trainer account.",
    action: "Create a scenario",
    destination: "designer",
    tab: "create",
  },
  learner: {
    title: "Practise real decisions. Without real-world risk.",
    purpose:
      "You work with linked synthetic records, investigate an unfolding incident, choose a response and explain the result. No live business system is connected.",
    action: "Run a scenario",
    destination: "catalog",
  },
};

export function RoleHome({
  user,
  overview,
  scenarios,
  onNavigate,
  onScenario,
}) {
  const role = roles[user.role];
  const [facts, setFacts] = useState(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    const paths =
      user.role === "admin" ? ["/scenario-drafts"] : ["/assignments"];
    Promise.all(paths.map((path) => api(path)))
      .then((data) => {
        if (!active) return;
        setFacts(
          user.role === "admin"
            ? { drafts: data[0] }
            : { assignments: data[0] },
        );
        setError("");
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [user.id, user.role, retry]);
  const supplier =
    scenarios.find((s) => s.key === "supply_chain") ||
    scenarios.find((s) => s.key === "supplier_risk");
  const pending = facts?.drafts?.filter((d) => d.status !== "published").length;
  const ready = facts?.drafts?.filter(
    (d) => d.status !== "published" && d.checks.every((c) => c.passed),
  ).length;
  return (
    <>
      <section className="mission-home" aria-label="Your next step">
        <span className="eyebrow">SIMFORGE AI · SAFE BUSINESS PRACTICE</span>
        <h1>{role.title}</h1>
        <p>{role.purpose}</p>
        <div className="actions">
          <button
            className="primary"
            onClick={() => onNavigate(role.destination, role.tab)}
          >
            {role.action}
            <ArrowRight size={17} />
          </button>
          <button
            className="secondary"
            onClick={() =>
              onNavigate(user.role === "admin" ? "catalog" : "assignments")
            }
          >
            {user.role === "admin"
              ? "Browse scenario library"
              : "View my training"}
          </button>
        </div>
      </section>
      <section
        className="journey-strip"
        aria-label="How the two roles work together"
      >
        {[
          [
            "Admin / Trainer",
            "Create a scenario",
            "Draft the workflow, hidden incident and permitted responses.",
          ],
          [
            "Admin / Trainer",
            "Validate and publish",
            "Inspect checks and learning goals; publish and notify learners.",
          ],
          [
            "Learner",
            "Investigate and decide",
            "Inspect mock data, respond to the incident and explain the outcome.",
          ],
          [
            "Learner",
            "Learn from the result",
            "Compare with no intervention and justify the decisions you made.",
          ],
        ].map(([who, title, detail], index) => (
          <article
            key={title}
            className={
              (who === "Learner") === (user.role === "learner")
                ? "current-role"
                : ""
            }
          >
            <small>
              {index + 1} · {who}
            </small>
            <strong>{title}</strong>
            <p>{detail}</p>
          </article>
        ))}
      </section>
      {error && (
        <p className="error-banner" role="alert">
          Workspace summary: {error}{" "}
          <button className="secondary" onClick={() => setRetry((x) => x + 1)}>
            Try again
          </button>
        </p>
      )}
      <div className="focus-stats">
        <article>
          <small>
            {user.role === "admin" ? "Unpublished drafts" : "My assignments"}
          </small>
          <strong>
            {user.role === "admin"
              ? (pending ?? "…")
              : (facts?.assignments?.length ?? "…")}
          </strong>
        </article>
        <article>
          <small>
            {user.role === "admin"
              ? "Drafts passing checks"
              : "Simulation runs"}
          </small>
          <strong>
            {user.role === "admin" ? (ready ?? "…") : (overview?.runs ?? "…")}
          </strong>
        </article>
        <article>
          <small>Business & data exercises</small>
          <strong>{overview?.scenarios ?? "…"}</strong>
        </article>
      </div>
      <div className="focus-grid">
        <section className="panel padded flagship">
          <span className="eyebrow">FEATURED BUSINESS EXERCISE</span>
          <h2>A supplier stops dispatching. What do you do next?</h2>
          <p>
            Trace the impact through inventory, logistics, production and
            customer delivery. Identify the first failing system, choose a
            response and compare with the same workload without intervention.
          </p>
          <ol>
            <li>Inspect an affected order and its evidence.</li>
            <li>Explain the cause before committing a response.</li>
            <li>Measure recovery, delays and synthetic impact.</li>
          </ol>
          <button
            className="primary"
            disabled={!supplier}
            onClick={() => onScenario(supplier)}
          >
            Explore supplier disruption
            <ArrowRight size={16} />
          </button>
        </section>
        <section
          className="panel padded"
          aria-label="What is real and what is simulated"
        >
          <h2>Explainable by design</h2>
          <p>
            <b>Codex authors a draft.</b> Python generates linked mock data and
            executes the scenario. The result must pass checks and human review.
          </p>
          <p>
            <b>Your actions have visible consequences.</b> Costs, delays, queues
            and recovery are calculated from the same reproducible workload.
          </p>
          <p>
            <b>The boundary is explicit.</b> These are training simulations, not
            production-system replicas or validated physical twins. Simulated
            savings are not proven customer savings.
          </p>
          <details>
            <summary>Four-minute presentation route</summary>
            <p>
              Explain the need → admin creates and checks a scenario → admin
              publishes → learner opens the notification, investigates and acts
              → compare outcomes. Assignments and coaching are optional.
            </p>
            <p>
              Use separate browser profiles for admin and learner. Clearly
              identify any pre-generated draft used as a latency fallback.
            </p>
          </details>
        </section>
      </div>
    </>
  );
}

export function ScenarioReviews({ user, onPublished }) {
  const [drafts, setDrafts] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(null);
  const [message, setMessage] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true,
      timer;
    const poll = async () => {
      try {
        const rows = await api("/scenario-drafts");
        if (active) {
          setDrafts(rows);
          setError("");
        }
      } catch (e) {
        if (active) setError(e.message);
      } finally {
        if (active) {
          setLoading(false);
          timer = setTimeout(poll, 4000);
        }
      }
    };
    poll();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [user.id, retry]);
  async function act(draft) {
    setBusy(draft.id);
    setError("");
    setMessage("");
    try {
      const published = await api(`/scenario-drafts/${draft.id}/publish`, {});
      await onPublished?.(published);
      setMessage("Scenario published. Learners have been notified.");
      setDrafts(await api("/scenario-drafts"));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  }
  return (
    <section className="panel padded" aria-label="Scenario publication queue">
      <div className="panel-heading">
        <div>
          <h2>2 · Check and publish</h2>
          <p>
            As Admin / Trainer, inspect the learning mission, permitted
            responses and validation checks, then publish. A separate trainer
            approval is not required. Learners are notified automatically.
          </p>
        </div>
        <ClipboardCheck size={23} />
      </div>
      {loading && <p role="status">Loading scenario reviews…</p>}
      {error && (
        <p className="error-banner" role="alert">
          {error}
          <button className="secondary" onClick={() => setRetry((x) => x + 1)}>
            Refresh reviews
          </button>
        </p>
      )}
      {message && (
        <p className="success-note" role="status">
          {message}
        </p>
      )}
      {!loading && !error && !drafts.length && (
        <p>
          No drafts yet. Create an exercise above, inspect its checks, then
          publish it to learners.
        </p>
      )}
      {drafts.map((draft) => {
        const passed = draft.checks.filter((c) => c.passed).length;
        return (
          <article className="draft-review" key={draft.id}>
            <div>
              <h3>{draft.definition.title}</h3>
              <span className="badge">
                {draft.source} ·{" "}
                {draft.status === "published"
                  ? "published"
                  : "draft for admin review"}
              </span>
            </div>
            <p>
              <b>Learning mission:</b> {draft.definition.mission}
            </p>
            <p className="tiny">
              Author: {draft.owner} · Version {draft.version} · {passed}/
              {draft.checks.length} scenario checks passed
            </p>
            <details>
              <summary>Inspect workflow and validation checks</summary>
              {draft.definition.nodes && (
                <p>{draft.definition.nodes.map((n) => n.label).join(" → ")}</p>
              )}
              <div className="validation-checks">
                {draft.checks.map((c) => (
                  <span key={c.name} className={c.passed ? "pass" : "fail"}>
                    {c.passed ? "✓" : "×"} {c.name}
                    <small>{c.detail}</small>
                  </span>
                ))}
              </div>
              {draft.pack_yaml && (
                <pre className="log-lines">{draft.pack_yaml}</pre>
              )}
            </details>
            {draft.approved_by && (
              <p>
                <b>SOP reviewer:</b> {draft.approved_by} —{" "}
                {draft.review_comment}
              </p>
            )}
            {user.role === "admin" && (
              <button
                className="primary"
                disabled={
                  busy !== null ||
                  passed !== draft.checks.length ||
                  draft.status === "published"
                }
                onClick={() => act(draft)}
              >
                {draft.status === "published"
                  ? "Published"
                  : "Publish & notify learners"}
              </button>
            )}
          </article>
        );
      })}
    </section>
  );
}

export function ScenarioStudio({ user, Graph, onPublished }) {
  const [revision, setRevision] = useState(0);
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">ADMIN / TRAINER · SCENARIO LAB</span>
          <h1>Scenario Lab</h1>
          <p>
            Create, validate and publish scenarios in one place. Learners
            receive the published exercise; you can assign it and observe their
            results without a separate trainer account.
          </p>
        </div>
      </div>
      <AdminStudio
        Graph={Graph}
        compact
        showReview={false}
        onDraftReady={() => setRevision((x) => x + 1)}
      />
      <ScenarioReviews key={revision} user={user} onPublished={onPublished} />
    </>
  );
}

export function CoachingWorkspace({ user, scenarios, onOpen, onRun }) {
  return (
    <TrainingDesk
      user={user}
      scenarios={scenarios}
      onOpen={onOpen}
      onRun={onRun}
    />
  );
}
