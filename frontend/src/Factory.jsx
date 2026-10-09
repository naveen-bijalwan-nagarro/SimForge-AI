import React, { useEffect, useRef, useState } from "react";
import {
  Bot,
  Check,
  FileUp,
  Play,
  Plus,
  ShieldCheck,
  Sparkles,
  Trash2,
  Wand2,
  X,
} from "lucide-react";
import { api } from "./client";
import { CyGraph, EChart } from "./viz";
import { CodexConnection } from "./CodexConnection";

const STATUS_COLOR = {
  pending: "#c9cedc",
  running: "#7761db",
  completed: "#35a37b",
  failed: "#e5484d",
  waiting: "#e2a336",
};

function usePoll(fn, active, ms = 900) {
  useEffect(() => {
    if (!active) return;
    let alive = true,
      timer;
    const tick = async () => {
      try {
        await fn();
      } catch {}
      if (alive) timer = setTimeout(tick, ms);
    };
    timer = setTimeout(tick, ms);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [active]);
}

function Checks({ items }) {
  const groups = {};
  items.forEach(
    (c) => (groups[c.category] = [...(groups[c.category] || []), c]),
  );
  return (
    <div className="check-groups">
      {Object.entries(groups).map(([cat, list]) => (
        <div key={cat} className="check-group">
          <h5>
            {cat}{" "}
            <small>
              {list.filter((c) => c.passed).length}/{list.length}
            </small>
          </h5>
          {list.map((c) => (
            <p key={c.name} className={c.passed ? "pass" : "fail"}>
              {c.passed ? "✓" : "×"} {c.name}
              <small>{c.detail}</small>
            </p>
          ))}
        </div>
      ))}
    </div>
  );
}

/* ================================================================== SOP FACTORY */
export function SopFactory({ user }) {
  const [status, setStatus] = useState(null);
  const [sops, setSops] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [name, setName] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [sop, setSop] = useState(null);
  const [objective, setObjective] = useState(
    "Detect the supplier disruption early and protect customer deliveries within budget.",
  );
  const [engine, setEngine] = useState("auto");
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState([]);
  const [comment, setComment] = useState("");
  const refresh = async () => {
    setSops(await api("/factory/sops"));
    setJobs(await api("/factory/jobs"));
  };
  useEffect(() => {
    api("/factory/status")
      .then(setStatus)
      .catch((e) => setError(e.message));
    refresh().catch(() => {});
  }, []);
  usePoll(
    async () => setJob(await api(`/factory/jobs/${job.id}`)),
    job?.status === "running",
    700,
  );
  async function act(fn) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const steps =
    job?.steps ||
    status?.steps?.map((s) => ({ ...s, status: "pending" })) ||
    [];
  const flow = steps.map((s) => s.key);
  const edges = flow
    .slice(0, -1)
    .map((k, i) => ({
      source: k,
      target: flow[i + 1],
      color: "#c9cedc",
      label: "",
    }))
    .filter((e) => e.source !== "repair" && e.target !== "repair");
  edges.push(
    { source: "redteam", target: "repair", color: "#e2a336", label: "fail" },
    {
      source: "repair",
      target: "run_tests",
      color: "#e2a336",
      label: "re-test",
    },
    { source: "redteam", target: "policy", color: "#35a37b", label: "pass" },
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            SIMFORGE AI · FROM SOP TO TESTED SIMULATION
          </span>
          <h1>SOP factory</h1>
          <p>
            Upload a procedure. Personal data is removed first, then a scenario
            engineer (Codex when available) drafts the simulation, generated
            tests and red-team attacks check it, failures are repaired, and a
            policy gate decides. As Admin / Trainer, review and approve the
            result, then publish it from Scenario studio. No separate trainer
            account is required.
          </p>
        </div>
      </div>
      {error && (
        <p className="error-banner">
          {typeof error === "string" ? error : JSON.stringify(error)}
        </p>
      )}
      {status && (
        <div className="stack-strip">
          <span>
            <b>Orchestration</b>
            {status.orchestrator}
          </span>
          <span>
            <b>PII</b>
            {status.pii_engine}
          </span>
          <span>
            <b>Knowledge base</b>
            {status.knowledge_base}
          </span>
          <span>
            <b>Policy</b>
            {status.policy_engine}
          </span>
          <span className={status.codex.ready ? "ok" : ""}>
            <b>Codex</b>
            {status.codex.reason}
          </span>
        </div>
      )}
      <CodexConnection
        admin={user.role === "admin"}
        onChange={(codex) =>
          setStatus((previous) =>
            previous ? { ...previous, codex } : previous,
          )
        }
      />
      <div className="workspace-grid">
        <section className="panel padded">
          <h3>1 · Upload an SOP</h3>
          <label>
            Name
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Supplier disruption SOP v3"
            />
          </label>
          <label>
            Paste text
            <textarea
              rows="8"
              className="code-editor"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste the procedure (markdown or plain text)…"
            />
          </label>
          <label>
            …or a file (.pdf, .docx, .md, .txt)
            <input
              type="file"
              accept=".pdf,.docx,.md,.txt"
              onChange={(e) => setFile(e.target.files[0] || null)}
            />
          </label>
          <div className="actions">
            <button
              className="secondary"
              onClick={() =>
                act(async () => {
                  const d = await api("/factory/demo");
                  setName(d.name);
                  setText(d.text);
                  setFile(null);
                })
              }
            >
              Load demo SOP
            </button>
            <button
              className="primary"
              disabled={busy || !name || (!text && !file)}
              onClick={() =>
                act(async () => {
                  let body = { name, text };
                  if (file) {
                    if (file.size > 650000)
                      throw new Error("File limit is 650 KB");
                    const b64 = await new Promise((res, rej) => {
                      const r = new FileReader();
                      r.onload = () => res(String(r.result).split(",")[1]);
                      r.onerror = rej;
                      r.readAsDataURL(file);
                    });
                    body = { name, file_b64: b64, filename: file.name };
                  }
                  const r = await api("/factory/sops", body);
                  setSop(r);
                  setText("");
                  setFile(null);
                  await refresh();
                })
              }
            >
              <FileUp size={15} /> Sanitize & index
            </button>
          </div>
          {sop && (
            <div className="callout">
              <ShieldCheck size={18} />
              <div>
                <strong>
                  {sop.findings.total} personal-data entities removed before
                  storage
                </strong>
                <p className="tiny">
                  {Object.entries(sop.findings.entities)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join(" · ") || "none"}{" "}
                  · {sop.findings.engine}. Only the sanitized text is stored or
                  sent to any model.
                </p>
              </div>
            </div>
          )}
          {sop?.preview && <pre className="sop-preview">{sop.preview}</pre>}
          {sops.length > 0 && (
            <>
              <h4>Uploaded SOPs</h4>
              <div className="chips">
                {sops.map((s) => (
                  <button
                    key={s.id}
                    className={sop?.id === s.id ? "chip active" : "chip"}
                    onClick={() =>
                      act(async () => {
                        const r = await api(`/factory/sops/${s.id}`);
                        setSop({ ...r, preview: r.text.slice(0, 1500) });
                      })
                    }
                  >
                    {s.name}
                  </button>
                ))}
              </div>
            </>
          )}
          {sop && (
            <div className="kb-search">
              <label>
                Search the knowledge base
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="e.g. escalation threshold"
                />
              </label>
              <button
                className="secondary"
                disabled={!query}
                onClick={() =>
                  act(async () =>
                    setHits(
                      await api(
                        `/factory/sops/${sop.id}/search?q=${encodeURIComponent(query)}`,
                      ),
                    ),
                  )
                }
              >
                Search
              </button>
              {hits.map((h) => (
                <p key={h.ord} className="hit">
                  <small>
                    chunk {h.ord} · score {h.score}
                  </small>
                  {h.text.slice(0, 260)}…
                </p>
              ))}
            </div>
          )}
        </section>
        <section className="panel padded">
          <h3>2 · Generate, test & repair</h3>
          <label>
            Learning objective
            <textarea
              rows="2"
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
            />
          </label>
          <label>
            Scenario engineer
            <select value={engine} onChange={(e) => setEngine(e.target.value)}>
              <option value="auto">
                Auto (Codex if signed in, else built-in)
              </option>
              <option value="codex">Codex (falls back if unavailable)</option>
              <option value="builtin">Built-in (offline, deterministic)</option>
            </select>
          </label>
          <button
            className="primary full"
            disabled={busy || !sop || job?.status === "running"}
            onClick={() =>
              act(async () => {
                const r = await api("/factory/jobs", {
                  sop_id: sop.id,
                  objective,
                  engine,
                });
                setJob({ id: r.id, status: "running" });
              })
            }
          >
            <Play size={15} /> Run the pipeline
          </button>
          <CyGraph
            height={560}
            rankDir="TB"
            label="Pipeline graph"
            nodes={steps.map((s) => ({
              id: s.key,
              label: s.label + (s.runs > 1 ? ` ×${s.runs}` : ""),
              color: STATUS_COLOR[s.status] || "#c9cedc",
              size: s.status === "running" ? 34 : 24,
            }))}
            edges={edges}
          />
          <div className="step-list">
            {steps.map((s) => (
              <p key={s.key} className={"step-line " + s.status}>
                <i
                  className="dot"
                  style={{ background: STATUS_COLOR[s.status] }}
                />{" "}
                <strong>{s.label}</strong>{" "}
                <small>{s.detail || s.description}</small>
              </p>
            ))}
          </div>
          {jobs.length > 0 && (
            <details>
              <summary>Previous runs ({jobs.length})</summary>
              {jobs.map((j) => (
                <button
                  key={j.id}
                  className="list-row"
                  onClick={() =>
                    act(async () => setJob(await api(`/factory/jobs/${j.id}`)))
                  }
                >
                  <div>
                    <strong>{j.title || "Untitled"}</strong>
                    <small>
                      {j.status} ·{" "}
                      {j.totals
                        ? `${j.totals.passed}/${j.totals.total} checks`
                        : ""}
                    </small>
                  </div>
                </button>
              ))}
            </details>
          )}
        </section>
      </div>
      {job && job.status !== "running" && (
        <JobResult
          job={job}
          setJob={setJob}
          user={user}
          comment={comment}
          setComment={setComment}
          act={act}
          busy={busy}
        />
      )}
    </>
  );
}

function JobResult({ job, setJob, comment, setComment, act, busy }) {
  if (job.status === "failed")
    return <p className="error-banner">Pipeline failed: {job.error}</p>;
  const history = job.history || [];
  return (
    <>
      <section className="panel padded">
        <div className="panel-heading">
          <div>
            <h3>3 · Results: {job.spec_summary?.title}</h3>
            <p>
              {job.totals?.passed}/{job.totals?.total} checks passed after{" "}
              {Math.max(0, history.length - 1)} repair iteration(s) · engine:{" "}
              {job.engine_used}
            </p>
          </div>
          <a
            className="secondary"
            href={`/api/factory/jobs/${job.id}/promptfoo`}
          >
            Export Promptfoo suite
          </a>
        </div>
        {job.trace?.length > 0 && (
          <p className="callout">
            <Bot size={16} /> {job.trace.join(" ")}
          </p>
        )}
        <div className="grid-2">
          <EChart
            height={220}
            label="Checks passed per iteration"
            option={{
              tooltip: {},
              xAxis: {
                type: "category",
                data: history.map((h) => `iteration ${h.iteration}`),
              },
              yAxis: { type: "value" },
              series: [
                {
                  type: "bar",
                  name: "passed",
                  stack: "t",
                  data: history.map((h) => h.passed),
                  itemStyle: { color: "#35a37b" },
                },
                {
                  type: "bar",
                  name: "failed",
                  stack: "t",
                  data: history.map((h) => h.total - h.passed),
                  itemStyle: { color: "#e5484d" },
                },
              ],
            }}
          />
          <div>
            <h4>Repairs</h4>
            <ul className="critic">
              {(job.changes || []).map((c, i) => (
                <li key={i}>
                  iteration {c.iteration}: {c.change}
                </li>
              ))}
            </ul>
            {job.quarantined?.length > 0 && (
              <>
                <h4>Quarantined untrusted SOP lines</h4>
                <ul className="critic">
                  {job.quarantined.map((q) => (
                    <li key={q}>
                      <code>{q}</code>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        </div>
        <h4>Generated tests & red-team attacks</h4>
        <Checks items={[...(job.tests || []), ...(job.redteam || [])]} />
      </section>
      <div className="workspace-grid">
        <section className="panel padded">
          <h3>Generated simulation</h3>
          {job.spec_summary && (
            <CyGraph
              height={300}
              label="Generated world"
              nodes={job.spec_summary.nodes.map((n) => ({
                id: n.id,
                label: `${n.label}\n(${n.role})`,
                color: "#7761db",
                size: 22,
              }))}
              edges={job.spec_summary.edges.map((e) => ({
                ...e,
                color: "#b8bfd3",
                label: "",
              }))}
            />
          )}
          <ul className="critic">
            {(job.spec_summary?.actions || []).map((a) => (
              <li key={a.label}>
                {a.effect}: {a.label} · {a.cost} units
              </li>
            ))}
          </ul>
          <details>
            <summary>Scenario pack (YAML)</summary>
            <pre className="log-lines">{job.pack_yaml}</pre>
          </details>
        </section>
        <section className="panel padded">
          <h3>4 · Policy gate & human review</h3>
          <p className="tiny">{job.policy?.engine}</p>
          {job.policy?.deny?.length ? (
            <ul className="critic">
              {job.policy.deny.map((d) => (
                <li key={d}>{d}</li>
              ))}
            </ul>
          ) : (
            <p className="pass">✓ Policy allows publication</p>
          )}
          {job.status === "awaiting_approval" ? (
            <>
              <label>
                Review comment
                <textarea
                  rows="2"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="What did you verify against the SOP?"
                />
              </label>
              <div className="actions">
                <button
                  className="primary"
                  disabled={busy}
                  onClick={() =>
                    act(async () =>
                      setJob(
                        await api(`/factory/jobs/${job.id}/approve`, {
                          comment,
                        }),
                      ),
                    )
                  }
                >
                  <Check size={15} /> Approve for publication
                </button>
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() =>
                    act(async () =>
                      setJob(
                        await api(`/factory/jobs/${job.id}/reject`, {
                          comment,
                        }),
                      ),
                    )
                  }
                >
                  <X size={15} /> Reject
                </button>
              </div>
            </>
          ) : (
            <p className="callout">
              {job.status === "approved"
                ? "Approved. Open Scenario studio → Review & publish to publish this exercise and notify learners."
                : job.status === "rejected"
                  ? "Rejected by the reviewer."
                  : `Status: ${job.status}`}
            </p>
          )}
        </section>
      </div>
    </>
  );
}

/* ================================================================== CODEX SANDBOX */
export function CodexSandbox() {
  const [guide, setGuide] = useState(null);
  const [status, setStatus] = useState(null);
  const [answers, setAnswers] = useState(null);
  const [preview, setPreview] = useState(null);
  const [job, setJob] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const logRef = useRef(null);
  useEffect(() => {
    api("/codex/sandbox/guide")
      .then((g) => {
        setGuide(g);
        setAnswers(g.example);
      })
      .catch((e) => setError(e.message));
    api("/codex/sandbox/jobs")
      .then(setJobs)
      .catch(() => {});
  }, []);
  usePoll(
    async () => setJob(await api(`/codex/sandbox/jobs/${job.id}`)),
    job?.status === "running",
    1500,
  );
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [job?.events?.length]);
  async function act(fn) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (!guide || !answers)
    return <p className="muted">{error || "Loading the sandbox…"}</p>;
  const set = (k, v) => setAnswers({ ...answers, [k]: v });
  const stages = answers.stages || [];
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">ADMINISTRATOR · CODEX SANDBOX</span>
          <h1>Create a new use case with Codex</h1>
          <p>
            Describe a world — from a Minecraft-style block village to a mock
            banking app — and Codex drafts, validates and tests a scenario pack
            through the SimForge MCP tools in an isolated workspace. The guided
            builder produces the same pack offline. Drafts always need your
            review before publishing.
          </p>
        </div>
      </div>
      {error && <p className="error-banner">{error}</p>}
      <CodexConnection onChange={setStatus} />
      <div className="stack-strip">
        <span className={status?.installed ? "ok" : ""}>
          <b>Codex CLI</b>
          {status?.installed ? status.version : "not installed"}
        </span>
        <span className={status?.authenticated ? "ok" : ""}>
          <b>Sign-in</b>
          {status?.authenticated
            ? "signed in"
            : status?.authenticated === false
              ? "not signed in"
              : "unknown"}
        </span>
        <span className="ok">
          <b>MCP server</b>simforge (13 tools)
        </span>
        <span>
          <b>Workspace</b>isolated per job · workspace-write
        </span>
      </div>
      <div className="workspace-grid">
        <section className="panel padded wizard">
          {guide.steps.map((s) => (
            <details
              key={s.key}
              open={["basics", "stages", "incident"].includes(s.key)}
            >
              <summary>
                <strong>{s.title}</strong> <small>{s.help}</small>
              </summary>
              {s.key === "basics" && (
                <div className="form-grid">
                  <label>
                    Title
                    <input
                      value={answers.title || ""}
                      onChange={(e) => set("title", e.target.value)}
                    />
                  </label>
                  <label>
                    Category
                    <input
                      value={answers.category || ""}
                      onChange={(e) => set("category", e.target.value)}
                    />
                  </label>
                  <label>
                    Visual style
                    <select
                      value={answers.style || "workflow"}
                      onChange={(e) => set("style", e.target.value)}
                    >
                      {guide.styles.map((x) => (
                        <option key={x}>{x}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Learner role
                    <input
                      value={answers.learner_role || ""}
                      onChange={(e) => set("learner_role", e.target.value)}
                    />
                  </label>
                </div>
              )}
              {s.key === "flow" && (
                <div className="form-grid">
                  <label>
                    Unit of work
                    <input
                      value={answers.unit || ""}
                      onChange={(e) => set("unit", e.target.value)}
                    />
                  </label>
                  <label>
                    Impact measure
                    <input
                      value={answers.impact || ""}
                      onChange={(e) => set("impact", e.target.value)}
                    />
                  </label>
                </div>
              )}
              {s.key === "stages" && (
                <>
                  {stages.map((st, i) => (
                    <div className="column-row" key={i}>
                      <input
                        aria-label={`Stage ${i + 1} label`}
                        value={st.label}
                        onChange={(e) =>
                          set(
                            "stages",
                            stages.map((x, j) =>
                              j === i ? { ...x, label: e.target.value } : x,
                            ),
                          )
                        }
                      />
                      <select
                        aria-label={`Stage ${i + 1} role`}
                        value={st.role}
                        onChange={(e) =>
                          set(
                            "stages",
                            stages.map((x, j) =>
                              j === i ? { ...x, role: e.target.value } : x,
                            ),
                          )
                        }
                      >
                        {guide.roles.map((r) => (
                          <option key={r}>{r}</option>
                        ))}
                      </select>
                      <select
                        aria-label={`Stage ${i + 1} evidence`}
                        value={st.modality}
                        onChange={(e) =>
                          set(
                            "stages",
                            stages.map((x, j) =>
                              j === i ? { ...x, modality: e.target.value } : x,
                            ),
                          )
                        }
                      >
                        {guide.modalities.map((r) => (
                          <option key={r}>{r}</option>
                        ))}
                      </select>
                      <button
                        className="secondary"
                        aria-label="Remove stage"
                        onClick={() =>
                          set(
                            "stages",
                            stages.filter((_, j) => j !== i),
                          )
                        }
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                  <button
                    className="secondary"
                    onClick={() =>
                      set("stages", [
                        ...stages,
                        {
                          label: "New stage",
                          role: "operations",
                          modality: "log",
                        },
                      ])
                    }
                  >
                    <Plus size={14} /> Add stage
                  </button>
                </>
              )}
              {s.key === "incident" && (
                <>
                  <label>
                    Hidden root cause
                    <textarea
                      rows="2"
                      value={answers.root_cause || ""}
                      onChange={(e) => set("root_cause", e.target.value)}
                    />
                  </label>
                  <label>
                    First observable signal
                    <input
                      value={answers.signal || ""}
                      onChange={(e) => set("signal", e.target.value)}
                    />
                  </label>
                </>
              )}
              {s.key === "responses" && (
                <>
                  {(answers.responses || []).map((r, i) => (
                    <div className="column-row" key={i}>
                      <input
                        aria-label={`Response ${i + 1}`}
                        value={r.label}
                        onChange={(e) =>
                          set(
                            "responses",
                            answers.responses.map((x, j) =>
                              j === i ? { ...x, label: e.target.value } : x,
                            ),
                          )
                        }
                      />
                      <select
                        aria-label={`Response ${i + 1} stage`}
                        value={r.stage}
                        onChange={(e) =>
                          set(
                            "responses",
                            answers.responses.map((x, j) =>
                              j === i
                                ? { ...x, stage: Number(e.target.value) }
                                : x,
                            ),
                          )
                        }
                      >
                        {stages.map((st, k) => (
                          <option key={k} value={k}>
                            {st.label}
                          </option>
                        ))}
                      </select>
                      <select
                        aria-label={`Response ${i + 1} effect`}
                        value={r.effect}
                        onChange={(e) =>
                          set(
                            "responses",
                            answers.responses.map((x, j) =>
                              j === i ? { ...x, effect: e.target.value } : x,
                            ),
                          )
                        }
                      >
                        {guide.effects.map((x) => (
                          <option key={x}>{x}</option>
                        ))}
                      </select>
                      <button
                        className="secondary"
                        aria-label="Remove response"
                        onClick={() =>
                          set(
                            "responses",
                            answers.responses.filter((_, j) => j !== i),
                          )
                        }
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                  <button
                    className="secondary"
                    onClick={() =>
                      set("responses", [
                        ...(answers.responses || []),
                        { label: "New response", stage: 0, effect: "reroute" },
                      ])
                    }
                  >
                    <Plus size={14} /> Add response
                  </button>
                </>
              )}
              {s.key === "links" && (
                <div className="form-grid">
                  <label>
                    Distractor explanations (one per line)
                    <textarea
                      rows="3"
                      value={(answers.decoys || []).join("\n")}
                      onChange={(e) =>
                        set("decoys", e.target.value.split("\n"))
                      }
                    />
                  </label>
                  <label>
                    Success measures (one per line)
                    <textarea
                      rows="3"
                      value={(answers.objectives || []).join("\n")}
                      onChange={(e) =>
                        set("objectives", e.target.value.split("\n"))
                      }
                    />
                  </label>
                  <label>
                    Emits signal (optional)
                    <input
                      value={answers.emits || ""}
                      onChange={(e) => set("emits", e.target.value)}
                      placeholder="e.g. delayed_shipments"
                    />
                  </label>
                  <label>
                    Consumes signal (optional)
                    <input
                      value={answers.consumes || ""}
                      onChange={(e) => set("consumes", e.target.value)}
                      placeholder="e.g. blackout"
                    />
                  </label>
                </div>
              )}
            </details>
          ))}
          <div className="actions">
            <button
              className="secondary"
              onClick={() => setAnswers(guide.example)}
            >
              <Sparkles size={14} /> Load Minecraft-style example
            </button>
            <button
              className="secondary"
              disabled={busy}
              onClick={() =>
                act(async () =>
                  setPreview(await api("/codex/sandbox/preview", { answers })),
                )
              }
            >
              <Wand2 size={14} /> Preview (guided, instant)
            </button>
            <button
              className="primary"
              disabled={busy || job?.status === "running"}
              onClick={() =>
                act(async () => {
                  const r = await api("/codex/sandbox/jobs", {
                    answers,
                    mode: "auto",
                  });
                  setJob({ id: r.id, status: "running", events: [] });
                })
              }
            >
              <Bot size={14} /> Generate with Codex
            </button>
          </div>
        </section>
        <section className="panel padded">
          <h3>Codex activity</h3>
          {!job && (
            <p className="muted">
              Start a job to watch Codex call the SimForge MCP tools, write the
              pack and run the tests. If Codex is unavailable the guided builder
              is used and the reason is recorded.
            </p>
          )}
          {job && (
            <>
              <p>
                <span className="badge">{job.status}</span>{" "}
                {job.source && (
                  <span className="badge purple">{job.source}</span>
                )}
              </p>
              <div className="codex-log" ref={logRef} aria-live="polite">
                {(job.events || [])
                  .filter((e) => e.text)
                  .map((e, i) => (
                    <p key={i}>
                      <small>{e.kind}</small> {e.text}
                    </p>
                  ))}
              </div>
              {job.trace?.length > 0 && (
                <p className="tiny">{job.trace.join(" ")}</p>
              )}
              {job.checks && <Checks items={job.checks} />}
              {job.draft_id && (
                <p className="callout">
                  <Check size={16} /> Draft saved. Publish it from{" "}
                  <strong>Scenario studio → Review and publish</strong>;
                  learners are notified automatically.
                </p>
              )}
              {job.pack_yaml && (
                <details>
                  <summary>Generated pack (YAML)</summary>
                  <pre className="log-lines">{job.pack_yaml}</pre>
                </details>
              )}
            </>
          )}
          {preview && (
            <>
              <h4>Guided preview</h4>
              <Checks items={preview.checks} />
              <details>
                <summary>Pack YAML</summary>
                <pre className="log-lines">{preview.yaml}</pre>
              </details>
            </>
          )}
          <h4>Finish in the admin panel</h4>
          <p className="tiny">
            The wizard, Codex/MCP activity, tests and generated YAML are
            available here. Review and publish the result in{" "}
            <a href="#/designer/review">Review & publish</a>. No terminal
            commands are required.
          </p>
          {jobs.length > 0 && (
            <details>
              <summary>Previous jobs ({jobs.length})</summary>
              {jobs.map((j) => (
                <p key={j.id} className="tiny">
                  {j.title} · {j.status} · {j.source}
                </p>
              ))}
            </details>
          )}
        </section>
      </div>
    </>
  );
}
