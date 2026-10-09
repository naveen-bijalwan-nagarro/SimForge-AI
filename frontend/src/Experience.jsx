import React, { useEffect, useRef, useState } from "react";
import {
  Bell,
  Check,
  Database,
  Download,
  Play,
  ShieldCheck,
  X,
  Workflow,
} from "lucide-react";
import { api } from "./client";
import { CodexConnection } from "./CodexConnection";
import { OpenAIConnection } from "./OpenAIConnection";

export const exerciseTime = (minute) => {
  const seconds = Math.round((9 * 60 + Number(minute || 0)) * 60);
  return [
    Math.floor(seconds / 3600),
    Math.floor(seconds / 60) % 60,
    seconds % 60,
  ]
    .map((x) => String(x).padStart(2, "0"))
    .join(":");
};

const roleText = {
  admin: [
    "Admin / Trainer",
    "Create scenarios, inspect their checks and publish them for learners. You also assign exercises and observe results. A separate trainer account is not required; learners cannot create or publish scenarios.",
  ],
  learner: [
    "Learner",
    "Open assignments or the Scenario library, inspect linked mock data, diagnose the incident and make your own decisions. Compare outcomes and explain your reasoning; you cannot author, approve or publish scenarios.",
  ],
};

export function RoleGuide({ role }) {
  return (
    <section className="role-guide" aria-label="Your workspace role">
      <ShieldCheck size={23} />
      <div>
        <strong>{roleText[role][0]} workspace</strong>
        <p>{roleText[role][1]}</p>
      </div>
      <small>
        For simultaneous roles, use separate browser profiles or an incognito
        window. Tabs in the same profile share sign-in.
      </small>
    </section>
  );
}

export function Notifications({ onOpen }) {
  const [items, setItems] = useState([]),
    [open, setOpen] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    let alive = true,
      timer;
    async function poll() {
      try {
        const rows = await api("/notifications");
        if (alive) {
          setItems(rows);
          setError("");
        }
      } catch (e) {
        if (alive) setError(e.message);
      }
      if (alive) timer = setTimeout(poll, 4000);
    }
    poll();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, []);
  const unread = items.filter((x) => !x.seen).length;
  return (
    <div className="notification-host">
      <button
        className="notification-button"
        aria-label={`Notifications (${unread} unread)`}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <Bell size={19} />
        <span>{unread}</span>
      </button>
      {open && (
        <section className="notification-panel" aria-label="Notifications">
          <h3>Notifications</h3>
          <p className="tiny">
            New scenarios and trainer assignments appear here automatically.
          </p>
          {error && <p role="alert">{error}</p>}
          {!items.length && <p>No notifications yet.</p>}
          {items.map((item) => (
            <button
              className={"notification-item " + (!item.seen ? "unread" : "")}
              key={item.id}
              onClick={async () => {
                try {
                  await onOpen(item.scenario_key);
                  await api(`/notifications/${item.id}/read`, {});
                  setItems((old) =>
                    old.map((x) => (x.id === item.id ? { ...x, seen: 1 } : x)),
                  );
                  setOpen(false);
                } catch (e) {
                  setError(e.message);
                }
              }}
            >
              <strong>{item.title}</strong>
              <p>{item.message}</p>
              <small>{new Date(item.created * 1000).toLocaleString()}</small>
            </button>
          ))}
        </section>
      )}
    </div>
  );
}

function Grid({ rows }) {
  if (!rows.length)
    return (
      <p className="empty">
        No matching records at this point in the exercise.
      </p>
    );
  const keys = [...new Set(rows.flatMap((r) => Object.keys(r)))];
  return (
    <div className="relational-grid">
      <table>
        <thead>
          <tr>
            {keys.map((k) => (
              <th key={k}>{k}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {keys.map((k) => (
                <td key={k}>
                  {typeof row[k] === "object"
                    ? JSON.stringify(row[k])
                    : String(row[k] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function DataExplorer({ prepared, run }) {
  const [table, setTable] = useState("work_items"),
    [offset, setOffset] = useState(0),
    [result, setResult] = useState(null),
    [error, setError] = useState(""),
    [workId, setWorkId] = useState("");
  const tables = {
    ...prepared.tables,
    ...(run
      ? {
          live_telemetry: {
            description:
              "Observed health and queue counts by system and exercise minute. No future readings.",
          },
          activity_log: {
            description: "Actual work-item transitions; latest 4,000 retained.",
          },
          source_events: {
            description:
              "Observed incident signals, cascades, decisions and effects from source systems. Hidden causes remain in the debrief.",
          },
        }
      : {}),
  };
  useEffect(() => {
    let active = true;
    const path = run
      ? `/runs/${run.id}/data/${table}`
      : `/preparations/${prepared.id}/tables/${table}`;
    api(
      `${path}?offset=${offset}&limit=30&work_id=${encodeURIComponent(workId)}`,
    )
      .then((r) => {
        if (active) {
          setResult(r);
          setError("");
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [prepared.id, run?.id, run?.tick, table, offset, workId]);
  return (
    <section className="data-explorer">
      <div className="dataset-selector">
        <label>
          Dataset
          <select
            aria-label="Dataset"
            value={table}
            onChange={(e) => {
              // Reselecting the current dataset must not clear its rows: no
              // dependency changes, so the loading effect would not run again.
              if (e.target.value === table) return;
              setTable(e.target.value);
              setOffset(0);
              setResult(null);
            }}
          >
            {Object.entries(tables).map(([name, info]) => (
              <option key={name} value={name}>
                {name}{" "}
                {info.rows != null
                  ? `(${info.rows.toLocaleString()} rows)`
                  : "(live)"}
              </option>
            ))}
          </select>
        </label>
        {run && (
          <label>
            Trace work ID
            <input
              placeholder="e.g. TRA-00001"
              value={workId}
              onChange={(e) => {
                setWorkId(e.target.value);
                setOffset(0);
              }}
            />
          </label>
        )}
        <a
          className="secondary"
          href={`/api/preparations/${prepared.id}/export`}
        >
          <Download size={16} /> Download starting datasets
        </a>
      </div>
      <p className="muted">{tables[table]?.description}</p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {result ? (
        <>
          <Grid rows={result.rows} />
          <div className="dataset-pagination">
            <span>
              {result.total.toLocaleString()} records
              {run && ` · observed at ${exerciseTime(result.tick)}`}
            </span>
            <button
              className="secondary"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - 30))}
            >
              Previous rows
            </button>
            <button
              className="secondary"
              disabled={offset + 30 >= result.total}
              onClick={() => setOffset(offset + 30)}
            >
              Next rows
            </button>
          </div>
        </>
      ) : (
        <p>Loading records…</p>
      )}
    </section>
  );
}

export function EnvironmentSetup({
  scenario,
  onClose,
  onReady,
  onLegacy,
  initialPrepared = null,
  readOnly = false,
}) {
  const [seed, setSeed] = useState(initialPrepared?.seed ?? 2026),
    [population, setPopulation] = useState(initialPrepared?.population ?? 300),
    [horizon, setHorizon] = useState(initialPrepared?.horizon ?? 45),
    [prepared, setPrepared] = useState(initialPrepared),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [stage, setStage] = useState(initialPrepared ? "Datasets" : "Mission");
  const brief = scenario.briefing;
  async function generate() {
    setBusy(true);
    setError("");
    try {
      setPrepared(
        await api("/preparations", {
          scenario_key: scenario.key,
          seed: Number(seed),
          population: Number(population),
          horizon: Number(horizon),
        }),
      );
      setStage("Datasets");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function launch() {
    if (readOnly) return;
    setBusy(true);
    setError("");
    try {
      onReady(await api("/runs", { preparation_id: prepared.id }));
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  }
  return (
    <div className="modal-backdrop">
      <section
        className="modal environment-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="launch-title"
      >
        <button
          className="close"
          disabled={busy}
          aria-label="Close launch dialog"
          onClick={onClose}
        >
          <X size={20} />
        </button>
        <span className="eyebrow">
          {scenario.category} / PREPARE YOUR ENVIRONMENT
        </span>
        <h2 id="launch-title">{scenario.title}</h2>
        <div className="setup-progress">
          <span className={stage === "Mission" ? "active" : ""}>
            1. Understand your mission
          </span>
          <span className={stage === "Datasets" ? "active" : ""}>
            2. Generate & inspect data
          </span>
          <span>3. Enter live simulation</span>
        </div>
        <div className="tabs">
          <button
            onClick={() => setStage("Mission")}
            className={stage === "Mission" ? "active" : ""}
          >
            Mission
          </button>
          <button
            disabled={!prepared}
            onClick={() => setStage("Datasets")}
            className={stage === "Datasets" ? "active" : ""}
          >
            Datasets {prepared && `(${Object.keys(prepared.tables).length})`}
          </button>
        </div>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {stage === "Mission" ? (
          <>
            <p>{brief?.context || scenario.summary}</p>
            <div className="mission-banner">
              <strong>
                You are the {brief?.role || "incident coordinator"}.
              </strong>
              <p>{brief?.mission || scenario.objective}</p>
            </div>
            <ol className="mission-steps">
              {brief?.steps.map((step, i) => (
                <li key={step.title}>
                  <span>{i + 1}</span>
                  <div>
                    <strong>{step.title}</strong>
                    <p>{step.detail}</p>
                  </div>
                </li>
              ))}
            </ol>
            <p>
              <strong>Success looks like:</strong> {brief?.success}
            </p>
            <div className="form-grid">
              <label>
                Reproducible seed
                <input
                  type="number"
                  min="0"
                  max="2147483647"
                  value={seed}
                  disabled={!!prepared}
                  onChange={(e) => setSeed(e.target.value)}
                />
              </label>
              <label>
                Work items to generate
                <input
                  type="number"
                  min="20"
                  max="5000"
                  value={population}
                  disabled={!!prepared}
                  onChange={(e) => setPopulation(e.target.value)}
                />
              </label>
              <label>
                Exercise duration (simulated minutes)
                <input
                  type="number"
                  min="20"
                  max="120"
                  value={horizon}
                  disabled={!!prepared}
                  onChange={(e) => setHorizon(e.target.value)}
                />
              </label>
            </div>
            <p className="tiny">
              {brief?.clock_explanation} The exercise starts at 09:00. A
              45-minute exercise ends at 09:45, not after 45 minutes of waiting.
            </p>
            {!prepared && (
              <button
                className="primary full"
                disabled={busy}
                onClick={generate}
              >
                <Database size={17} />
                {busy
                  ? "Generating linked datasets and checking relationships…"
                  : "Generate scenario datasets"}
              </button>
            )}
            {scenario.kind === "training" && (
              <button
                className="secondary full"
                disabled={busy}
                onClick={() => onLegacy(scenario)}
              >
                Open historical case assessment instead
              </button>
            )}
          </>
        ) : (
          prepared && (
            <>
              <div className="prepared-stats">
                <div>
                  <strong>{Object.keys(prepared.tables).length}</strong>
                  <span>linked datasets</span>
                </div>
                <div>
                  <strong>
                    {Object.values(prepared.tables)
                      .reduce((n, t) => n + t.rows, 0)
                      .toLocaleString()}
                  </strong>
                  <span>synthetic records</span>
                </div>
                <div>
                  <strong>{prepared.validation.foreign_key_checks}</strong>
                  <span>relationship checks passed</span>
                </div>
              </div>
              <DataExplorer prepared={prepared} />
              <details className="relationship-list">
                <summary>How the datasets connect</summary>
                {prepared.relationships.map((r) => (
                  <p key={r.join(".")}>
                    <code>
                      {r[0]}.{r[1]}
                    </code>{" "}
                    →{" "}
                    <code>
                      {r[2]}.{r[3]}
                    </code>
                  </p>
                ))}
              </details>
              <p className="tiny">
                The generated work_items and planned routes drive this run.
                Source-system status changes as those same records move.
                Historical case_* tables stay fixed for investigation.
              </p>
            </>
          )
        )}
        {prepared && (
          <button
            className="primary full"
            disabled={busy || readOnly}
            onClick={launch}
          >
            <Play size={16} />
            Enter simulation with these datasets
          </button>
        )}
        {readOnly && (
          <p className="tiny">
            Inspection only: this workload belongs to another user. Open the
            scenario from Scenario library to generate your own preview
            environment.
          </p>
        )}
      </section>
    </div>
  );
}

function ServiceConsole({ run }) {
  const [system, setSystem] = useState("all"),
    [selectedId, setSelectedId] = useState(null);
  const records = run.entities.filter((e) =>
    system === "all" ? e.state !== "scheduled" : e.current_node === system,
  );
  const selected = run.entities.find((e) => e.id === selectedId);
  return (
    <div className="service-console" aria-label="Mock application console">
      <div className="service-app-bar">
        <span>
          <i /> <i /> <i />
        </span>
        <strong>{run.title} / Operations application</strong>
        <span>SYNTHETIC</span>
      </div>
      <div className="service-app-body">
        <nav aria-label="Mock application systems">
          <button
            className={system === "all" ? "active" : ""}
            onClick={() => setSystem("all")}
          >
            All active records
          </button>
          {run.live.systems.map((s) => (
            <button
              key={s.system_id}
              className={system === s.system_id ? "active" : ""}
              onClick={() => setSystem(s.system_id)}
            >
              {s.label}
              <small>{s.processing + s.queued} active</small>
            </button>
          ))}
        </nav>
        <section>
          <div className="service-app-heading">
            <h3>Operational work queue</h3>
            <span>
              {records.length} records · {exerciseTime(run.tick)}
            </span>
          </div>
          <p>
            Open a record to inspect its route, deadline and current state.
            Queues update from the live engine.
          </p>
          <div className="service-work-list">
            {records.slice(0, 20).map((e) => (
              <button key={e.id} onClick={() => setSelectedId(e.id)}>
                <strong>{e.id}</strong>
                <span>
                  {run.nodes.find((n) => n.id === e.current_node)?.label ||
                    "Workflow complete"}
                </span>
                <span className={"work-status " + e.state}>{e.state}</span>
              </button>
            ))}
            {!records.length && (
              <p>
                No active records here. Start playback or select another system.
              </p>
            )}
          </div>
          {records.length > 20 && (
            <small>
              Showing the first 20 records. Live datasets supports paginated
              inspection of the complete workload.
            </small>
          )}
          {selected && (
            <div className="service-record">
              <button
                aria-label="Close record details"
                onClick={() => setSelectedId(null)}
              >
                <X size={15} />
              </button>
              <h3>{selected.id}</h3>
              <p>
                {selected.state} · {selected.region} · {selected.priority}
              </p>
              <p>
                Arrival: {exerciseTime(selected.arrival)} · Deadline:{" "}
                {exerciseTime(selected.due_minute)}
              </p>
              <p>
                Route:{" "}
                {selected.planned_path
                  .map((k) => run.nodes.find((n) => n.id === k)?.label || k)
                  .join(" → ")}
              </p>
              <p>
                Use this work ID in Live datasets to trace its linked
                source-system records.
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export function LiveOperations({ run }) {
  const [selected, setSelected] = useState(null);
  const live = run.live;
  if (!live) return null;
  const columns = Math.min(3, live.systems.length),
    width = columns * 245 + 10,
    rows = Math.ceil(live.systems.length / columns);
  const positions = Object.fromEntries(
    live.systems.map((s, i) => [
      s.system_id,
      { x: 125 + (i % columns) * 245, y: 90 + Math.floor(i / columns) * 155 },
    ]),
  );
  const selectedSystem = live.systems.find((s) => s.system_id === selected);
  return (
    <section
      className={
        "live-operations panel " +
        (run.clock?.running ? "is-playing " : "") +
        run.environment_style
      }
    >
      <div className="panel-heading">
        <div>
          <h3>Live operations</h3>
          <p>{live.explanation}</p>
        </div>
        <span className="badge">
          {run.clock?.running
            ? "PLAYING"
            : run.status === "completed"
              ? "COMPLETED"
              : "PAUSED"}
        </span>
      </div>
      {run.environment_style === "service_app" ? (
        <ServiceConsole run={run} />
      ) : (
        <div className="live-scene" aria-label="Live workflow visualization">
          <svg
            viewBox={`0 0 ${width} ${rows * 155 + 15}`}
            role="img"
            aria-label="Systems and dependencies. Dots represent actively processing work; select a system below for details."
          >
            <defs>
              <marker
                id="flow-arrow"
                viewBox="0 0 10 10"
                refX="8"
                refY="5"
                markerWidth="5"
                markerHeight="5"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#8591b8" />
              </marker>
            </defs>
            {run.edges.map((e, i) => {
              const a = positions[e.source],
                b = positions[e.target];
              return a && b ? (
                <path
                  key={i}
                  d={`M${a.x},${a.y} C${a.x},${a.y + 65} ${b.x},${b.y - 65} ${b.x},${b.y}`}
                  className="flow-link"
                  markerEnd="url(#flow-arrow)"
                />
              ) : null;
            })}
            {live.systems.map((s) => {
              const pos = positions[s.system_id];
              const color =
                s.health < 50
                  ? "#e78e73"
                  : s.health < 80
                    ? "#e3bd73"
                    : "#80d2bd";
              return (
                <g key={s.system_id} transform={`translate(${pos.x},${pos.y})`}>
                  {run.environment_style === "voxel" && (
                    <>
                      <path
                        d="M-92,-33 L-69,-51 L115,-51 L92,-33 Z"
                        fill="#415781"
                      />
                      <path
                        d="M92,-33 L115,-51 L115,25 L92,43 Z"
                        fill="#263453"
                      />
                    </>
                  )}
                  <rect
                    x="-92"
                    y="-33"
                    width="184"
                    height="76"
                    rx={run.environment_style === "voxel" ? 2 : 13}
                    fill="#182941"
                    stroke={selected === s.system_id ? "#e3deff" : color}
                    strokeWidth="2"
                  />
                  <text y="-9" textAnchor="middle" fill="#edf2ff" fontSize="12">
                    {s.label.length > 26 ? s.label.slice(0, 24) + "…" : s.label}
                  </text>
                  <text y="11" textAnchor="middle" fill={color} fontSize="11">
                    {s.processing} processing · {s.queued} queued
                  </text>
                  {Array.from({ length: Math.min(s.processing, 8) }, (_, i) => (
                    <circle
                      className="work-particle"
                      key={i}
                      cx={-35 + i * 10}
                      cy="29"
                      r="3"
                      fill={color}
                      style={{ animationDelay: `${i * 0.15}s` }}
                    />
                  ))}
                </g>
              );
            })}
          </svg>
        </div>
      )}
      <p className="scene-caption">
        {run.environment_style === "voxel"
          ? "Block-style operational world, not a Minecraft server."
          : run.environment_style === "service_app"
            ? "Mock application workflow; no production application is connected."
            : "Each box is a real engine system. Dots are capped at eight per system; counts show the full workload."}{" "}
        Animation pauses with the exercise.
      </p>
      <div className="system-selector">
        {live.systems.map((s) => (
          <button
            key={s.system_id}
            className={selected === s.system_id ? "selected" : ""}
            onClick={() => setSelected(s.system_id)}
          >
            {s.label}
            <strong>{s.health.toFixed(0)}% health</strong>
          </button>
        ))}
      </div>
      {selectedSystem && (
        <div className="system-inspection">
          <strong>{selectedSystem.label}</strong>
          <p>
            {selectedSystem.processing} records processing;{" "}
            {selectedSystem.queued} waiting for a capacity slot.
          </p>
          <p>
            Trace these IDs in Live datasets:{" "}
            {selectedSystem.records.join(", ") ||
              "No active records at this system yet."}
          </p>
        </div>
      )}
      <div className="live-bottom">
        <section>
          <h3>What you should do now</h3>
          <p>
            {run.tick === 0
              ? "Your datasets are ready. Start playback, then watch records enter the first systems."
              : run.nodes.some((n) => n.health < 70)
                ? "A system is degraded. Pause, inspect its records and upstream dependencies, then choose a response in the Decision desk."
                : "Observe the work moving through the systems. Compare queue growth and completion times before intervening."}
          </p>
          <small>Budget and health are illustrative training units.</small>
        </section>
        <section>
          <h3>Record activity</h3>
          <div className="live-activity">
            {live.activity.slice(0, 8).map((a) => (
              <div key={a.id}>
                <time>{exerciseTime(a.tick)}</time>
                <span>{a.message}</span>
              </div>
            ))}
            {!live.activity.length && (
              <p>
                No arrivals yet. Start playback to activate the generated
                workload.
              </p>
            )}
          </div>
        </section>
      </div>
    </section>
  );
}

export function RunDatasets({ run }) {
  const [prepared, setPrepared] = useState(null),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    if (run.preparation_id)
      api("/preparations/" + run.preparation_id)
        .then((r) => {
          if (active) setPrepared(r);
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    return () => {
      active = false;
    };
  }, [run.preparation_id]);
  return (
    <section className="panel padded">
      <h3>Inspect linked data as the exercise runs</h3>
      {error && <p role="alert">{error}</p>}
      {prepared ? (
        <DataExplorer prepared={prepared} run={run} />
      ) : (
        <p>
          {run.preparation_id
            ? "Loading dataset manifest…"
            : "This older run predates prepared environments. Start a new run to inspect linked datasets."}
        </p>
      )}
    </section>
  );
}

export const authorTemplates = {
  "Supplier disruption": {
    title: "Supplier Disruption Command",
    summary:
      "A dispatch-confirmation fault blocks inbound supply, reduces stock and delays customer deliveries. Find the source and restore the flow within budget.",
    unit: "orders",
    environment_style: "service_app",
    learner_role: "Supply planner",
    mission:
      "Trace an affected order from supplier dispatch through receiving, inventory, production and customer delivery. Diagnose the first failing system and justify a response with evidence.",
    success:
      "Recover processing, reduce late deliveries against the no-action baseline and stay within the synthetic response budget.",
    nodes: [
      ["dispatch", "Supplier dispatch", "investigator"],
      ["receiving", "Inbound receiving", "operations"],
      ["inventory", "Inventory allocation", "operations"],
      ["production", "Production planning", "operations"],
      ["delivery", "Customer delivery", "finance"],
    ].map(([id, label, role]) => ({ id, label, role, capacity: 5 })),
    edges: [
      ["dispatch", "receiving"],
      ["receiving", "inventory"],
      ["inventory", "production"],
      ["production", "delivery"],
    ].map(([source, target]) => ({ source, target })),
    incident_node: "dispatch",
    cause:
      "A dispatch-confirmation rule holds supplier orders in an inactive allocation queue.",
  },
  "Service application": {
    title: "Customer Service Application Outage",
    summary:
      "A broken case-routing rule overloads specialist teams while priority customer cases wait. Recover service and protect urgent cases.",
    unit: "cases",
    environment_style: "service_app",
    learner_role: "Service desk controller",
    mission:
      "Find the source of delayed cases, protect critical customers and restore routing using the mock service application.",
    success:
      "Use case and workflow records to explain the incident, recover service and stay within budget.",
    nodes: [
      ["intake", "Case intake", "investigator"],
      ["triage", "Priority triage", "operations"],
      ["specialists", "Specialist queues", "operations"],
      ["billing", "Billing review", "finance"],
      ["resolution", "Case resolution", "operations"],
      ["customers", "Customer follow-up", "finance"],
    ].map(([id, label, role]) => ({ id, label, role, capacity: 5 })),
    edges: [
      ["intake", "triage"],
      ["triage", "specialists"],
      ["triage", "billing"],
      ["specialists", "resolution"],
      ["billing", "resolution"],
      ["resolution", "customers"],
    ].map(([source, target]) => ({ source, target })),
    incident_node: "triage",
    cause:
      "A routing-rule release sends priority cases to an unstaffed specialist queue.",
  },
  "Block-building world": {
    title: "Voxel Settlement Resource Crisis",
    summary:
      "A mining allocation fault starves workshops, storage and building crews. Keep the settlement supplied while investigating the broken resource chain.",
    unit: "deliveries",
    environment_style: "voxel",
    learner_role: "Settlement resource coordinator",
    mission:
      "Trace resource deliveries through the settlement, identify the bottleneck and restore construction without exhausting emergency supplies.",
    success:
      "Restore settlement processing, protect construction deliveries and explain the source using linked records.",
    nodes: [
      ["mines", "Resource mines", "investigator"],
      ["storage", "Storage depot", "operations"],
      ["workshops", "Crafting workshops", "operations"],
      ["transport", "Transport carts", "operations"],
      ["construction", "Building crews", "operations"],
      ["citizens", "Settlement services", "finance"],
    ].map(([id, label, role]) => ({ id, label, role, capacity: 5 })),
    edges: [
      ["mines", "storage"],
      ["storage", "workshops"],
      ["storage", "transport"],
      ["workshops", "construction"],
      ["transport", "construction"],
      ["construction", "citizens"],
    ].map(([source, target]) => ({ source, target })),
    incident_node: "mines",
    cause:
      "A duplicated resource allocation reserves all incoming ore for an inactive construction project.",
  },
};

export function AdminStudio({
  onPublished,
  Graph,
  compact = false,
  showReview = true,
  onDraftReady,
}) {
  const [text, setText] = useState(
      JSON.stringify(authorTemplates["Supplier disruption"], null, 2),
    ),
    [drafts, setDrafts] = useState([]),
    [jobs, setJobs] = useState([]),
    [status, setStatus] = useState(null),
    [engine, setEngine] = useState("codex"),
    [apiStatus, setApiStatus] = useState(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [prompt, setPrompt] = useState(
      "Create a supplier disruption exercise for a supply planner. Connect supplier dispatch, inbound receiving, inventory allocation, production and customer delivery. A dispatch-confirmation fault should cause queues and late orders. Include a clear mission, evidence-led diagnosis and safe repair, investigation and alternate-route decisions. Use synthetic data only.",
    ),
    [job, setJob] = useState(null);
  async function refresh() {
    setDrafts(await api("/scenario-drafts"));
  }
  useEffect(() => {
    refresh().catch((e) => setError(e.message));
    api("/authoring/jobs")
      .then((previous) => {
        setJobs(previous);
        const running = previous.find((j) => j.status === "running");
        if (running) setJob(running);
      })
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (!job || job.status !== "running") return;
    let active = true,
      timer;
    async function poll() {
      try {
        const result = await api("/authoring/jobs/" + job.id);
        if (active) {
          setJob(result);
          if (result.status !== "running") {
            await refresh();
            setJobs(await api("/authoring/jobs"));
            if (result.status === "ready") onDraftReady?.();
          } else timer = setTimeout(poll, 2000);
        }
      } catch (e) {
        if (active) setError(e.message);
      }
    }
    timer = setTimeout(poll, 1500);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [job?.id, job?.status]);
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
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {}
  return (
    <>
      {!compact && (
        <div className="page-heading">
          <div>
            <span className="eyebrow">ADMINISTRATOR / SCENARIO STUDIO</span>
            <h1>Create, validate and publish</h1>
            <p>
              Only published scenarios appear for learners. Publishing sends
              notifications automatically.
            </p>
          </div>
        </div>
      )}
      {error && (
        <p className="error-banner" role="alert">
          {error}
        </p>
      )}
      <section className="panel padded codex-author">
        <h2>1 · Create an exercise</h2>
        <label>
          Authoring engine
          <select value={engine} onChange={(e) => setEngine(e.target.value)}>
            <option value="codex">Primary: Codex (signed-in local CLI)</option>
            <option value="openai_api">Backup: OpenAI API (admin only)</option>
            <option value="manual">Offline template</option>
          </select>
        </label>
        {engine === "codex" && <CodexConnection onChange={setStatus} />}
        <p className="tiny">
          Codex is always the default primary. The API is an explicit admin
          backup, never an automatic retry. Switching engines alone does not
          send a prompt or incur API usage.
        </p>
        {engine === "codex" &&
          status &&
          (!status.ready ||
            (job?.status === "failed" && job.engine !== "openai_api")) && (
            <section
              className="success-note"
              aria-label="Alternate authoring flow"
            >
              <p>
                Codex is unavailable or its last draft failed. Check sign-in,
                quota and connection, or explicitly choose the API backup.
              </p>
              <button
                className="secondary"
                onClick={() => setEngine("openai_api")}
              >
                Use OpenAI API backup
              </button>
            </section>
          )}
        {engine === "openai_api" && (
          <>
            <button className="secondary" onClick={() => setEngine("codex")}>
              Return to primary Codex
            </button>
            <OpenAIConnection onChange={setApiStatus} />
          </>
        )}
        {engine === "codex" && <p>{status?.safety}</p>}
        {engine !== "manual" && (
          <>
            <label>
              Scenario description
              <textarea
                rows="3"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
              />
            </label>
            <button
              className="primary"
              disabled={
                busy ||
                job?.status === "running" ||
                (engine === "openai_api"
                  ? !apiStatus?.ready
                  : !status?.ready) ||
                prompt.trim().length < 30
              }
              onClick={() =>
                act(async () =>
                  setJob(
                    await api(
                      engine === "openai_api"
                        ? "/authoring/openai"
                        : "/authoring/codex",
                      { prompt },
                    ),
                  ),
                )
              }
            >
              {engine === "openai_api"
                ? "Generate draft with OpenAI API"
                : "Generate draft with Codex"}
            </button>
            <p className="tiny">
              Your description is sent to OpenAI through the selected server
              connection. API requests use separate API billing; they are not
              Codex CLI activity. Use synthetic, non-sensitive requirements
              only.{" "}
              {engine === "codex" &&
                (status?.enabled
                  ? status.mode
                  : "Enable local authoring in the connection panel above. Production deployment requires server opt-in. Templates work offline.")}
            </p>
            {job && (
              <p role="status">
                <strong>
                  {job.status === "running"
                    ? `${job.engine === "openai_api" ? "OpenAI API" : "Codex"} is generating a draft…`
                    : job.status}
                </strong>{" "}
                {job.message}
              </p>
            )}
            {jobs.length > 0 && (
              <details>
                <summary>Previous generation jobs ({jobs.length})</summary>
                {jobs.map((j) => (
                  <p key={j.id}>
                    <button className="secondary" onClick={() => setJob(j)}>
                      {j.status} · {(j.prompt || "Scenario draft").slice(0, 90)}
                    </button>
                  </p>
                ))}
              </details>
            )}
          </>
        )}
      </section>
      <details
        className="panel padded template-authoring"
        open={engine === "manual"}
      >
        <summary>Use a tested template instead (works without Codex)</summary>
        <p>
          A template draft uses the same checks, admin review and publication
          gate. Its source is recorded as manual, not Codex.
        </p>
        <div className="workspace-grid designer-grid">
          <section className="panel padded">
            <h3>World definition</h3>
            <div className="template-buttons">
              {Object.entries(authorTemplates).map(([label, value]) => (
                <button
                  className="secondary"
                  key={label}
                  onClick={() => setText(JSON.stringify(value, null, 2))}
                >
                  {label}
                </button>
              ))}
            </div>
            <label>
              Scenario definition JSON
              <textarea
                className="code-editor"
                rows="22"
                value={text}
                onChange={(e) => setText(e.target.value)}
                spellCheck="false"
              />
            </label>
            <button
              className="primary full"
              disabled={busy || !parsed}
              onClick={() =>
                act(async () => {
                  await api("/scenario-drafts", parsed);
                  await refresh();
                  onDraftReady?.();
                })
              }
            >
              Validate & save draft
            </button>
            <p className="tiny">
              Definitions are constrained JSON, never executable uploads. No
              real game server, external app or production system is created.
            </p>
          </section>
          <section className="panel">
            <div className="panel-heading">
              <h3>Dependency preview</h3>
              <Workflow size={18} />
            </div>
            {Array.isArray(parsed?.nodes) &&
            Array.isArray(parsed?.edges) &&
            parsed.nodes.every(
              (n) =>
                n && typeof n.id === "string" && typeof n.label === "string",
            ) &&
            parsed.edges.every(
              (e) =>
                e &&
                typeof e.source === "string" &&
                typeof e.target === "string",
            ) ? (
              <Graph nodes={parsed.nodes} edges={parsed.edges} />
            ) : (
              <p className="padded">
                Enter a valid JSON definition to preview its workflow.
              </p>
            )}
          </section>
        </div>
      </details>
      {showReview && (
        <section className="panel padded">
          <h3>Review and publish</h3>
          <p>
            Review the mission and checks before making a scenario available to
            everyone.
          </p>
          {!drafts.length && <p>No drafts yet. Save a definition above.</p>}
          {drafts.map((d) => (
            <article className="draft-review" key={d.id}>
              <div>
                <h3>{d.definition.title}</h3>
                <span className="badge">
                  {d.source} · {d.status}
                </span>
              </div>
              <p>{d.definition.mission}</p>
              <div className="validation-checks">
                {d.checks.map((c) => (
                  <span className={c.passed ? "pass" : "fail"} key={c.name}>
                    {c.passed ? "✓" : "×"} {c.name}
                    <small>{c.detail}</small>
                  </span>
                ))}
              </div>
              {d.pack_yaml ? (
                <details className="pack-yaml">
                  <summary>View scenario pack (YAML)</summary>
                  <pre>{d.pack_yaml}</pre>
                </details>
              ) : (
                <button
                  className="secondary"
                  onClick={() => setText(JSON.stringify(d.definition, null, 2))}
                >
                  Load definition for review
                </button>
              )}
              <button
                className="primary"
                disabled={
                  busy ||
                  d.status === "published" ||
                  d.checks.some((c) => !c.passed)
                }
                onClick={() =>
                  act(async () => {
                    const published = await api(
                      `/scenario-drafts/${d.id}/publish`,
                      {},
                    );
                    await refresh();
                    await onPublished(published);
                  })
                }
              >
                {d.status === "published"
                  ? "Published"
                  : "Publish & notify learners"}
              </button>
            </article>
          ))}
        </section>
      )}
    </>
  );
}

export function TrainingDesk({ user, scenarios, onOpen, onRun }) {
  const [learners, setLearners] = useState([]),
    [assignments, setAssignments] = useState([]),
    [runs, setRuns] = useState([]),
    [chosen, setChosen] = useState([]),
    [key, setKey] = useState(scenarios[0]?.key || ""),
    [guidance, setGuidance] = useState(
      "Trace one work item through the linked datasets. Identify the first disrupted system, explain the downstream impact and justify your response before completing the debrief.",
    ),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  const manage = user.role === "admin";
  async function refresh() {
    const [a, r] = await Promise.all([api("/assignments"), api("/runs")]);
    setAssignments(a);
    setRuns(r);
    if (manage) setLearners(await api("/learners"));
  }
  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, []);
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>{manage ? "Trainer workspace" : "My assignments"}</h1>
          <p>
            {manage
              ? "Assign a published mission, guide learners and observe their progress without taking over their decisions."
              : "Read your trainer’s guidance, then generate your own environment and complete the exercise."}
          </p>
        </div>
        <button
          className="secondary"
          onClick={() => refresh().catch((e) => setError(e.message))}
        >
          Refresh progress
        </button>
      </div>
      {error && (
        <p role="alert" className="error-banner">
          {error}
        </p>
      )}
      {message && (
        <p role="status" className="success-note">
          {message}
        </p>
      )}
      {manage && (
        <section className="panel padded">
          <h3>Assign an exercise</h3>
          <label>
            Published scenario
            <select value={key} onChange={(e) => setKey(e.target.value)}>
              {scenarios.map((s) => (
                <option key={s.key} value={s.key}>
                  {s.title}
                </option>
              ))}
            </select>
          </label>
          <div className="learner-checks">
            {learners.map((l) => (
              <label key={l.id}>
                <input
                  type="checkbox"
                  checked={chosen.includes(l.id)}
                  onChange={(e) =>
                    setChosen((old) =>
                      e.target.checked
                        ? [...old, l.id]
                        : old.filter((x) => x !== l.id),
                    )
                  }
                />
                {l.name}
              </label>
            ))}
          </div>
          <label>
            Trainer guidance
            <textarea
              rows="3"
              value={guidance}
              onChange={(e) => setGuidance(e.target.value)}
            />
          </label>
          <button
            className="primary"
            disabled={!chosen.length || busy}
            onClick={async () => {
              setBusy(true);
              setError("");
              try {
                await api("/assignments", {
                  scenario_key: key,
                  learners: chosen,
                  guidance,
                });
                await refresh();
                setMessage("Exercise assigned. Learners have been notified.");
              } catch (e) {
                setError(e.message);
              } finally {
                setBusy(false);
              }
            }}
          >
            Assign & notify learners
          </button>
        </section>
      )}
      <section className="panel padded">
        <h3>Assigned exercises</h3>
        {!assignments.length && (
          <p>
            No assignments yet. Published scenarios are also available from the
            library.
          </p>
        )}
        {assignments.map((a) => (
          <article className="assignment" key={a.id}>
            <h3>{a.title}</h3>
            <p>{a.guidance}</p>
            <small>Trainer: {a.trainer}</small>
            <button
              className="secondary"
              onClick={() => onOpen(a.scenario_key)}
            >
              Open mission
            </button>
          </article>
        ))}
      </section>
      <section className="panel padded">
        <h3>{manage ? "Observe learner runs" : "My exercise progress"}</h3>
        {runs
          .filter((r) => !manage || r.owner !== user.id)
          .map((r) => (
            <button className="list-row" key={r.id} onClick={() => onRun(r.id)}>
              <strong>{r.title}</strong>
              <span>
                {r.owner} · {r.tick} of {r.horizon} simulated minutes ·{" "}
                {r.status}
              </span>
            </button>
          ))}
        {!runs.length && <p>No runs started yet.</p>}
      </section>
    </>
  );
}
