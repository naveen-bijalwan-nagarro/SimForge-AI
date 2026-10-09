import React, { Suspense, lazy, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ArrowRight,
  Box,
  Check,
  ChevronRight,
  CircleHelp,
  Clock,
  Database,
  Download,
  FlaskConical,
  Gamepad2,
  GitBranch,
  Globe2,
  Layers3,
  LayoutDashboard,
  LogOut,
  Network,
  Pause,
  Play,
  Plus,
  Radio,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Users,
  X,
  Zap,
} from "lucide-react";
import "./style.css";
import { api } from "./client";
import { LearningCheck } from "./LearningCheck";
import { LearningJourney } from "./LearningJourney";
import { CoachingWorkspace, RoleHome, ScenarioStudio } from "./Hackathon";
import {
  EnvironmentSetup,
  LiveOperations,
  Notifications,
  RoleGuide,
  RunDatasets,
  exerciseTime,
} from "./Experience";

// Heavy visual pages (Three.js, ECharts, Cytoscape) load on demand.
const pick = (loader, name) =>
  lazy(() => loader().then((m) => ({ default: m[name] })));
const labs = () => import("./Labs");
const investigate = () => import("./Investigate");
const MLLab = pick(labs, "MLLab");
const LabCatalog = pick(labs, "LabCatalog");
const DatasetStudio = pick(labs, "DatasetStudio");
const ScenarioGraph = pick(labs, "ScenarioGraph");
const Live3DPanel = pick(investigate, "Live3DPanel");
const EvidenceLocker = pick(investigate, "EvidenceLocker");
const CommanderPanel = pick(investigate, "CommanderPanel");
const DiagnosisPanel = pick(investigate, "DiagnosisPanel");
const ScorecardPanel = pick(investigate, "ScorecardPanel");
const SignalsPanel = pick(investigate, "SignalsPanel");
const RolesMatrix = pick(investigate, "RolesMatrix");
const Loading = () => <p className="muted padded">Loading visual workspace…</p>;

const money = (v) => Math.round(v || 0).toLocaleString();
const stamp = (v) => new Date(v * 1000).toLocaleString();
const labels = {
  overview: "Overview",
  catalog: "Scenario library",
  runs: "Simulation runs",
  training: "Training datasets",
  designer: "Scenario Lab",
  assignments: "Assignments & coaching",
  lab: "Generator lab",
  connectors: "Local integrations",
  audit: "Activity & audit",
  world: "Simulation workspace",
  dataset: "Training workspace",
  mllab: "ML failure lab",
  studio: "Dataset studio",
  graph: "Scenario graph",
  factory: "SOP factory",
  sandbox: "Codex sandbox",
};
const LIST_PATHS = {
  runs: "/runs",
  training: "/datasets",
  preparations: "/preparations",
  audit: "/audit",
};
const icons = {
  overview: LayoutDashboard,
  catalog: Layers3,
  runs: Activity,
  training: Database,
  designer: GitBranch,
  lab: FlaskConical,
  connectors: Network,
  audit: ShieldCheck,
  assignments: Users,
  mllab: Sparkles,
  studio: Database,
  graph: Network,
  factory: Settings2,
  sandbox: Zap,
};
const AUTHOR_VIEWS = ["designer", "sandbox"],
  MANAGER_VIEWS = ["factory", "lab", "connectors", "audit"];
const canOpen = (v, role) =>
  Object.hasOwn(labels, v) &&
  !["world", "dataset"].includes(v) &&
  (!AUTHOR_VIEWS.includes(v) || role === "admin") &&
  (!MANAGER_VIEWS.includes(v) || role === "admin");
// Hash routes give every page an address, so browser Back/Forward and reloads work:
// #/runs, #/runs/<run id> (or #/assignments/<run id>), #/training/<dataset id>, #/mllab/<lab id>.
function routeFor({ view, parent, run, dataset, openLab, libraryMode }) {
  if (view === "world" && run)
    return `#/${parent}/${encodeURIComponent(run.id)}`;
  if (view === "dataset" && dataset)
    return `#/training/${encodeURIComponent(dataset.id)}`;
  if (view === "mllab" && openLab)
    return `#/mllab/${encodeURIComponent(openLab)}`;
  if (view === "catalog" && libraryMode !== "all")
    return `#/catalog/${libraryMode}`;
  return `#/${view}`;
}
function parseRoute(hash) {
  try {
    const [section = "", id = ""] = hash
      .replace(/^#\/?/, "")
      .split("/")
      .map(decodeURIComponent);
    return { section, id };
  } catch {
    return { section: "", id: "" };
  }
}
function Breadcrumbs({ trail }) {
  return (
    <nav className="breadcrumbs" aria-label="Breadcrumb">
      <ol>
        {trail.map((c, i) => (
          <li key={c.label + i}>
            {i > 0 && <ChevronRight size={14} aria-hidden="true" />}
            {c.onClick && i < trail.length - 1 ? (
              <button
                type="button"
                onClick={c.onClick}
                aria-label={"Back to " + c.label}
                title={"Back to " + c.label}
              >
                {c.label}
              </button>
            ) : (
              <strong aria-current="page">{c.label}</strong>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
const worldIcon = (s) =>
  s.category === "Agentic Simulation Lab"
    ? Gamepad2
    : s.category === "Security & Governance"
      ? ShieldCheck
      : Globe2;
function Badge({ children, tone = "" }) {
  return <span className={"badge " + tone}>{children}</span>;
}
function Metric({ label, value, sub, icon: Icon = Activity }) {
  return (
    <div className="metric">
      <div className="metric-top">
        {label}
        <Icon size={16} />
      </div>
      <strong>{value}</strong>
      <small>{sub}</small>
    </div>
  );
}
function Empty({ title = "Nothing here yet", children }) {
  return (
    <div className="empty">
      <Box size={34} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
function Table({ rows }) {
  if (!rows?.length)
    return (
      <Empty title="No records">
        Records will appear as this simulation progresses.
      </Empty>
    );
  const keys = [...new Set(rows.flatMap(Object.keys))];
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {keys.map((k) => (
              <th key={k}>{k.replaceAll("_", " ")}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.id || i}>
              {keys.map((k) => (
                <td key={k}>
                  {typeof r[k] === "object"
                    ? JSON.stringify(r[k])
                    : String(r[k] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function Chart({ history }) {
  if (!history?.length) return null;
  const last = Math.max(1, history.at(-1).tick);
  const pts = history
    .map((h) => `${24 + (h.tick / last) * 732},${130 - h.service}`)
    .join(" ");
  return (
    <div className="chart">
      <svg
        viewBox="0 0 780 165"
        role="img"
        aria-label="Service health over simulated time"
      >
        <defs>
          <linearGradient id="chart-fill" x1="0" x2="0" y1="0" y2="1">
            <stop stopColor="#7c6ff5" stopOpacity=".3" />
            <stop offset="1" stopColor="#7c6ff5" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[30, 80, 130].map((y, i) => (
          <g key={y}>
            <line x1="24" y1={y} x2="756" y2={y} stroke="#e9ebf2" />
            <text x="0" y={y + 4} fontSize="9" fill="#8a90a6">
              {100 - i * 50}
            </text>
          </g>
        ))}
        <polygon points={`24,130 ${pts} 756,130`} fill="url(#chart-fill)" />
        <polyline points={pts} fill="none" stroke="#7962df" strokeWidth="2.5" />
        <text x="24" y="153" fontSize="10" fill="#8a90a6">
          0m
        </text>
        <text x="727" y="153" fontSize="10" fill="#8a90a6">
          {last}m
        </text>
      </svg>
    </div>
  );
}
function WorldGraph({ nodes, edges, snapshot, onNode }) {
  const positions = {};
  nodes.forEach(
    (n, i) =>
      (positions[n.id] = {
        x: 100 + (i % 3) * 240,
        y: 70 + Math.floor(i / 3) * 145,
      }),
  );
  const height = Math.ceil(nodes.length / 3) * 145;
  return (
    <div className="world-graph">
      <svg
        viewBox={`0 0 700 ${height}`}
        role="img"
        aria-label="Causal system dependency graph"
      >
        <defs>
          <marker
            id="arrow"
            markerWidth="7"
            markerHeight="7"
            refX="6"
            refY="3.5"
            orient="auto"
          >
            <path d="M0 0 L7 3.5 L0 7" fill="#b2b8c9" />
          </marker>
        </defs>
        {edges.map((e, i) => {
          const a = positions[e.source],
            b = positions[e.target];
          return a && b ? (
            <path
              key={i}
              d={`M${a.x} ${a.y + 28} C${a.x} ${a.y + 70},${b.x} ${b.y - 70},${b.x} ${b.y - 30}`}
              stroke="#c9cedc"
              fill="none"
              strokeWidth="1.5"
              markerEnd="url(#arrow)"
            />
          ) : null;
        })}
        {nodes.map((n) => {
          const { x, y } = positions[n.id],
            health = snapshot?.health?.[n.id] ?? n.health ?? 100;
          const color =
            health < 40 ? "#e87572" : health < 75 ? "#d9a04b" : "#43a88a";
          return (
            <g key={n.id} className="graph-node" onClick={() => onNode?.(n)}>
              <rect
                x={x - 93}
                y={y - 30}
                width="186"
                height="63"
                rx="12"
                fill="white"
                stroke={color}
                strokeOpacity=".65"
              />
              <circle cx={x - 75} cy={y - 10} r="4" fill={color} />
              <text x={x - 63} y={y - 6} fontSize="10" fill="#29314e">
                {n.label.length > 24 ? n.label.slice(0, 22) + "…" : n.label}
              </text>
              <text x={x - 75} y={y + 15} fontSize="10" fill="#8a90a6">
                {n.role}
              </text>
              <text
                x={x + 75}
                y={y + 15}
                textAnchor="end"
                fontSize="11"
                fontWeight="600"
                fill={color}
              >
                {Math.round(health)}%
              </text>
            </g>
          );
        })}
      </svg>
      <div className="graph-legend">
        <span>
          <i className="dot green" /> Healthy
        </span>
        <span>
          <i className="dot amber" /> Degraded
        </span>
        <span>
          <i className="dot red" /> Critical
        </span>
        <span>Arrows show dependencies</span>
      </div>
    </div>
  );
}
function LoginScreen({ onLogin, mode }) {
  const [username, setUsername] = useState("admin"),
    [password, setPassword] = useState(mode === "production" ? "" : "admin123"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      onLogin(await api("/auth/login", { username, password }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-page">
      <div className="login-story">
        <div className="brand">
          <div className="brand-mark">
            <Layers3 />
          </div>
          SimForge<span>AI</span>
        </div>
        <Badge tone="dark">THE SIMULATION STUDIO</Badge>
        <h1>
          Complex worlds.
          <br />
          Real decisions.
          <br />
          <em>Safe mock-data practice.</em>
        </h1>
        <p>
          Explore cascading failures, coordinate specialist agents, and discover
          what your next decision changes.
        </p>
        <div className="login-features">
          <span>
            <GitBranch size={17} /> Causal worlds
          </span>
          <span>
            <Gamepad2 size={17} /> Agentic Simulation Lab
          </span>
          <span>
            <ShieldCheck size={17} /> Synthetic data
          </span>
        </div>
        <div className="orb orb-a" />
        <div className="orb orb-b" />
      </div>
      <div className="login-form">
        <div className="form-wrap">
          <span className="eyebrow">WELCOME TO YOUR WORKSPACE</span>
          <h2>Enter the studio</h2>
          <p className="muted">Your next scenario is waiting.</p>
          <div className="login-roles">
            <p>
              <strong>Admin / Trainer</strong> creates, checks and publishes
              scenarios, assigns exercises and observes results.
            </p>
            <p>
              <strong>Learner</strong> practises with generated data and live
              simulations.
            </p>
          </div>
          {mode !== "production" && (
            <div className="role-picker">
              {["admin", "learner"].map((r) => (
                <button
                  key={r}
                  type="button"
                  className={username === r ? "selected" : ""}
                  onClick={() => {
                    setUsername(r);
                    setPassword(r + "123");
                  }}
                >
                  {r}
                </button>
              ))}
            </div>
          )}
          <form onSubmit={submit}>
            <label>
              Username
              <input
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </label>
            {error && <p className="error">{error}</p>}
            <button className="primary full" disabled={busy}>
              {busy ? "Signing in…" : "Open workspace"}
              <ArrowRight size={17} />
            </button>
          </form>
          <div className="login-note">
            <ShieldCheck size={16} />
            {mode === "production"
              ? "Use the account created by your administrator."
              : "Local development accounts. All scenario records are synthetic."}
          </div>
        </div>
      </div>
    </div>
  );
}

function App() {
  const [user, setUser] = useState(null),
    [ready, setReady] = useState(false),
    [mode, setMode] = useState("development"),
    [view, setView] = useState("overview"),
    [items, setItems] = useState([]),
    [mlCatalog, setMlCatalog] = useState([]),
    [overview, setOverview] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [selected, setSelected] = useState(null),
    [run, setRun] = useState(null),
    [dataset, setDataset] = useState(null),
    [lists, setLists] = useState({
      runs: [],
      training: [],
      preparations: [],
      audit: [],
    }),
    [listStates, setListStates] = useState({}),
    [filter, setFilter] = useState("All scenarios"),
    [query, setQuery] = useState(""),
    [toast, setToast] = useState(""),
    [openLab, setOpenLab] = useState(null),
    [libraryMode, setLibraryMode] = useState("all"),
    // The list a simulation run was opened from ("runs" or "assignments"), shown in the breadcrumb.
    [parent, setParent] = useState("runs"),
    [routed, setRouted] = useState(false),
    [routeVersion, setRouteVersion] = useState(0);
  const replaceRoute = useRef(false);
  const lastBrowserHash = useRef(null);
  // Lists have different schemas. Keep their caches separate, and accept only
  // the latest response for each page (also invalidated on logout).
  const listRequests = useRef({});
  const listSequence = useRef(0);
  useEffect(() => {
    Promise.all([
      api("/health").then((x) => setMode(x.mode)),
      api("/auth/me")
        .then(setUser)
        .catch(() => {}),
    ]).finally(() => setReady(true));
  }, []);
  useEffect(() => {
    if (!user) return;
    lastBrowserHash.current = window.location.hash;
    loadHome();
    applyRoute(window.location.hash, true).finally(() => setRouted(true));
    const onPop = () => {
      if (lastBrowserHash.current === window.location.hash) return;
      lastBrowserHash.current = window.location.hash;
      applyRoute(window.location.hash);
    };
    window.addEventListener("popstate", onPop);
    window.addEventListener("hashchange", onPop);
    return () => {
      window.removeEventListener("popstate", onPop);
      window.removeEventListener("hashchange", onPop);
    };
  }, [user]);
  const route = routeFor({
    view,
    parent,
    run,
    dataset,
    openLab,
    libraryMode,
  });
  useEffect(() => {
    if (!routed || route === window.location.hash) return;
    const method =
      replaceRoute.current || !window.location.hash
        ? "replaceState"
        : "pushState";
    replaceRoute.current = false;
    window.history[method](null, "", route);
    lastBrowserHash.current = route;
  }, [route, routed, routeVersion]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 5000);
    return () => clearTimeout(timer);
  }, [toast]);
  async function act(fn) {
    setBusy(true);
    setError("");
    try {
      return await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function signOut() {
    await act(async () => {
      await api("/auth/logout", {});
      setRouted(false);
      setSelected(null);
      setRun(null);
      setDataset(null);
      setOpenLab(null);
      setLibraryMode("all");
      setItems([]);
      setMlCatalog([]);
      listRequests.current = {};
      setLists({ runs: [], training: [], preparations: [], audit: [] });
      setListStates({});
      setOverview(null);
      setToast("");
      setQuery("");
      setFilter("All scenarios");
      setView("overview");
      window.history.replaceState(null, "", "#/overview");
      setUser(null);
    });
  }
  async function loadHome() {
    await act(async () => {
      const [s, o, ml] = await Promise.all([
        api("/scenarios"),
        api("/overview"),
        api("/mllab/catalog"),
      ]);
      setItems(s);
      setMlCatalog(ml.scenarios);
      setOverview(o);
    });
  }
  async function loadList(next) {
    if (next === "training") loadList("preparations");
    if (!LIST_PATHS[next]) return;
    const request = ++listSequence.current;
    listRequests.current[next] = request;
    setListStates((current) => ({
      ...current,
      [next]: { loading: true, error: "" },
    }));
    try {
      const rows = await api(LIST_PATHS[next]);
      if (listRequests.current[next] !== request) return;
      setLists((current) => ({ ...current, [next]: rows }));
      setListStates((current) => ({
        ...current,
        [next]: { loading: false, error: "" },
      }));
    } catch (e) {
      if (listRequests.current[next] !== request) return;
      setListStates((current) => ({
        ...current,
        [next]: { loading: false, error: e.message },
      }));
    }
  }
  async function go(next, tab) {
    if (next === "factory") {
      next = "designer";
    } else if (next === "sandbox") {
      next = "designer";
    } else if (next === "mllab") {
      next = "catalog";
      tab = "ml";
      setOpenLab(null);
    }
    if (!canOpen(next, user.role)) next = "overview";
    if (next === "catalog")
      setLibraryMode(["business", "data", "ml"].includes(tab) ? tab : "all");
    setView(next);
    setError("");
    if (next === "mllab") setOpenLab(null);
    if (next === "overview" || next === "catalog") loadHome();
    await loadList(next);
  }
  function openTrainingLibrary() {
    setFilter("Training library");
    setQuery("");
    go("catalog", "data");
  }
  // Show the page a URL names (initial load, reload, browser Back/Forward).
  async function applyRoute(hash, initial = false) {
    try {
      const { section, id } = parseRoute(hash);
      if (
        ["factory", "sandbox"].includes(section) ||
        (section === "mllab" && !id)
      ) {
        replaceRoute.current = true;
        await go(canOpen(section, user?.role) ? section : "overview");
        return;
      }
      const target = canOpen(section, user?.role) ? section : "overview";
      setError("");
      const coachingSection =
        target === "assignments" && ["review", "sop"].includes(id);
      if (
        id &&
        !coachingSection &&
        ["runs", "assignments", "training"].includes(target)
      ) {
        const opened = await act(async () => {
          if (target === "training") {
            setDataset(await api("/datasets/" + encodeURIComponent(id)));
            setView("dataset");
          } else {
            setRun(await api("/runs/" + encodeURIComponent(id)));
            setParent(target);
            setView("world");
          }
          return true;
        });
        if (opened) return;
        replaceRoute.current = true; // the item is gone: show its list instead
      }
      setOpenLab(target === "mllab" && id ? id : null);
      setLibraryMode(
        target === "catalog" && ["business", "data", "ml"].includes(id)
          ? id
          : "all",
      );
      setView(target);
      if (target === "overview" && !initial) loadHome();
      await loadList(target);
    } finally {
      // Normalize aliases even when they resolve to the already-open page.
      setRouteVersion((version) => version + 1);
    }
  }
  async function launchLegacy(spec) {
    await act(async () => {
      const d = await api("/datasets", {
        scenario_key: spec.key,
        seed: 2026,
        scale: 1,
      });
      setDataset(d);
      setView("dataset");
      setSelected(null);
    });
  }
  async function openScenario(key) {
    if (String(key).startsWith("draft:")) {
      await go(user.role === "admin" ? "designer" : "assignments", "review");
      return;
    }
    const all = await api("/scenarios");
    setItems(all);
    const found = all.find((s) => s.key === key);
    if (!found) throw new Error("This scenario is no longer available");
    setSelected(found);
  }
  async function openRun(id) {
    // The admin observes, while only the owning learner can change this run.
    // Runs opened from Assignments & coaching lead back there; forks/handoffs keep their parent.
    const from =
      view === "assignments"
        ? "assignments"
        : view === "world"
          ? parent
          : "runs";
    await act(async () => {
      setRun(await api("/runs/" + id));
      setParent(from);
      setView("world");
    });
  }
  const canAuthor = user?.role === "admin";
  async function openPrepared(id) {
    await act(async () => {
      const prepared = await api("/preparations/" + encodeURIComponent(id));
      const all = await api("/scenarios");
      const spec =
        all.find((s) => s.key === prepared.scenario_key) || prepared.scenario;
      if (!spec) throw new Error("This scenario is no longer available");
      setSelected({ ...spec, prepared });
    });
  }
  const canManage = user?.role === "admin";
  if (!ready)
    return (
      <div className="boot">
        <Layers3 size={32} />
        <span>Opening SimForge-AI…</span>
      </div>
    );
  if (!user) return <LoginScreen onLogin={setUser} mode={mode} />;
  // Detail pages belong to a list: highlight it in the sidebar and link back to it.
  const section =
    view === "world"
      ? parent
      : view === "dataset"
        ? "training"
        : view === "mllab"
          ? "catalog"
          : view;
  const navLabel = (key) =>
    key === "assignments"
      ? user.role === "learner"
        ? "My training"
        : "Assignments & results"
      : labels[key];
  const pageList = lists[view] || [];
  const trail = [{ label: "Workspace", onClick: () => go("overview") }];
  if (view === "world" && run)
    trail.push(
      { label: labels[parent], onClick: () => go(parent) },
      { label: run.title },
    );
  else if (view === "dataset" && dataset)
    trail.push(
      { label: labels.training, onClick: () => go("training") },
      { label: dataset.title },
    );
  else if (view === "mllab" && openLab)
    trail.push(
      { label: labels.catalog, onClick: () => go("catalog", "ml") },
      { label: "Challenge" },
    );
  else trail.push({ label: labels[view] });
  const libraryItems = [
    ...items,
    ...mlCatalog.map((s) => ({
      ...s,
      key: `ml:${s.key}`,
      scenario_key: s.key,
      kind: "ml",
      summary: s.story,
      category: s.group,
    })),
  ];
  const filtered = libraryItems.filter(
    (s) =>
      (libraryMode === "all" ||
        (libraryMode === "business"
          ? s.kind === "world"
          : s.kind === "training")) &&
      (filter === "All scenarios" ||
        (filter === "Training library"
          ? s.kind === "training"
          : s.category === filter)) &&
      [s.title, s.summary, s.category]
        .join(" ")
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  function scenarioCard(s) {
    const Icon = s.kind === "ml" ? FlaskConical : worldIcon(s);
    return (
      <button
        className={"scenario-card " + (s.kind === "world" ? "world" : "")}
        key={s.key}
        onClick={() =>
          s.kind === "ml"
            ? act(async () => {
                const lab = await api("/mllab/labs", {
                  scenario_key: s.scenario_key,
                  seed: 2026,
                });
                setOpenLab(lab.id);
                setView("mllab");
              })
            : setSelected(s)
        }
      >
        <div className="card-top">
          <div
            className={
              "scenario-icon " +
              (s.category === "Agentic Simulation Lab"
                ? "purple"
                : s.category === "Security & Governance"
                  ? "teal"
                  : "blue")
            }
          >
            <Icon size={23} />
          </div>
          <Badge>
            {s.kind === "ml"
              ? "ML INVESTIGATION"
              : s.kind === "training"
                ? "LIVE OR HISTORICAL CASE"
                : "LIVE SIMULATION"}
          </Badge>
        </div>
        <div className="category-label">{s.category}</div>
        <h3>{s.title}</h3>
        <p>{s.summary}</p>
        <small className="card-mission">
          Your role: {s.kind === "ml" ? "ML investigator" : s.briefing?.role}
        </small>
        <div className="card-bottom">
          <span>
            {s.kind === "ml"
              ? "Starting check · Model evidence · Post-check"
              : s.kind === "training"
                ? "Starting check · Live or historical case · Post-check"
                : "Starting check · Live decisions · Post-check"}
          </span>
          <ArrowRight size={17} />
        </div>
      </button>
    );
  }
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Layers3 size={22} />
          </div>
          SimForge<span>AI</span>
        </div>
        <div className="workspace-name">
          <div className="workspace-avatar">S</div>
          <div>
            Simulation studio<small>Local workspace</small>
          </div>
          <ChevronRight size={15} />
        </div>
        <div className="sidebar-menu">
          <span className="nav-label">{user.role.toUpperCase()} WORKSPACE</span>
          <nav aria-label="Main navigation">
            {[
              "overview",
              ...(canAuthor ? ["designer"] : []),
              "catalog",
              "assignments",
              "runs",
              "training",
            ].map((key) => {
              const Icon = icons[key];
              return (
                <button
                  key={key}
                  className={section === key ? "active" : ""}
                  aria-current={section === key ? "page" : undefined}
                  onClick={() => go(key)}
                >
                  <Icon size={18} />
                  {navLabel(key)}
                </button>
              );
            })}
          </nav>
          <details className="advanced-navigation">
            <summary>Advanced tools</summary>
            <nav aria-label="Advanced navigation">
              {[
                "studio",
                "graph",
                ...(canManage ? ["lab", "connectors", "audit"] : []),
              ].map((key) => {
                const Icon = icons[key];
                return (
                  <button
                    key={key}
                    className={section === key ? "active" : ""}
                    aria-current={section === key ? "page" : undefined}
                    onClick={() => go(key)}
                  >
                    <Icon size={18} />
                    {labels[key]}
                  </button>
                );
              })}
            </nav>
          </details>
        </div>
        <div className="sidebar-footer">
          <div className="runtime-indicator">
            <i className="dot green" />
            CPU engine online<small>Python · SQLite · Local agents</small>
          </div>
          <div className="profile">
            <div className="avatar">{user.name[0]}</div>
            <div>
              {user.name}
              <small>{user.role}</small>
            </div>
          </div>
          <button
            className="secondary full logout-button"
            aria-label="Log out"
            disabled={busy}
            onClick={signOut}
          >
            <LogOut size={16} />
            <span>Log out</span>
          </button>
        </div>
      </aside>
      <div className="main-shell">
        <header>
          <Breadcrumbs trail={trail} />
          <div className="header-right">
            <Notifications key={user.id} onOpen={openScenario} />
            <Badge tone="green">
              <i className="dot green" />
              Local environment
            </Badge>
            <span className="header-divider" />
            <CircleHelp size={18} />
            <div className="avatar small">{user.name[0]}</div>
            <button
              className="secondary logout-button"
              disabled={busy}
              onClick={signOut}
            >
              <LogOut size={16} />
              Log out
            </button>
          </div>
        </header>
        <main>
          <RoleGuide role={user.role} />
          <Suspense fallback={null}>
            <RolesMatrix />
          </Suspense>
          {error && (
            <div className="error-banner" role="alert">
              {error}
              <button onClick={() => setError("")} aria-label="Dismiss error">
                <X size={16} />
              </button>
            </div>
          )}
          {view === "overview" && (
            <RoleHome
              key={user.id}
              user={user}
              overview={overview}
              scenarios={items}
              onNavigate={go}
              onScenario={setSelected}
            />
          )}
          {view === "catalog" && (
            <>
              <PageTitle
                title="Scenario library"
                subtitle="Choose a practice format. Each exercise offers a starting and post knowledge check; its practice score still follows its own engine."
              >
                {canAuthor && (
                  <button className="primary" onClick={() => go("designer")}>
                    <Plus size={17} />
                    Create a scenario
                  </button>
                )}
              </PageTitle>
              <div className="library-toolbar">
                <div
                  className="tabs"
                  role="tablist"
                  aria-label="Exercise types"
                >
                  {[
                    ["all", "All exercises"],
                    ["business", "Business simulations"],
                    ["ml", "ML investigations"],
                    ["data", "Data investigations"],
                  ].map(([key, label]) => (
                    <button
                      key={key}
                      role="tab"
                      aria-selected={libraryMode === key}
                      className={libraryMode === key ? "active" : ""}
                      onClick={() => {
                        setQuery("");
                        setFilter(
                          key === "data" ? "Training library" : "All scenarios",
                        );
                        go("catalog", key);
                      }}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <div className="search">
                  <Search size={16} />
                  <input
                    aria-label="Search scenarios"
                    placeholder="Search scenarios…"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                </div>
              </div>
              <section
                className="library-purpose"
                aria-label="What this exercise type teaches"
              >
                <strong>
                  {libraryMode === "ml"
                    ? "Diagnose a broken ML system"
                    : libraryMode === "data"
                      ? "Investigate a historical business case"
                      : libraryMode === "business"
                        ? "Practise decisions in a changing business workflow"
                        : "Choose a simulation, historical case or ML investigation"}
                </strong>
                <p>
                  {libraryMode === "ml"
                    ? "Take a starting check, inspect model evidence, identify hidden drift, leakage or serving faults, apply a fix and compare recovery. Then complete the post-check."
                    : libraryMode === "data"
                      ? "Open the historical assessment from the mission dialog. Take a starting check before inspecting linked mock-data records, submit your evidence-based case, then complete the post-check. There is no simulation clock."
                      : libraryMode === "business"
                        ? "Take a starting check, generate linked datasets, follow live queues, inspect evidence and choose actions. The debrief compares your decisions with the same workload without intervention; finish with a post-check."
                        : "Choose one of three practice formats. The starting and post checks measure knowledge change; each format has its own practice score."}
                </p>
              </section>
              {libraryMode === "ml" ? (
                <Suspense fallback={<Loading />}>
                  <LabCatalog
                    user={user}
                    query={query}
                    onOpen={(id) => {
                      setOpenLab(id);
                      setView("mllab");
                    }}
                  />
                </Suspense>
              ) : (
                <>
                  <div className="filters">
                    {[
                      "All scenarios",
                      ...new Set(
                        items
                          .filter((s) => s.kind === "world")
                          .map((s) => s.category),
                      ),
                      "Training library",
                    ]
                      .filter(
                        (label) =>
                          libraryMode !== "data" ||
                          label === "Training library",
                      )
                      .map((label) => (
                        <button
                          className={filter === label ? "active" : ""}
                          key={label}
                          onClick={() => setFilter(label)}
                        >
                          {label}
                        </button>
                      ))}
                  </div>
                  <div className="scenario-grid">
                    {filtered.map(scenarioCard)}
                  </div>
                  {!filtered.length && (
                    <Empty title="No matching scenarios">
                      Try a different search or category.
                    </Empty>
                  )}
                </>
              )}
              <div className="footnote">
                <ShieldCheck size={15} />
                Synthetic data. Illustrative outcomes. No production systems are
                connected.
              </div>
            </>
          )}
          {view === "runs" && (
            <>
              <PageTitle
                title="Your simulation runs"
                subtitle="Resume a world, review its decisions, or compare a new strategy."
              />
              <ListPanel
                state={listStates.runs}
                label="simulation runs"
                onRetry={() => loadList("runs")}
              >
                {pageList.length ? (
                  pageList.map((r) => (
                    <button
                      className="list-row"
                      key={r.id}
                      onClick={() => openRun(r.id)}
                    >
                      <div className="list-icon">
                        <Activity size={19} />
                      </div>
                      <div>
                        <strong>{r.title}</strong>
                        <small>
                          Seed {r.seed} · {r.population} entities ·{" "}
                          {stamp(r.created)}
                        </small>
                      </div>
                      <Badge tone={r.status === "completed" ? "green" : ""}>
                        {r.status}
                      </Badge>
                      <span>
                        {r.tick} of {r.horizon} simulated minutes
                      </span>
                      <ChevronRight size={18} />
                    </button>
                  ))
                ) : (
                  <Empty title="Your first world awaits">
                    Start a simulation from the scenario library.
                  </Empty>
                )}
              </ListPanel>
            </>
          )}
          {view === "training" && (
            <>
              <PageTitle
                title="Training datasets"
                subtitle="Generated on demand, then saved: linked scenario datasets and historical case files. New published scenarios create fresh mock-data environments when learners launch them."
              >
                <button className="secondary" onClick={openTrainingLibrary}>
                  <Layers3 size={16} />
                  Browse the {
                    items.filter((s) => s.kind === "training").length
                  }{" "}
                  training cases
                </button>
              </PageTitle>
              <section
                className="panel purpose"
                aria-label="What training datasets are for"
              >
                <ol className="how-steps">
                  <li>
                    <strong>Generate a case file</strong>
                    <span>
                      Pick a case in the Scenario library's{" "}
                      <em>Training library</em> (sales decline, payment fraud,
                      AML monitoring, SLA breach…) and choose{" "}
                      <em>Open historical case assessment</em>. SimForge builds
                      related tables (customers, orders, invoices, tickets…)
                      from a seed and plants one hidden pattern.
                    </span>
                  </li>
                  <li>
                    <strong>Investigate the records</strong>
                    <span>
                      Page through each table here, or download the CSV bundle
                      for Excel, SQL or pandas.
                    </span>
                  </li>
                  <li>
                    <strong>Make your case</strong>
                    <span>
                      Choose the root cause, cite the evidence (IDs, regions,
                      fields) and recommend an action. Scored out of 100: root
                      cause 55, evidence 25, recommendation 20.
                    </span>
                  </li>
                </ol>
                <p className="muted">
                  Unlike <b>Simulation runs</b> (live worlds where you act over
                  time), there is no clock: it is a data investigation.{" "}
                  <b>Dataset studio</b> is for designing your own datasets and
                  schemas; the <b>ML failure lab</b> is for debugging a deployed
                  model.
                </p>
              </section>
              <ListPanel
                state={listStates.training}
                label="training datasets"
                onRetry={() => loadList("training")}
              >
                {pageList.length ? (
                  pageList.map((d) => (
                    <button
                      className="list-row"
                      key={d.id}
                      onClick={() => {
                        setDataset(d);
                        setView("dataset");
                      }}
                    >
                      <div className="list-icon">
                        <Database size={18} />
                      </div>
                      <div>
                        <strong>{d.title}</strong>
                        <small>
                          {Object.keys(d.tables).length} tables · Seed{" "}
                          {d.meta.seed}
                        </small>
                      </div>
                      <Badge>{d.assessments.length} assessments</Badge>
                      <ChevronRight size={18} />
                    </button>
                  ))
                ) : (
                  <Empty title="No case files yet">
                    Open a case from the Training library and generate its
                    records.
                    <br />
                    <button className="primary" onClick={openTrainingLibrary}>
                      Open the Training library
                      <ArrowRight size={16} />
                    </button>
                  </Empty>
                )}
              </ListPanel>
              <section
                aria-label="Scenario-generated datasets"
                className="panel padded"
              >
                <h2>Scenario-generated datasets</h2>
                <p>
                  Each new scenario generates its own linked workload when you
                  choose Generate scenario datasets. Saved environments can be
                  reopened here and reused for a reproducible simulation. Live
                  telemetry grows as a run advances.
                </p>
                <ListPanel
                  state={listStates.preparations}
                  label="scenario datasets"
                  onRetry={() => loadList("preparations")}
                >
                  {lists.preparations.length ? (
                    lists.preparations.map((prepared) => (
                      <button
                        className="list-row"
                        key={prepared.id}
                        onClick={() => openPrepared(prepared.id)}
                      >
                        <Database size={18} />
                        <div>
                          <strong>{prepared.title}</strong>
                          <small>
                            {Object.keys(prepared.tables).length} linked tables
                            · {prepared.population} work items · Seed{" "}
                            {prepared.seed}
                          </small>
                        </div>
                        <Badge>
                          {prepared.owner === user.id
                            ? "Inspect / run"
                            : "Inspect only"}
                        </Badge>
                        <ChevronRight size={18} />
                      </button>
                    ))
                  ) : (
                    <p>
                      No scenario environments generated yet. Open any published
                      scenario in Scenario library and generate its datasets.
                    </p>
                  )}
                </ListPanel>
              </section>
            </>
          )}
          {view === "world" && run && (
            <World
              run={run}
              setRun={setRun}
              act={act}
              busy={busy}
              toast={setToast}
              user={user}
              onOpenRun={openRun}
              onOpenLab={(id) => {
                setOpenLab(id);
                setView("mllab");
              }}
            />
          )}
          {view === "dataset" && dataset && (
            <Dataset
              key={dataset.id}
              data={dataset}
              user={user}
              onUpdated={setDataset}
              act={act}
              busy={busy}
            />
          )}
          {view === "designer" && canAuthor && (
            <ScenarioStudio
              user={user}
              Graph={WorldGraph}
              onPublished={async (published) => {
                await loadHome();
                setToast(
                  published
                    ? "Scenario published. Learners have been notified."
                    : "Scenario library refreshed.",
                );
              }}
            />
          )}
          {view === "assignments" && (
            <CoachingWorkspace
              user={user}
              scenarios={items}
              onOpen={openScenario}
              onRun={openRun}
            />
          )}
          <Suspense fallback={<Loading />}>
            {view === "mllab" && (
              <MLLab
                user={user}
                openLab={openLab}
                setOpenLab={setOpenLab}
                onCatalog={() => go("catalog", "ml")}
              />
            )}
            {view === "studio" && <DatasetStudio scenarios={items} />}
            {view === "graph" && (
              <ScenarioGraph onOpenScenario={openScenario} />
            )}
          </Suspense>
          {view === "lab" && <Lab act={act} busy={busy} />}
          {view === "connectors" && <Connectors act={act} busy={busy} />}
          {view === "audit" && (
            <>
              <PageTitle
                title="Activity & audit"
                subtitle="A local record of sign-ins, datasets, simulation decisions and exports."
              />
              <ListPanel
                state={listStates.audit}
                label="audit records"
                onRetry={() => loadList("audit")}
              >
                <Table
                  rows={pageList.map((x) => ({
                    ...x,
                    created: stamp(x.created),
                  }))}
                />
              </ListPanel>
            </>
          )}
        </main>
        <footer>
          SimForge-AI <span>CPU-first simulation studio · v2.0</span>
          <span>Built for decisions that matter.</span>
        </footer>
      </div>
      {busy && (
        <div className="working">
          <span className="spinner" />
          Working locally…
        </div>
      )}
      {toast && (
        <div className="toast">
          <Check size={17} />
          {toast}
        </div>
      )}
      {selected && (
        <EnvironmentSetup
          key={selected.prepared?.id || selected.key}
          scenario={selected}
          initialPrepared={selected.prepared}
          readOnly={!!selected.prepared && selected.prepared.owner !== user.id}
          onClose={() => setSelected(null)}
          onLegacy={launchLegacy}
          onReady={(r) => {
            setRun(r);
            setParent("runs");
            setView("world");
            setSelected(null);
          }}
        />
      )}
    </div>
  );
}
function ListPanel({ state, label, onRetry, children }) {
  return (
    <div className="panel" aria-busy={state?.loading || false}>
      {state?.loading ? (
        <p className="muted padded" role="status">
          Loading {label}…
        </p>
      ) : state?.error ? (
        <div className="padded" role="alert">
          <p>
            Could not load {label}: {state.error}
          </p>
          <button className="secondary" onClick={onRetry}>
            Try again
          </button>
        </div>
      ) : (
        children
      )}
    </div>
  );
}
function PageTitle({ title, subtitle, children }) {
  return (
    <div className="page-heading">
      <div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      {children}
    </div>
  );
}

function World({ run, setRun, act, busy, toast, user, onOpenRun, onOpenLab }) {
  const [tab, setTab] = useState("World map"),
    [agents, setAgents] = useState([]),
    [report, setReport] = useState(null),
    [replay, setReplay] = useState(null),
    [node, setNode] = useState(null),
    [playbackError, setPlaybackError] = useState("");
  const observing = run.owner !== user.id;
  useEffect(() => {
    if ((!run.clock?.running && !observing) || busy) return;
    let active = true,
      timer;
    async function poll() {
      try {
        const next = await api(`/runs/${run.id}?role=${run.role}`);
        if (active) {
          setRun(next);
          setPlaybackError("");
        }
      } catch (e) {
        if (active) setPlaybackError(e.message);
      }
      if (active) timer = setTimeout(poll, 1000);
    }
    timer = setTimeout(poll, 800);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [run.id, run.clock?.running, run.role, observing, busy]);
  async function playback(command, speed = run.clock?.speed || 1) {
    await act(async () => {
      const latest = await api(`/runs/${run.id}?role=${run.role}`);
      setRun(
        await api(`/runs/${run.id}/playback`, {
          command,
          speed: Number(speed),
          version: latest.version,
          role: run.role,
        }),
      );
    });
  }
  useEffect(() => {
    setAgents([]);
    setReport(null);
    setReplay(null);
  }, [run.id, run.tick, run.version]);
  const m = run.metrics,
    complete = run.tick >= run.horizon;
  async function advance(ticks) {
    await act(async () => {
      const latest = await api(`/runs/${run.id}?role=${run.role}`);
      setRun(
        await api(`/runs/${run.id}/advance`, {
          ticks,
          version: latest.version,
          role: run.role,
        }),
      );
    });
  }
  async function finish() {
    await act(async () => {
      let next = await api(`/runs/${run.id}?role=${run.role}`);
      while (next.tick < next.horizon) {
        next = await api(`/runs/${next.id}/advance`, {
          ticks: Math.min(30, next.horizon - next.tick),
          version: next.version,
          role: next.role,
        });
      }
      setRun(next);
      setTab("Debrief");
    });
  }
  async function decide(id) {
    await act(async () => {
      const latest = await api(`/runs/${run.id}?role=${run.role}`);
      setRun(
        await api(`/runs/${run.id}/decisions`, {
          action_id: id,
          version: latest.version,
          role: run.role,
        }),
      );
      toast(
        "Decision committed and exercise paused. Resume playback to observe its effects.",
      );
    });
  }
  useEffect(() => {
    if (tab === "Debrief" && complete)
      act(async () => setReport(await api(`/runs/${run.id}/report`)));
  }, [tab, complete, run.id]);
  const decisionDesk = (
    <section className="panel decision-panel">
      <div className="panel-heading">
        <div>
          <h3>Decision desk</h3>
          <p>Every intervention has a trade-off.</p>
        </div>
        <Settings2 size={19} />
      </div>
      {run.actions.map((a) => {
        const used = run.decisions.some((d) => d.action_id === a.id);
        return (
          <div className="action-card" key={a.id}>
            <div>
              <strong>{a.label}</strong>
              <Badge tone={used ? "green" : ""}>
                {used ? "Committed" : a.effect}
              </Badge>
            </div>
            <p>{a.description}</p>
            <div className="action-meta">
              <span>{money(a.cost)} units</span>
              <span>
                <Clock size={12} />
                {a.duration} simulated minutes to take effect
              </span>
            </div>
            <button
              className="secondary full"
              disabled={
                busy ||
                complete ||
                observing ||
                used ||
                a.cost > m.budget - m.spent
              }
              onClick={() => decide(a.id)}
            >
              {used ? (
                <>
                  <Check size={14} />
                  Committed
                </>
              ) : (
                <>
                  Commit action
                  <ArrowRight size={14} />
                </>
              )}
            </button>
          </div>
        );
      })}
      <p className="tiny decision-note">
        Actions are applied at the current simulation time. Committed choices
        remain in the audit trail.
      </p>
    </section>
  );
  return (
    <>
      <PageTitle
        title={run.title}
        subtitle={`Seed ${run.seed} · ${run.population.toLocaleString()} ${run.unit} · A deterministic, synthetic world`}
      >
        <button
          className="secondary"
          disabled={busy || observing}
          onClick={() =>
            act(async () => {
              setRun(await api(`/runs/${run.id}/fork`, {}));
              setTab("World map");
            })
          }
        >
          <GitBranch size={16} />
          Try another strategy
        </button>
      </PageTitle>
      {observing && (
        <div className="role-guide">
          <strong>Observation mode</strong>
          <p>
            You can inspect this learner’s run but cannot make decisions or
            control their clock.
          </p>
        </div>
      )}
      {playbackError && (
        <p role="alert" className="error-banner">
          Playback connection: {playbackError}
        </p>
      )}
      <LearningJourney
        run={run}
        observing={observing}
        onView={(view) => setTab(view === "Learning" ? "Debrief" : view)}
        onStart={() => playback("play")}
        busy={busy}
      />
      <LearningCheck
        run={run}
        observing={observing}
        expanded={tab === "Debrief" || run.tick === 0}
        onOpen={() => setTab("Debrief")}
        onSaved={async () =>
          setRun(await api(`/runs/${run.id}?role=${run.role}`))
        }
      />
      <div className="run-bar">
        <div className="clock">
          <Radio size={17} />
          <strong>
            {exerciseTime(run.tick)}
            <span>
              {" "}
              · {run.tick} of {run.horizon} simulated minutes
            </span>
          </strong>
          <Badge tone={complete ? "green" : "purple"}>
            {complete ? "Completed" : run.clock?.running ? "Playing" : "Paused"}
          </Badge>
        </div>
        <div className="run-actions">
          <select
            aria-label="Role perspective"
            value={run.role}
            disabled={busy}
            onChange={(e) =>
              act(async () =>
                setRun(await api(`/runs/${run.id}?role=${e.target.value}`)),
              )
            }
          >
            {(
              run.perspectives || [
                { id: "operations", label: "Operations" },
                { id: "investigator", label: "Investigator" },
                { id: "finance", label: "Business" },
              ]
            ).map((p) => (
              <option key={p.id} value={p.id}>
                {p.label} perspective
              </option>
            ))}
          </select>
          <select
            aria-label="Playback speed"
            value={run.clock?.speed || 1}
            disabled={busy || complete || observing}
            onChange={(e) =>
              playback(run.clock?.running ? "play" : "pause", e.target.value)
            }
          >
            <option value="0.25">0.25× · 4 seconds per minute</option>
            <option value="1">1× · 1 second per minute</option>
            <option value="3">3× · 3 minutes per second</option>
          </select>
          <button
            className="primary"
            disabled={busy || complete || observing}
            onClick={() => playback(run.clock?.running ? "pause" : "play")}
          >
            {run.clock?.running ? <Pause size={16} /> : <Play size={16} />}{" "}
            {run.clock?.running ? "Pause simulation" : "Start playback"}
          </button>
          <button
            className="secondary"
            disabled={busy || complete || observing}
            onClick={() => advance(1)}
          >
            <Play size={15} />
            Step one simulated minute
          </button>
          <button
            className="primary"
            disabled={busy || complete || observing}
            onClick={finish}
          >
            Complete run
            <ArrowRight size={15} />
          </button>
        </div>
      </div>
      <p className="clock-explanation">
        Exercise clock starts at 09:00 and ends at {exerciseTime(run.horizon)}.
        One real second = {run.clock?.speed || 1} simulated minute(s). Pausing
        freezes the exercise; closing the page does not pause it.
      </p>
      <div className="metrics four">
        <Metric
          label="Service health"
          value={`${m.service}%`}
          sub="Average system availability"
        />
        <Metric
          label="Work completed"
          value={`${m.completed} / ${m.population}`}
          sub={`${m.late} completed late`}
          icon={Check}
        />
        <Metric
          label="Response budget"
          value={money(m.budget - m.spent)}
          sub={`${money(m.spent)} synthetic units committed`}
          icon={ShieldCheck}
        />
        <Metric
          label="Simulation score"
          value={`${m.score} / 100`}
          sub={`${money(m.loss)} impact units accumulated`}
          icon={Zap}
        />
      </div>
      <div
        className="tabs learner-primary-tabs"
        role="group"
        aria-label="Learning workspace"
      >
        {["World map", "Evidence locker", "Diagnosis", "Debrief"].map((t) => (
          <button
            className={tab === t ? "active" : ""}
            key={t}
            onClick={() => setTab(t)}
          >
            {
              {
                "World map": "Operations",
                "Evidence locker": "Evidence",
                Diagnosis: "Diagnose & act",
                Debrief: "Learning review",
              }[t]
            }
          </button>
        ))}
      </div>
      <details
        className="advanced-simulation-tabs"
        open={[
          "Live datasets",
          "Live 3D",
          "Event timeline",
          "Agent council",
          "Entity data",
        ].includes(tab)}
      >
        <summary>Data & visual tools</summary>
        <div
          className="tabs"
          role="group"
          aria-label="Additional simulation views"
        >
          {[
            "Live datasets",
            "Live 3D",
            "Event timeline",
            "Agent council",
            "Entity data",
          ].map((t) => (
            <button
              key={t}
              className={tab === t ? "active" : ""}
              onClick={() => setTab(t)}
            >
              {t}
            </button>
          ))}
        </div>
      </details>
      {tab === "Live datasets" && <RunDatasets run={run} />}
      <Suspense fallback={<Loading />}>
        {tab === "Live 3D" && <Live3DPanel run={run} />}
        {tab === "Evidence locker" && <EvidenceLocker run={run} />}
        {tab === "Diagnosis" && (
          <div className="workspace-grid diagnosis-workspace">
            <DiagnosisPanel
              run={run}
              setRun={setRun}
              busy={busy}
              observing={observing}
            />
            {decisionDesk}
          </div>
        )}
        {tab === "Agent council" && (
          <CommanderPanel
            run={run}
            decide={decide}
            busy={busy || observing}
            complete={complete}
          />
        )}
        {tab === "Debrief" && complete && (
          <>
            <ScorecardPanel run={run} />
            <SignalsPanel
              run={run}
              onOpenRun={onOpenRun}
              onOpenLab={onOpenLab}
            />
          </>
        )}
      </Suspense>
      {tab === "World map" && (
        <div className="workspace-grid live-workspace">
          <div>
            <LiveOperations run={run} />
            <details className="panel dependency-details">
              <summary>Dependency graph and system details</summary>
              <section>
                <div className="panel-heading">
                  <div>
                    <h3>Connected systems</h3>
                    <p>Select a system to inspect its state.</p>
                  </div>
                  <Badge>{run.nodes.length} nodes</Badge>
                </div>
                <WorldGraph
                  nodes={run.nodes}
                  edges={run.edges}
                  onNode={setNode}
                />
                {node && (
                  <div className="node-detail">
                    <strong>{node.label}</strong>
                    <span>
                      {node.role} · {node.capacity} processing slots ·{" "}
                      {node.health}% health
                    </span>
                    <button
                      onClick={() => setNode(null)}
                      aria-label="Close system details"
                    >
                      <X size={14} />
                    </button>
                  </div>
                )}
              </section>
            </details>
            <section className="panel">
              <div className="panel-heading">
                <h3>Service health over time</h3>
                <Badge>SIMULATED MINUTES</Badge>
              </div>
              <Chart history={run.history} />
            </section>
          </div>
          {decisionDesk}
        </div>
      )}
      {tab === "Event timeline" && (
        <>
          <div className="panel replay-panel">
            <div className="panel-heading">
              <h3>Replay the world</h3>
              <Badge>Minute {replay ?? run.tick}</Badge>
            </div>
            <input
              aria-label="Replay minute"
              type="range"
              min="0"
              max={run.tick}
              value={replay ?? run.tick}
              onChange={(e) => setReplay(Number(e.target.value))}
            />
            <p className="tiny">
              Historical inspection only. Your live decision time remains minute{" "}
              {run.tick}.
            </p>
            <WorldGraph
              nodes={run.nodes}
              edges={run.edges}
              snapshot={run.history.find(
                (h) => h.tick === (replay ?? run.tick),
              )}
            />
          </div>
          <div className="panel">
            <div className="panel-heading">
              <h3>Event ledger</h3>
              <Badge>{run.role} visibility</Badge>
            </div>
            {run.events.filter((e) => e.tick <= (replay ?? run.tick)).length ? (
              run.events
                .filter((e) => e.tick <= (replay ?? run.tick))
                .map((e) => (
                  <div className="event" key={e.id}>
                    <span className="event-time">{exerciseTime(e.tick)}</span>
                    <i
                      className={
                        "dot " +
                        (e.severity === "critical"
                          ? "red"
                          : e.severity === "warning"
                            ? "amber"
                            : "green")
                      }
                    />
                    <div>
                      <strong>{e.message}</strong>
                      <small>
                        {e.kind} · {e.node} · {e.role}
                        {e.cause_id && ` · follows ${e.cause_id}`}
                      </small>
                    </div>
                  </div>
                ))
            ) : (
              <Empty title="The world is quiet">
                Advance time to see incidents and their downstream effects.
              </Empty>
            )}
          </div>
        </>
      )}
      {tab === "Agent council" && (
        <>
          <div className="council-intro">
            <div>
              <h2>Different perspectives. One shared world.</h2>
              <p>
                Three local, rule-based specialists inspect role-visible
                evidence and propose bounded responses.
              </p>
            </div>
            <button
              className="primary"
              disabled={busy}
              onClick={() =>
                act(async () =>
                  setAgents(await api(`/runs/${run.id}/agents`, {})),
                )
              }
            >
              <Users size={17} />
              Convene council
            </button>
          </div>
          <div className="agent-grid">
            {agents.map((a) => (
              <section className="panel agent" key={a.role}>
                <div className="agent-avatar">
                  <Users size={25} />
                </div>
                <h3>{a.agent}</h3>
                <Badge tone="purple">{a.mode}</Badge>
                <div className="workflow">
                  {a.workflow.map((s, i) => (
                    <div className="workflow-step" key={s.step}>
                      <span className={s.status === "waiting" ? "waiting" : ""}>
                        {s.status === "waiting" ? (
                          <Pause size={11} />
                        ) : (
                          <Check size={11} />
                        )}
                      </span>
                      <div>
                        <strong>{s.step}</strong>
                        <small>{s.detail}</small>
                      </div>
                    </div>
                  ))}
                </div>
                <p className="tiny">
                  Evidence:{" "}
                  {a.evidence_ids.join(", ") || "No incident evidence yet"}
                </p>
                {a.proposals.map((p) => (
                  <div className="proposal" key={p.action_id}>
                    <strong>{p.label}</strong>
                    <p>{p.reason}</p>
                    <button
                      className="secondary full"
                      disabled={
                        busy ||
                        complete ||
                        !p.approved_by_policy ||
                        run.decisions.some((d) => d.action_id === p.action_id)
                      }
                      onClick={() => decide(p.action_id)}
                    >
                      Commit · {money(p.cost)} units
                    </button>
                  </div>
                ))}
              </section>
            ))}
          </div>
          {!agents.length && (
            <Empty title="Your specialists are ready">
              Convene the council after an incident to compare evidence and
              recommendations. No API key or model download is used.
            </Empty>
          )}
        </>
      )}
      {tab === "Entity data" && (
        <div className="panel">
          <div className="panel-heading">
            <h3>Work item ledger</h3>
            <Badge>First 200 of {run.entities.length}</Badge>
          </div>
          <Table rows={run.entities.slice(0, 200)} />
        </div>
      )}
      {tab === "Debrief" &&
        (report ? (
          <>
            <div className="debrief">
              <div className="debrief-icon">
                <ShieldCheck size={32} />
              </div>
              <div>
                <span className="eyebrow">GROUND TRUTH REVEALED</span>
                <h2>{report.ground_truth.cause}</h2>
                <p>
                  Incident began at minute {report.ground_truth.onset} in{" "}
                  {report.ground_truth.root}.
                </p>
              </div>
              <a className="secondary" href={`/api/runs/${run.id}/export`}>
                <Download size={16} />
                Export report
              </a>
            </div>
            <div className="metrics four">
              <Metric
                label="No-action score"
                value={report.baseline.score}
                sub="Identical world, seed and horizon"
              />
              <Metric
                label="Your score"
                value={m.score}
                sub={`${report.comparison.score_change > 0 ? "+" : ""}${report.comparison.score_change} vs baseline`}
              />
              <Metric
                label="Gross impact avoided"
                value={money(report.comparison.loss_avoided)}
                sub="Synthetic impact units"
              />
              <Metric
                label="Net response benefit"
                value={money(report.comparison.net_benefit)}
                sub="Impact avoided minus action costs"
              />
            </div>
            <div className="panel">
              <div className="panel-heading">
                <h3>Decision history</h3>
              </div>
              <Table rows={run.decisions} />
            </div>
            <div className="callout">
              <CircleHelp size={19} />
              {report.note}
            </div>
          </>
        ) : (
          <Empty
            title={
              complete ? "Preparing debrief…" : "The story is still unfolding"
            }
          >
            Complete the run to reveal the incident source and compare your
            decisions with an identical no-action baseline.
          </Empty>
        ))}
    </>
  );
}

function Dataset({ data, user, onUpdated, act, busy }) {
  const [table, setTable] = useState(Object.keys(data.tables)[0]),
    [rows, setRows] = useState([]),
    [offset, setOffset] = useState(0),
    [root, setRoot] = useState(""),
    [evidence, setEvidence] = useState(""),
    [recommendation, setRecommendation] = useState(""),
    [result, setResult] = useState(data.assessments?.at(-1) || null),
    [checkState, setCheckState] = useState(null),
    [skipBaseline, setSkipBaseline] = useState(false),
    [tableTouched, setTableTouched] = useState(false);
  const observing = Boolean(data.owner && data.owner !== user.id);
  const baselineGate =
    !observing &&
    !result &&
    !skipBaseline &&
    (!checkState || checkState.baseline_open);
  useEffect(() => {
    if (baselineGate) return;
    act(async () => {
      setRows(
        (await api(`/datasets/${data.id}/tables/${table}?offset=${offset}`))
          .rows,
      );
      setTableTouched(true);
    });
  }, [data.id, table, offset, baselineGate]);
  const check = (
    <LearningCheck
      resourceId={data.id}
      resourcePath={`/datasets/${data.id}`}
      kind="case"
      completed={Boolean(result)}
      activityKey={`${data.assessments?.length || 0}:${tableTouched}:${skipBaseline}`}
      observing={observing}
      expanded
      onStateChange={setCheckState}
    />
  );
  if (baselineGate)
    return (
      <>
        <PageTitle
          title={data.title}
          subtitle={`Synthetic training records · Seed ${data.meta.seed}`}
        />
        {check}
        <section className="panel padded">
          <h3>Start with what you know</h3>
          <p>
            Answer the starting knowledge check before opening the case evidence
            to compare your knowledge after practice. You can continue without
            it, but knowledge change will be unavailable.
          </p>
          <button
            className="secondary"
            disabled={busy}
            onClick={() =>
              act(async () => {
                setCheckState(
                  await api(`/datasets/${data.id}/learning-check/skip`, {}),
                );
                setSkipBaseline(true);
              })
            }
          >
            Continue without starting check
          </button>
        </section>
      </>
    );
  return (
    <>
      <PageTitle
        title={data.title}
        subtitle={`Synthetic training records · Seed ${data.meta.seed}`}
      >
        <a className="secondary" href={`/api/datasets/${data.id}/export`}>
          <Download size={16} />
          Download CSV bundle
        </a>
      </PageTitle>
      {check}
      <div className="callout">
        <ShieldCheck size={20} />
        <div>
          <strong>Structural quality: {data.quality.score}%</strong>
          <p>
            {data.quality.checks
              .map((c) => `${c.passed ? "✓" : "✕"} ${c.name}`)
              .join(" · ")}
          </p>
          <small>{data.quality.note}</small>
        </div>
      </div>
      <div className="tabs table-tabs">
        {Object.entries(data.tables).map(([k, n]) => (
          <button
            key={k}
            className={k === table ? "active" : ""}
            onClick={() => {
              setTable(k);
              setOffset(0);
            }}
          >
            {k}
            <small>{n}</small>
          </button>
        ))}
      </div>
      <div className="panel">
        <Table rows={rows} />
        <div className="pagination">
          <button
            className="secondary"
            disabled={busy || offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 100))}
          >
            Previous
          </button>
          <span>
            {offset + 1}–{Math.min(offset + 100, data.tables[table])} of{" "}
            {data.tables[table]}
          </span>
          <button
            className="secondary"
            disabled={busy || offset + 100 >= data.tables[table]}
            onClick={() => setOffset(offset + 100)}
          >
            Next
          </button>
        </div>
      </div>
      <section className="panel assessment">
        <div className="panel-heading">
          <div>
            <h3>Make your case</h3>
            <p>{data.scenario.objective}</p>
            <small className="muted">
              Scored out of 100: root cause 55 · evidence 25 · recommendation 20
            </small>
          </div>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            act(async () => {
              setResult(
                await api(`/datasets/${data.id}/assess`, {
                  root_cause: root,
                  evidence: evidence.split(","),
                  recommendation,
                }),
              );
              onUpdated(await api(`/datasets/${data.id}`));
            });
          }}
        >
          <label>
            Root cause
            <select
              value={root}
              onChange={(e) => setRoot(e.target.value)}
              required
            >
              <option value="">Select your finding</option>
              {data.scenario.root_options.map((o) => (
                <option key={o}>{o}</option>
              ))}
            </select>
          </label>
          <label>
            Evidence labels (comma-separated)
            <input
              value={evidence}
              onChange={(e) => setEvidence(e.target.value)}
              placeholder="For example: S-03, lead_time, stock"
            />
          </label>
          <label>
            Your recommendation
            <textarea
              value={recommendation}
              onChange={(e) => setRecommendation(e.target.value)}
              required
              rows="3"
            />
          </label>
          <button className="primary" disabled={busy}>
            Submit assessment
            <ArrowRight size={16} />
          </button>
        </form>
        {result && (
          <div className="assessment-result">
            <h4>Latest case attempt</h4>
            <strong>{result.score} / 100</strong>
            <p>Expected finding: {result.expected_root}</p>
            <p>Evidence: {result.expected_evidence.join(", ")}</p>
            <small>{result.note}</small>
          </div>
        )}
      </section>
    </>
  );
}

const draft = {
  title: "Warehouse Recovery Challenge",
  summary:
    "A stock synchronization failure interrupts picking, dispatch and customer deliveries.",
  unit: "orders",
  nodes: [
    {
      id: "inventory",
      label: "Inventory sync",
      role: "investigator",
      capacity: 5,
    },
    {
      id: "picking",
      label: "Picking stations",
      role: "operations",
      capacity: 4,
    },
    {
      id: "dispatch",
      label: "Dispatch lanes",
      role: "operations",
      capacity: 5,
    },
    {
      id: "customers",
      label: "Customer delivery",
      role: "finance",
      capacity: 6,
    },
  ],
  edges: [
    { source: "inventory", target: "picking" },
    { source: "picking", target: "dispatch" },
    { source: "dispatch", target: "customers" },
  ],
  incident_node: "inventory",
  cause: "A duplicate stock-update batch blocks inventory synchronization.",
};
function Designer({ act, busy, onCreated }) {
  const [text, setText] = useState(JSON.stringify(draft, null, 2));
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {}
  return (
    <>
      <PageTitle
        title="Design a connected world"
        subtitle="Define real dependencies, finite capacity, an initiating incident and a business outcome."
      />
      <div className="workspace-grid designer-grid">
        <section className="panel padded">
          <h3>World definition</h3>
          <p className="muted">
            Edit the example below. Each node has an owner and processing
            capacity. Dependencies must form a connected, acyclic graph.
          </p>
          <label className="sr-only" htmlFor="world-json">
            World definition JSON
          </label>
          <textarea
            id="world-json"
            className="code-editor"
            rows="26"
            value={text}
            onChange={(e) => setText(e.target.value)}
            spellCheck="false"
          />
          <button
            className="primary full"
            disabled={busy || !parsed}
            onClick={() =>
              act(async () =>
                onCreated(await api("/scenarios", JSON.parse(text))),
              )
            }
          >
            <Plus size={16} />
            Validate & save world
          </button>
        </section>
        <div>
          <section className="panel">
            <div className="panel-heading">
              <h3>Dependency preview</h3>
              <GitBranch size={19} />
            </div>
            {Array.isArray(parsed?.nodes) && Array.isArray(parsed?.edges) ? (
              <WorldGraph
                nodes={parsed.nodes.filter(
                  (n) =>
                    n &&
                    typeof n.id === "string" &&
                    typeof n.label === "string",
                )}
                edges={parsed.edges.filter(
                  (e) => e && typeof e.source === "string",
                )}
              />
            ) : (
              <Empty title="Check your JSON">
                A graph preview appears when the definition is valid JSON.
              </Empty>
            )}
          </section>
          <section className="panel padded">
            <h3>What makes a good world?</h3>
            <ol className="guide-list">
              <li>Start with one observable business disruption.</li>
              <li>Connect 3–12 systems through causal dependencies.</li>
              <li>Give each specialist a different view of the evidence.</li>
              <li>Balance processing capacity against the population.</li>
              <li>
                Run two strategies with the same seed and compare outcomes.
              </li>
            </ol>
            <div className="callout">
              This designer validates structured data. It never executes pasted
              Python or arbitrary workflow code.
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
function Lab({ act, busy }) {
  const [csv, setCsv] = useState(
      "region,orders,delay_minutes\nNorth,125,4\nSouth,98,7\nEast,146,3\nWest,111,9",
    ),
    [method, setMethod] = useState("independent"),
    [rows, setRows] = useState(100),
    [result, setResult] = useState(null);
  function download() {
    const blob = new Blob([JSON.stringify(result, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "simforge-synthetic-data.json";
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <>
      <PageTitle
        title="Generator lab"
        subtitle="Create small tabular datasets locally. No source file is saved by the service."
      />
      <div className="workspace-grid">
        <section className="panel padded">
          <h3>Source CSV</h3>
          <p className="muted">
            Use synthetic or approved non-sensitive records.
          </p>
          <label>
            Load CSV file
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => {
                const f = e.target.files[0];
                if (f)
                  act(async () => {
                    if (f.size > 250000) throw new Error("CSV limit is 250 KB");
                    setCsv(await f.text());
                  });
              }}
            />
          </label>
          <textarea
            aria-label="Source CSV"
            className="code-editor"
            value={csv}
            onChange={(e) => setCsv(e.target.value)}
            rows="10"
          />
          <div className="form-grid">
            <label>
              Engine
              <select
                value={method}
                onChange={(e) => setMethod(e.target.value)}
              >
                <option value="independent">
                  Independent + numeric jitter
                </option>
                <option value="bootstrap">Row bootstrap</option>
              </select>
            </label>
            <label>
              Output rows
              <input
                type="number"
                min="1"
                max="2000"
                value={rows}
                onChange={(e) => setRows(e.target.value)}
              />
            </label>
          </div>
          <button
            className="primary full"
            disabled={busy}
            onClick={() =>
              act(async () =>
                setResult(
                  await api("/synthesis", {
                    csv,
                    rows: Number(rows),
                    seed: 2026,
                    method,
                  }),
                ),
              )
            }
          >
            <FlaskConical size={16} />
            Generate dataset
          </button>
        </section>
        <section className="panel padded">
          <h3>Quality & privacy</h3>
          <p>
            These lightweight samplers support testing and workshops. They do
            not anonymize personal data.
          </p>
          {result ? (
            <>
              <div className="metrics">
                <Metric label="Generated rows" value={result.rows.length} />
                <Metric
                  label="Exact source overlaps"
                  value={result.exact_overlap}
                />
              </div>
              <p className="muted">{result.note}</p>
              <button className="secondary" onClick={download}>
                <Download size={16} />
                Download result
              </button>
            </>
          ) : (
            <Empty title="Ready when you are">
              Generate a dataset to inspect overlap and output records.
            </Empty>
          )}
        </section>
      </div>
      {result && (
        <div className="panel">
          <div className="panel-heading">
            <h3>Generated records</h3>
            <Badge>First 100 rows</Badge>
          </div>
          <Table rows={result.rows.slice(0, 100)} />
        </div>
      )}
    </>
  );
}
function Connectors({ act, busy }) {
  const [profiles, setProfiles] = useState([]),
    [datasets, setDatasets] = useState([]),
    [name, setName] = useState("Training sandbox"),
    [type, setType] = useState("sqlite"),
    [did, setDid] = useState(""),
    [result, setResult] = useState(null);
  async function load() {
    const [p, d] = await Promise.all([api("/connectors"), api("/datasets")]);
    setProfiles(p);
    setDatasets(d);
    if (!did && d.length) setDid(d[0].id);
  }
  useEffect(() => {
    act(load);
  }, []);
  return (
    <>
      <PageTitle
        title="Local integrations"
        subtitle="Export synthetic datasets into controlled files or a separate SQLite sandbox."
      />
      <div className="workspace-grid">
        <section className="panel padded">
          <h3>Add an integration</h3>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              act(async () => {
                await api("/connectors", { name, type });
                await load();
              });
            }}
          >
            <label>
              Name
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </label>
            <label>
              Destination
              <select value={type} onChange={(e) => setType(e.target.value)}>
                <option value="sqlite">SQLite sandbox</option>
                <option value="file">CSV + JSON ZIP</option>
              </select>
            </label>
            <button className="primary" disabled={busy}>
              <Plus size={16} />
              Create integration
            </button>
          </form>
          <p className="tiny">
            Destinations are managed inside the application's data/exports
            directory. No network credentials or external database are required.
          </p>
        </section>
        <section className="panel padded">
          <h3>Release a dataset</h3>
          <label>
            Training dataset
            <select value={did} onChange={(e) => setDid(e.target.value)}>
              <option value="">Select dataset</option>
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.title} · {d.id.slice(0, 6)}
                </option>
              ))}
            </select>
          </label>
          {profiles.map((p) => (
            <div className="connector" key={p.id}>
              <Database size={20} />
              <div>
                <strong>{p.name}</strong>
                <small>{p.type}</small>
              </div>
              <button
                className="secondary"
                disabled={busy || !did}
                onClick={() =>
                  act(async () =>
                    setResult(await api(`/connectors/${p.id}/push/${did}`, {})),
                  )
                }
              >
                Export
                <ArrowRight size={14} />
              </button>
            </div>
          ))}
          {!profiles.length && (
            <p className="muted">
              Create your first integration to export records.
            </p>
          )}
          {result && (
            <div className="callout">
              <Check size={18} />
              <div>
                <strong>{result.tables} tables exported</strong>
                <p className="break">{result.destination}</p>
              </div>
            </div>
          )}
        </section>
      </div>
    </>
  );
}

createRoot(document.getElementById("root")).render(<App />);
