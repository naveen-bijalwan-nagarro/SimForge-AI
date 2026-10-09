import React, { useEffect, useState } from "react";
import { SecurityLog } from "./AuthoringSecurity";
import { ScenarioCleanup } from "./ScenarioInputs";
import { ArrowRight, ClipboardCheck } from "lucide-react";
import { api } from "./client";
import { AdminStudio, TrainingDesk } from "./Experience";

const roles = {
  admin: {
    title: "Training management",
    purpose:
      "Create exercises, publish to learners and review learning evidence.",
    action: "Create a scenario",
    destination: "designer",
    tab: "create",
  },
  learner: {
    title: "My learning workspace",
    purpose:
      "Practise decisions with synthetic records. No live business systems are connected.",
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
    scenarios.find(
      (s) => /supplier disruption/i.test(s.title) && s.key !== "supply_chain",
    ) ||
    scenarios.find((s) => s.key === "supply_chain") ||
    scenarios.find((s) => s.key === "supplier_risk");
  const pending = facts?.drafts?.filter((d) => d.status !== "published").length;
  const ready = facts?.drafts?.filter(
    (d) => d.status !== "published" && d.checks.every((c) => c.passed),
  ).length;
  return (
    <>
      <section className="mission-home" aria-label="Your next step">
        <span className="eyebrow">SIMFORGE AI</span>
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
          <h2>Supplier disruption</h2>
          <p>
            Trace delayed orders, investigate the failing handoff and compare
            your response with the same workload without intervention.
          </p>
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
          <h2>Learning evidence</h2>
          <p>
            Take a quick knowledge check, practise the scenario and see
            objective feedback from your answers, diagnosis and actions.
          </p>
          <p>
            Simulation outcomes and learning-check results are reported
            separately.
          </p>
          <details>
            <summary>Training boundaries</summary>
            <p>
              Costs and impact are synthetic, not proven customer savings. A
              short practice check does not establish job competence.
            </p>
            <p>
              Codex drafts definitions; Python runs the simulation without a
              model. Use separate browser profiles for simultaneous admin and
              learner sessions.
            </p>
          </details>
        </section>
      </div>
    </>
  );
}

export function ScenarioReviews({ user, onPublished, onEdit }) {
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
            Review the mission, references and checks. Publishing notifies
            learners.
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
            {draft.governance && (
              <p className="tiny">
                Privacy policy {draft.governance.policy_version} · brief
                redactions {draft.governance.input_privacy?.total || 0} ·
                generated-text redactions{" "}
                {draft.governance.output_privacy?.total || 0}.{" "}
                {draft.edited_by
                  ? "Administrator revised this draft; source provenance retained."
                  : "Human review required before publication."}
              </p>
            )}
            <SecurityLog events={draft.governance?.events} />
            {draft.documents?.length > 0 && (
              <details>
                <summary>
                  Reference provenance ({draft.documents.length} documents)
                </summary>
                {draft.documents.map((d) => (
                  <p key={d.id}>
                    {d.name} · SHA-256 {d.sha256.slice(0, 12)} ·{" "}
                    {d.truncated ? "excerpted" : "complete extracted text"}
                  </p>
                ))}
              </details>
            )}
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
              <>
                {draft.definition.nodes && (
                  <button
                    className="secondary"
                    disabled={busy !== null}
                    onClick={() => onEdit(draft)}
                  >
                    Edit and revalidate
                  </button>
                )}
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
              </>
            )}
          </article>
        );
      })}
    </section>
  );
}

export function ScenarioStudio({ user, Graph, onPublished }) {
  const [revision, setRevision] = useState(0);
  const [cleanupRevision, setCleanupRevision] = useState(0);
  const [editingDraft, setEditingDraft] = useState(null);
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">ADMIN / TRAINER · SCENARIO LAB</span>
          <h1>Scenario Lab</h1>
          <p>Draft an exercise, review the checks and publish to learners.</p>
        </div>
      </div>
      <AdminStudio
        key={cleanupRevision}
        Graph={Graph}
        compact
        showReview={false}
        editingDraft={editingDraft}
        onDraftReady={() => setRevision((x) => x + 1)}
      />
      <ScenarioReviews
        key={revision}
        user={user}
        onPublished={onPublished}
        onEdit={(draft) => setEditingDraft({ ...draft })}
      />
      <ScenarioCleanup
        onChanged={async () => {
          setRevision((x) => x + 1);
          setCleanupRevision((x) => x + 1);
          await onPublished?.();
        }}
      />
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
