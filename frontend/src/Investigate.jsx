import React, { Suspense, lazy, useEffect, useMemo, useState } from "react";
import {
  Boxes,
  Brain,
  Download,
  FileText,
  Image as ImageIcon,
  Link2,
  Mail,
  Map as MapIcon,
  MessageSquare,
  Radar,
  Receipt,
  ScrollText,
  Share2,
  Ticket,
  Users,
  Activity,
  Gauge,
  Video,
} from "lucide-react";
import { api } from "./client";
import { CyGraph, EChart, healthColor, lineOption } from "./viz";

// WebGL (Three.js / deck.gl) loads only when a 3D or population view opens.
const World3D = lazy(() =>
  import("./viz3d").then((m) => ({ default: m.World3D })),
);
const PopulationDeck = lazy(() =>
  import("./viz3d").then((m) => ({ default: m.PopulationDeck })),
);
const GL = ({ children }) => (
  <Suspense fallback={<p className="muted padded">Starting WebGL…</p>}>
    {children}
  </Suspense>
);

const MODALITY_ICON = {
  log: ScrollText,
  email: Mail,
  sensor: Activity,
  image: ImageIcon,
  video: Video,
  map: MapIcon,
  ticket: Ticket,
  document: FileText,
  transaction: Receipt,
  graph: Share2,
  chat: MessageSquare,
  kpi: Gauge,
};

function Panel({ title, children, actions, subtitle }) {
  return (
    <section className="panel padded">
      <div className="panel-heading">
        <div>
          <h3>{title}</h3>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

function useLoad(fn, deps) {
  const [state, setState] = useState({ data: null, error: "", loading: true });
  useEffect(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true }));
    fn()
      .then((data) => alive && setState({ data, error: "", loading: false }))
      .catch(
        (e) =>
          alive && setState({ data: null, error: e.message, loading: false }),
      );
    return () => {
      alive = false;
    };
  }, deps);
  return state;
}

/* ------------------------------------------------------------------ live 3D */
export function Live3DPanel({ run }) {
  const [node, setNode] = useState(null);
  const n = node && run.nodes.find((x) => x.id === node.id);
  return (
    <Panel
      title="Live 3D operations"
      subtitle="WebGL view of the same simulation: towers are systems, spheres are work items moving through live queues."
      actions={
        <span className="badge purple">
          {(run.environment_style || "workflow").replace("_", " ")} scene
        </span>
      }
    >
      <GL>
        <World3D run={run} onSelect={setNode} playing={run.clock?.running} />
      </GL>
      {n && (
        <div className="node-detail">
          <strong>{n.label}</strong>
          <span>
            {n.role} · {n.capacity} slots · health {Math.round(n.health)}% ·
            queue {run.history?.at(-1)?.queues?.[n.id] ?? 0} · evidence:{" "}
            {n.modality || "log"} ({n.source || n.label})
          </span>
          <button
            onClick={() => setNode(null)}
            aria-label="Close system details"
          >
            ×
          </button>
        </div>
      )}
    </Panel>
  );
}

/* ------------------------------------------------------------------ evidence locker */
function ImageEvidence({ item, complete }) {
  const c = item.content;
  const [w, h] = [320, 240];
  return (
    <figure className="evidence-image">
      <div className="image-frame">
        <img src={c.url} alt={c.caption} width={w} height={h} loading="lazy" />
        <svg viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
          {(c.detections || []).map((d, i) => (
            <g key={i}>
              <rect
                x={d.box[0]}
                y={d.box[1]}
                width={d.box[2] - d.box[0]}
                height={d.box[3] - d.box[1]}
                fill="none"
                stroke="#f5c542"
                strokeWidth="2"
              />
              <text x={d.box[0]} y={d.box[1] - 3} fill="#f5c542" fontSize="10">
                {d.label} {d.score}
              </text>
            </g>
          ))}
          {complete &&
            (c.ground_truth_boxes || []).map((d, i) => (
              <rect
                key={"g" + i}
                x={d.box[0]}
                y={d.box[1]}
                width={d.box[2] - d.box[0]}
                height={d.box[3] - d.box[1]}
                fill="none"
                stroke="#ff4d6d"
                strokeDasharray="4 3"
                strokeWidth="2"
              />
            ))}
        </svg>
      </div>
      <figcaption>
        {c.caption} · lighting ×{c.lighting} ·{" "}
        <span className="yellow-key">■</span> detector
        {complete && (
          <>
            {" "}
            · <span className="red-key">▭</span> ground truth
          </>
        )}
      </figcaption>
    </figure>
  );
}

function EvidenceBody({ item, complete }) {
  const c = item.content;
  switch (item.modality) {
    case "log":
      return <pre className="log-lines">{c.lines.join("\n")}</pre>;
    case "email":
      return (
        <div className="email">
          <small>
            From {c.sender} · To {c.to}
          </small>
          <strong>{c.subject}</strong>
          <pre>{c.body}</pre>
        </div>
      );
    case "sensor":
      return (
        <EChart
          height={170}
          label={`${c.metric} series`}
          option={{
            ...lineOption(
              c.points.map((p) => p.t),
              [
                {
                  name: `${c.metric} (${c.unit})`,
                  data: c.points.map((p) => p.v),
                  areaStyle: { opacity: 0.08 },
                },
              ],
            ),
            series: [
              {
                name: `${c.metric} (${c.unit})`,
                type: "line",
                smooth: true,
                showSymbol: false,
                data: c.points.map((p) => p.v),
                areaStyle: { opacity: 0.08 },
                markLine: {
                  symbol: "none",
                  lineStyle: { color: "#e5484d", type: "dashed" },
                  label: { formatter: "alert threshold" },
                  data: [{ yAxis: c.threshold }],
                },
              },
            ],
          }}
        />
      );
    case "image":
      return <ImageEvidence item={item} complete={complete} />;
    case "video":
      return (
        <figure className="evidence-image">
          <img
            src={c.url}
            alt={c.caption}
            width={320}
            height={240}
            loading="lazy"
          />
          <figcaption>{c.caption} (animated clip)</figcaption>
        </figure>
      );
    case "map":
      return (
        <svg
          className="mini-map"
          viewBox="0 0 100 100"
          role="img"
          aria-label={`Map around ${c.label}`}
        >
          <rect width="100" height="100" fill="#eef3ea" />
          {[20, 40, 60, 80].map((v) => (
            <g key={v}>
              <line
                x1={v}
                y1="0"
                x2={v}
                y2="100"
                stroke="#d8e2d0"
                strokeWidth="0.4"
              />
              <line
                x1="0"
                y1={v}
                x2="100"
                y2={v}
                stroke="#d8e2d0"
                strokeWidth="0.4"
              />
            </g>
          ))}
          <circle
            cx={c.center.x}
            cy={c.center.y}
            r={c.radius}
            fill="#e5484d22"
            stroke="#e5484d"
            strokeWidth="0.5"
          />
          {c.points.map((p) => (
            <circle
              key={p.id}
              cx={p.x}
              cy={p.y}
              r="1.2"
              fill={
                p.status === "queued"
                  ? "#e2a336"
                  : p.status === "processing"
                    ? "#4a8fe7"
                    : "#35a37b"
              }
            />
          ))}
          <circle cx={c.center.x} cy={c.center.y} r="2.2" fill="#29314e" />
          <text
            x={c.center.x + 3}
            y={c.center.y - 3}
            fontSize="4"
            fill="#29314e"
          >
            {c.label}
          </text>
        </svg>
      );
    case "ticket":
      return (
        <div className="ticket">
          <span className="badge">{c.ticket}</span>{" "}
          <span className="badge">{c.priority}</span>{" "}
          <span className="badge">{c.status}</span>
          <p>{c.text}</p>
        </div>
      );
    case "document":
      return (
        <div className="document">
          <strong>{c.title}</strong>
          {c.paragraphs.map((p, i) => (
            <p key={i}>{p}</p>
          ))}
        </div>
      );
    case "transaction":
      return (
        <div className="table-scroll small-table">
          <table>
            <thead>
              <tr>
                {Object.keys(c.rows[0] || {}).map((k) => (
                  <th key={k}>{k}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {c.rows.map((r, i) => (
                <tr key={i} className={r.flag ? "flagged" : ""}>
                  {Object.values(r).map((v, j) => (
                    <td key={j}>{String(v ?? "")}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    case "graph":
      return (
        <CyGraph
          height={220}
          layout="cose"
          label="Entity relationship graph"
          nodes={c.nodes.map((n) => ({
            id: n.id,
            label: n.type === "hub" ? n.id : "",
            color: n.type === "hub" ? "#7761db" : "#4a8fe7",
            size: n.type === "hub" ? 22 : 10,
          }))}
          edges={c.edges.map((e) => ({
            ...e,
            label: "",
            color: e.type === "transfer" ? "#e5484d" : "#c9cedc",
          }))}
        />
      );
    case "chat":
      return (
        <div className="chat">
          {c.messages.map((m, i) => (
            <p key={i}>
              <strong>{m.sender}</strong> {m.text}
            </p>
          ))}
        </div>
      );
    default:
      return c.series ? (
        <EChart
          height={200}
          label="KPI dashboard"
          option={lineOption(
            c.series.map((s) => s.t),
            [
              {
                name: "Service health %",
                data: c.series.map((s) => s.service),
              },
              {
                name: "Queued work",
                data: c.series.map((s) => s.queued),
                yAxisIndex: 0,
              },
            ],
          )}
        />
      ) : (
        <div className="kpis">
          {(c.metrics || []).map((m) => (
            <span key={m.name} className="kpi">
              <small>{m.name}</small>
              <strong>
                {typeof m.value === "number"
                  ? Math.round(m.value * 10) / 10
                  : m.value}
                {m.unit === "%" ? "%" : ""}
              </strong>
            </span>
          ))}
        </div>
      );
  }
}

export function EvidenceLocker({ run }) {
  const perspectives = [
    ...(run.perspectives || []),
    { id: "executive", label: "Executive (KPIs only)" },
  ];
  const [role, setRole] = useState(
    run.role || perspectives[0]?.id || "operations",
  );
  const [modality, setModality] = useState("all");
  const { data, error, loading } = useLoad(
    () => api(`/runs/${run.id}/evidence?role=${role}`),
    [run.id, run.tick, role],
  );
  const items = (data?.items || []).filter(
    (i) => modality === "all" || i.modality === modality,
  );
  const kinds = [...new Set((data?.items || []).map((i) => i.modality))];
  return (
    <Panel
      title="Evidence locker"
      subtitle="Multimodal, role-scoped evidence. Some items are harmless distractors; the hidden cause is revealed only in the debrief."
      actions={
        <a className="secondary" href={`/api/runs/${run.id}/bundle`}>
          <Download size={15} /> Export dataset bundle
        </a>
      }
    >
      <div className="evidence-toolbar">
        <label>
          Evidence perspective
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            {perspectives.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
        <div className="chips" role="group" aria-label="Filter evidence type">
          {["all", ...kinds].map((k) => (
            <button
              key={k}
              className={modality === k ? "chip active" : "chip"}
              onClick={() => setModality(k)}
            >
              {k}
            </button>
          ))}
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      {loading && !data && <p className="muted">Collecting evidence…</p>}
      {!loading && !items.length && (
        <p className="muted">
          No evidence for this perspective yet. Advance the simulation or switch
          perspective.
        </p>
      )}
      <div className="evidence-grid">
        {items.map((item) => {
          const Icon = MODALITY_ICON[item.modality] || FileText;
          return (
            <article
              key={item.id}
              className={
                "evidence-card " + item.severity + (item.decoy ? " decoy" : "")
              }
            >
              <header>
                <Icon size={15} />
                <strong>{item.node_label}</strong>
                <span className="badge">{item.modality}</span>
                <small>
                  min {Number(item.tick).toFixed(1)} · {item.source}
                </small>
                {item.decoy && <span className="badge amber">distractor</span>}
              </header>
              <p className="evidence-title">{item.title}</p>
              <EvidenceBody item={item} complete={data?.complete} />
            </article>
          );
        })}
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ commander */
export function CommanderPanel({ run, decide, busy, complete }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const committed = new Set(run.decisions.map((d) => d.action_id));
  return (
    <Panel
      title="Incident commander (Planner → Critic → Commander)"
      subtitle="Synthesizes every specialist's proposals, flags conflicts and ranks a plan within budget. It never executes actions."
      actions={
        <button
          className="primary"
          disabled={busy}
          onClick={async () => {
            try {
              setError("");
              setData(await api(`/runs/${run.id}/commander`, {}));
            } catch (e) {
              setError(e.message);
            }
          }}
        >
          <Brain size={16} /> Ask the commander
        </button>
      }
    >
      {error && <p className="error">{error}</p>}
      {!data && (
        <p className="muted">
          Convene the commander after an incident to get a prioritized,
          budget-aware plan.
        </p>
      )}
      {data && (
        <div className="commander">
          <div>
            <h4>Root-cause hypotheses</h4>
            {data.commander.hypothesis.length ? (
              data.commander.hypothesis.map((h) => (
                <p key={h.node}>
                  <span
                    className="dot"
                    style={{ background: healthColor(h.health) }}
                  />{" "}
                  <strong>{h.label}</strong> · {Math.round(h.health)}% ·{" "}
                  {h.reason}
                </p>
              ))
            ) : (
              <p className="muted">No degraded systems yet.</p>
            )}
            <h4>Critic</h4>
            <ul className="critic">
              {data.commander.critic.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>
          <div>
            <h4>
              Prioritized plan · {data.commander.planned_cost.toLocaleString()}{" "}
              of {data.commander.remaining_budget.toLocaleString()} units
            </h4>
            {data.commander.plan.map((p) => (
              <div className="plan-row" key={p.action_id}>
                <span className="priority">{p.priority}</span>
                <div>
                  <strong>{p.label}</strong>
                  <small>
                    {p.proposed_by} · {p.cost.toLocaleString()} units{" "}
                    {p.within_budget ? "" : "· exceeds remaining budget"}
                  </small>
                </div>
                <button
                  className="secondary"
                  disabled={
                    busy ||
                    complete ||
                    committed.has(p.action_id) ||
                    !p.within_budget
                  }
                  onClick={() => decide(p.action_id)}
                >
                  {committed.has(p.action_id) ? "Committed" : "Commit"}
                </button>
              </div>
            ))}
            <p className="tiny">
              {data.commander.mode}. {data.specialists.length} specialists
              consulted: {data.specialists.map((s) => s.agent).join(", ")}.
            </p>
          </div>
        </div>
      )}
    </Panel>
  );
}

/* ------------------------------------------------------------------ diagnosis & scorecard */
export function DiagnosisPanel({ run, setRun, busy, observing }) {
  const { data, error } = useLoad(
    () => api(`/runs/${run.id}/diagnosis`),
    [run.id, run.version],
  );
  const [root, setRoot] = useState("");
  const [cause, setCause] = useState("");
  const [message, setMessage] = useState("");
  const submitted = data?.submitted;
  return (
    <Panel
      title="Root-cause diagnosis"
      subtitle="Commit your diagnosis before the debrief. It is scored for accuracy and timing."
    >
      {error && <p className="error">{error}</p>}
      {submitted ? (
        <p className="callout">
          Submitted at minute {submitted.tick}:{" "}
          <strong>
            {
              data.options.nodes.find((n) => n.id === submitted.root_node)
                ?.label
            }
          </strong>{" "}
          — {submitted.cause}
        </p>
      ) : data ? (
        <form
          className="diagnosis-form"
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              const latest = await api(`/runs/${run.id}?role=${run.role}`);
              setRun(
                await api(`/runs/${run.id}/diagnosis`, {
                  root_node: root,
                  cause,
                  version: latest.version,
                }),
              );
              setMessage("Diagnosis recorded.");
            } catch (err) {
              setMessage(err.message);
            }
          }}
        >
          <label>
            First failing system
            <select
              value={root}
              onChange={(e) => setRoot(e.target.value)}
              required
            >
              <option value="">Select a system</option>
              {data.options.nodes.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.label}
                </option>
              ))}
            </select>
          </label>
          <fieldset>
            <legend>Most likely explanation</legend>
            {data.options.causes.map((c) => (
              <label key={c} className="radio">
                <input
                  type="radio"
                  name="cause"
                  value={c}
                  checked={cause === c}
                  onChange={() => setCause(c)}
                  required
                />{" "}
                {c}
              </label>
            ))}
          </fieldset>
          <button
            className="primary"
            disabled={busy || observing || !root || !cause}
          >
            Submit diagnosis
          </button>
          {message && <p className="tiny">{message}</p>}
        </form>
      ) : (
        <p className="muted">Loading options…</p>
      )}
    </Panel>
  );
}

const DIMENSION_LABELS = {
  business_impact: "Business impact avoided",
  detection_speed: "Time to detection",
  root_cause_accuracy: "Root-cause accuracy",
  recovery_time: "Recovery time",
  cost_efficiency: "Cost efficiency",
  sla_impact: "SLA protection",
  collaboration: "Agent collaboration",
  necessary_actions: "No unnecessary actions",
};

export function ScorecardPanel({ run }) {
  const { data, error } = useLoad(
    () => api(`/runs/${run.id}/scorecard`),
    [run.id, run.tick],
  );
  if (error)
    return (
      <Panel title="Dynamic scorecard">
        <p className="muted">{error}</p>
      </Panel>
    );
  if (!data)
    return (
      <Panel title="Dynamic scorecard">
        <p className="muted">Scoring…</p>
      </Panel>
    );
  const keys = Object.keys(DIMENSION_LABELS);
  return (
    <Panel
      title={`Dynamic scorecard · ${data.overall} / 100`}
      subtitle="Eight weighted dimensions compared with the identical no-action world."
    >
      <div className="scorecard">
        <EChart
          height={300}
          label="Scorecard radar"
          option={{
            tooltip: {},
            radar: {
              indicator: keys.map((k) => ({
                name: DIMENSION_LABELS[k],
                max: 100,
              })),
              radius: "62%",
            },
            series: [
              {
                type: "radar",
                areaStyle: { opacity: 0.2 },
                data: [
                  {
                    value: keys.map((k) => data.dimensions[k]),
                    name: "Your run",
                  },
                ],
              },
            ],
          }}
        />
        <div>
          <table className="score-table">
            <tbody>
              {keys.map((k) => (
                <tr key={k}>
                  <td>{DIMENSION_LABELS[k]}</td>
                  <td>{data.dimensions[k]}</td>
                  <td className="tiny">×{data.weights[k]}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="tiny">
            Diagnosis: system{" "}
            {data.diagnosis.root_correct ? "✓ correct" : "✗ incorrect"}, cause{" "}
            {data.diagnosis.cause_correct ? "✓ correct" : "✗ incorrect"}.
            {data.unnecessary_actions.length
              ? ` Unnecessary actions: ${data.unnecessary_actions.join(", ")}.`
              : " No unnecessary actions."}
            {data.ground_truth.contributing?.length
              ? ` Contributing causes: ${data.ground_truth.contributing.map((c) => c.cause).join("; ")}.`
              : ""}
          </p>
        </div>
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ population & connections */
export function PopulationPanel({ run }) {
  const { data, error, loading } = useLoad(
    () => api(`/runs/${run.id}/population`),
    [run.id, run.tick],
  );
  if (loading && !data)
    return (
      <Panel title="Agent population">
        <p className="muted">Running agents…</p>
      </Panel>
    );
  if (error || !data?.kind)
    return (
      <Panel title="Agent population">
        <p className="muted">{error || data?.message}</p>
      </Panel>
    );
  const keys = Object.keys(data.series[0] || {}).filter((k) => k !== "t");
  return (
    <Panel
      title={`Agent population · ${data.description}`}
      subtitle={`${data.agents} autonomous agents (${data.engine}). The shock starts with the incident and eases after the root cause is repaired.`}
    >
      <div className="population">
        {data.snapshot?.length ? (
          <GL>
            <PopulationDeck data={data} />
          </GL>
        ) : (
          <div className="muted padded">This model has no spatial view.</div>
        )}
        <EChart
          height={340}
          label="Population time series"
          option={lineOption(
            data.series.map((s) => s.t),
            keys.map((k) => ({
              name: k.replaceAll("_", " "),
              data: data.series.map((s) => s[k]),
            })),
          )}
        />
      </div>
      {data.events?.length > 0 && (
        <details>
          <summary>{data.events.length} agent events</summary>
          <ul className="critic">
            {data.events.slice(-20).map((e, i) => (
              <li key={i}>
                t={e.t}: {e.message}
              </li>
            ))}
          </ul>
        </details>
      )}
    </Panel>
  );
}

export function SignalsPanel({ run, onOpenRun, onOpenLab }) {
  const { data, error } = useLoad(
    () => api(`/runs/${run.id}/signals`),
    [run.id, run.tick],
  );
  const [message, setMessage] = useState("");
  return (
    <Panel
      title="Connected scenarios"
      subtitle="Outcomes of this run can trigger other scenarios (Scenario A → signal → Scenario B)."
    >
      {error && <p className="error">{error}</p>}
      {data && !data.active.length && (
        <p className="muted">
          No outgoing signals: no watched system fell below its threshold.
        </p>
      )}
      {data?.active.map((s) => (
        <p key={s.signal}>
          <Link2 size={14} /> <strong>{s.signal}</strong> from {s.node} (lowest
          health {s.lowest_health}%, intensity {s.intensity})
        </p>
      ))}
      <div className="handoff-list">
        {data?.targets.map((t) => (
          <button
            key={t.key + t.signal}
            className="secondary"
            onClick={async () => {
              try {
                const r = await api(`/runs/${run.id}/handoff`, {
                  target: t.key,
                  signal: t.signal,
                });
                if (r.kind === "lab") onOpenLab(r.id);
                else onOpenRun(r.id);
              } catch (e) {
                setMessage(e.message);
              }
            }}
          >
            {t.kind === "lab" ? <Radar size={14} /> : <Boxes size={14} />}{" "}
            Launch {t.title} ({t.signal})
          </button>
        ))}
      </div>
      {message && <p className="error">{message}</p>}
    </Panel>
  );
}

export function RolesMatrix() {
  const rows = useMemo(
    () => [
      [
        "Run published exercises, investigate and make your own decisions",
        "✓",
        "✓",
      ],
      ["Business, ML and historical data investigations", "✓", "✓"],
      ["Create, validate and publish scenarios (notifies learners)", "", "✓"],
      [
        "Assign exercises and observe results without changing learner decisions",
        "",
        "✓",
      ],
      ["SOP review, advanced authoring and custom ML failure mixes", "", "✓"],
      ["Manage accounts", "", "✓"],
    ],
    [],
  );
  return (
    <details className="roles-matrix">
      <summary>
        <Users size={14} /> Roles & access
      </summary>
      <table>
        <thead>
          <tr>
            <th>Capability</th>
            <th>Learner</th>
            <th>Admin / Trainer</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r[0]}>
              {r.map((c, i) => (
                <td key={i}>{c}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="tiny">
        Exactly two roles: Admin / Trainer manages exercises and coaching;
        Learner runs published exercises. No separate trainer account or
        authoring workspace is required.
      </p>
    </details>
  );
}
