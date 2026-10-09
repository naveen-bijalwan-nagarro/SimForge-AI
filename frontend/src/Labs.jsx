import React, { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  Bot,
  Check,
  Database,
  Download,
  FlaskConical,
  Plus,
  Search,
  Trash2,
  Wand2,
} from "lucide-react";
import { api } from "./client";
import { LearningCheck } from "./LearningCheck";
import { CyGraph, EChart, lineOption } from "./viz";

const fmt = (v, d = 3) =>
  typeof v === "number"
    ? Math.abs(v) >= 100
      ? Math.round(v).toLocaleString()
      : Number(v.toFixed(d))
    : v === null || v === undefined
      ? "—"
      : String(v);

function Heading({ eyebrow, title, subtitle, children }) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      {children}
    </div>
  );
}

function Rows({ rows, highlight }) {
  if (!rows?.length) return <p className="muted">No rows.</p>;
  const keys = [...new Set(rows.flatMap((r) => Object.keys(r)))].filter(
    (k) => typeof rows[0][k] !== "object" || rows[0][k] === null,
  );
  return (
    <div className="table-scroll small-table">
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
            <tr key={i} className={highlight?.(r) ? "flagged" : ""}>
              {keys.map((k) => (
                <td key={k}>{fmt(r[k])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ================================================================== ML FAILURE LAB */
const STAGES = [
  ["raw", "Raw data"],
  ["eda", "EDA"],
  ["features", "Feature engineering"],
  ["train", "Train"],
  ["evaluate", "Evaluate"],
  ["deploy", "Deploy"],
  ["production", "Simulated production"],
  ["investigate", "Investigate"],
  ["fix", "Fix"],
  ["rescore", "Rescore"],
];

function MetricStrip({ metrics, primary }) {
  if (!metrics) return null;
  const keys =
    primary === "wape"
      ? ["wape", "bias", "mae"]
      : [
          "cost_per_1k",
          "recall",
          "precision",
          "accuracy",
          "auc",
          "alert_rate",
          "ece",
        ];
  return (
    <div className="metric-strip">
      {keys
        .filter((k) => metrics[k] !== undefined)
        .map((k) => (
          <span key={k}>
            <small>{k.replaceAll("_", " ")}</small>
            <strong>{fmt(metrics[k])}</strong>
          </span>
        ))}
    </div>
  );
}

function ProbeView({ probe, family }) {
  const d = probe.data;
  switch (probe.probe) {
    case "raw":
      return (
        <>
          {d.training && (
            <>
              <h4>Training records (labels as recorded)</h4>
              <Rows rows={d.training} />
            </>
          )}
          <h4>Production records (as served to the model)</h4>
          <Rows rows={d.production} />
        </>
      );
    case "eda": {
      const feats = d.features || [];
      return (
        <EdaView
          features={feats}
          segmentDrift={d.segment_drift}
          driverBySeries={d.driver_by_series}
        />
      );
    }
    case "features":
      return <Rows rows={d.features} />;
    case "training":
      return (
        <>
          <MetricStrip metrics={{ ...d, learning_curve: undefined }} />
          <Rows
            rows={[
              Object.fromEntries(
                Object.entries(d).filter(
                  ([, v]) => typeof v !== "object" || v === null,
                ),
              ),
            ]}
          />
          {d.learning_curve && (
            <EChart
              height={220}
              label="Learning curve"
              option={lineOption(
                d.learning_curve.map((r) => r.rows),
                [
                  {
                    name: "train AUC",
                    data: d.learning_curve.map((r) => r.train_auc),
                  },
                  {
                    name: "validation AUC",
                    data: d.learning_curve.map((r) => r.validation_auc),
                  },
                ],
              )}
            />
          )}
          {d.segment_rows && (
            <Rows
              rows={Object.entries(d.segment_rows).map(([segment, rows]) => ({
                segment,
                rows,
              }))}
            />
          )}
        </>
      );
    case "offline":
      return (
        <>
          <MetricStrip metrics={d.validation} />
          <p className="tiny">Decision threshold {fmt(d.threshold)}</p>
        </>
      );
    case "registry":
      return (
        <>
          <Rows
            rows={d.models.map((m) => ({
              ...m,
              features: Array.isArray(m.features)
                ? m.features.length
                : m.features,
              train_days: (m.train_days || []).join("-"),
            }))}
          />
          <p className="tiny">
            Approved {d.approved_version} · serving {d.serving_version} · model
            age {d.model_age_days} days
          </p>
        </>
      );
    case "timeline":
      if (family === "forecasting") {
        const series = Object.entries(d.series || {});
        return (
          <div className="grid-2">
            {series.map(([name, pts]) => (
              <EChart
                key={name}
                height={200}
                label={`${name} forecast vs actual`}
                option={{
                  ...lineOption(
                    pts.map((p) => p.day),
                    [
                      {
                        name: "recorded actual",
                        data: pts.map((p) => p.actual),
                      },
                      {
                        name: "forecast",
                        data: pts.map((p) => p.forecast),
                        lineStyle: { type: "dashed" },
                      },
                    ],
                    { markX: d.onset },
                  ),
                  title: { text: name, textStyle: { fontSize: 12 } },
                }}
              />
            ))}
          </div>
        );
      }
      return (
        <EChart
          height={260}
          label="Production monitoring"
          option={{
            ...lineOption(
              d.buckets.map((b) => b.days),
              [
                {
                  name: "cost / 1k",
                  data: d.buckets.map((b) => b.cost_per_1k),
                  yAxisIndex: 0,
                },
                {
                  name: "alert rate",
                  data: d.buckets.map((b) => b.alert_rate),
                  yAxisIndex: 1,
                },
                {
                  name: "observed precision",
                  data: d.buckets.map((b) => b.precision),
                  yAxisIndex: 1,
                },
                {
                  name: "observed recall",
                  data: d.buckets.map((b) => b.recall),
                  yAxisIndex: 1,
                },
                {
                  name: "labels matured %",
                  data: d.buckets.map((b) => b.labels_matured_pct / 100),
                  yAxisIndex: 1,
                  lineStyle: { type: "dotted" },
                },
              ],
            ),
            yAxis: [
              { type: "value", name: "cost" },
              { type: "value", name: "rate", max: 1 },
            ],
          }}
        />
      );
    case "segments":
      return (
        <>
          <EChart
            height={220}
            label="Segment comparison"
            option={{
              legend: {},
              tooltip: {},
              xAxis: { type: "category", data: d.rows.map((r) => r.segment) },
              yAxis: { type: "value" },
              series: [
                {
                  type: "bar",
                  name: "training share",
                  data: d.rows.map((r) => r.training_share),
                },
                {
                  type: "bar",
                  name: "production share",
                  data: d.rows.map((r) => r.production_share),
                },
                {
                  type: "bar",
                  name: "recall",
                  data: d.rows.map((r) => r.recall),
                },
              ],
            }}
          />
          <Rows rows={d.rows} />
        </>
      );
    case "importance":
      return (
        <>
          <EChart
            height={Math.max(180, d.features.length * 22)}
            label="Feature importance"
            option={{
              grid: { left: 150 },
              tooltip: {},
              xAxis: { type: "value" },
              yAxis: {
                type: "category",
                data: d.features.map((f) => f.feature).reverse(),
              },
              series: [
                {
                  type: "bar",
                  data: d.features.map((f) => f.share ?? f.weight).reverse(),
                },
              ],
            }}
          />
          <Rows rows={d.features} />
        </>
      );
    case "calibration":
      return (
        <EChart
          height={260}
          label="Reliability diagram"
          option={{
            legend: {},
            tooltip: {},
            xAxis: { type: "value", min: 0, max: 1, name: "predicted" },
            yAxis: { type: "value", min: 0, max: 1, name: "observed" },
            series: [
              {
                type: "line",
                name: "perfect",
                data: [
                  [0, 0],
                  [1, 1],
                ],
                lineStyle: { type: "dashed" },
                showSymbol: false,
              },
              {
                type: "line",
                name: `validation (ECE ${fmt(d.validation_ece)})`,
                data: d.validation.map((b) => [b.predicted, b.observed]),
              },
              {
                type: "line",
                name: `production (ECE ${fmt(d.production_ece)})`,
                data: d.production.map((b) => [b.predicted, b.observed]),
              },
            ],
          }}
        />
      );
    case "threshold":
      return (
        <>
          <EChart
            height={260}
            label="Threshold curve"
            option={{
              ...lineOption(
                d.curve.map((c) => fmt(c.threshold, 2)),
                [
                  {
                    name: "cost / 1k",
                    data: d.curve.map((c) => c.cost_per_1k),
                    yAxisIndex: 0,
                  },
                  {
                    name: "precision",
                    data: d.curve.map((c) => c.precision),
                    yAxisIndex: 1,
                  },
                  {
                    name: "recall",
                    data: d.curve.map((c) => c.recall),
                    yAxisIndex: 1,
                  },
                ],
              ),
              yAxis: [
                { type: "value", name: "cost" },
                { type: "value", max: 1 },
              ],
            }}
          />
          <p className="tiny">
            Deployed threshold {fmt(d.deployed)} (cost {fmt(d.deployed_cost)}) ·
            cost-optimal {fmt(d.cost_optimal)} (cost {fmt(d.optimal_cost)})
          </p>
        </>
      );
    case "label_audit":
      return (
        <>
          <Rows rows={d.audit} highlight={(r) => r.mismatches > 0} />
          <EChart
            height={180}
            label="Label maturity"
            option={lineOption(
              (d.maturity || d.completeness).map((m) => m.age_days),
              [
                {
                  name: "% arrived",
                  data: (d.maturity || d.completeness).map(
                    (m) => m.labels_arrived_pct ?? m.reported_pct,
                  ),
                },
              ],
            )}
          />
        </>
      );
    case "pipeline_trace":
      return <Rows rows={d.rows} highlight={(r) => r.match === false} />;
    case "schema":
      return (
        <Rows
          rows={(d.fields || d.series || [])
            .map((f) => ({
              field: f.field || f.series,
              versions: f.versions
                .map(
                  (v) =>
                    `${v.version}@${v.from_day}: ${v.unit}${v.nullable ? " (nullable)" : ""}`,
                )
                .join(" → "),
            }))
            .concat(
              (d.feeds || []).map((f) => ({
                field: f.field,
                versions: `feed ${f.status}${f.since ? " since day " + f.since : ""}`,
              })),
            )}
          highlight={(r) =>
            r.versions.includes("→") || r.versions.includes("stopped")
          }
        />
      );
    case "entity_graph":
      return d.nodes?.length ? (
        <>
          <CyGraph
            height={300}
            layout="cose"
            label="Entity network"
            nodes={d.nodes.map((n) => ({
              id: n.id,
              label: n.id,
              color:
                n.type === "entity"
                  ? n.fraud_rate > 0.3
                    ? "#e5484d"
                    : "#4a8fe7"
                  : "#7761db",
              size: n.type === "entity" ? 18 : 26,
            }))}
            edges={d.edges.map((e) => ({
              ...e,
              label: String(e.weight),
              color: "#c9cedc",
            }))}
          />
          <Rows rows={d.entities} highlight={(r) => r.lift > 3} />
        </>
      ) : (
        <p className="muted">{d.note}</p>
      );
    case "series":
      return (
        <Rows
          rows={d.rows}
          highlight={(r) => Math.abs(r.bias) > 0.2 || !r.in_training}
        />
      );
    case "residual_dow":
      return (
        <EChart
          height={220}
          label="Error by weekday"
          option={{
            tooltip: {},
            xAxis: { type: "category", data: d.rows.map((r) => r.weekday) },
            yAxis: { type: "value", name: "% error" },
            series: [
              { type: "bar", data: d.rows.map((r) => r.mean_error_pct) },
            ],
          }}
        />
      );
    case "events":
      return (
        <>
          <Rows
            rows={[
              { segment: "event days", ...(d.event_days || {}) },
              { segment: "normal days", ...d.normal_days },
              { segment: `${d.driver} days`, ...(d.driver_days || {}) },
            ]}
          />
          <p className="tiny">
            Calendar events in production window: {d.calendar.join(", ")}
          </p>
        </>
      );
    default:
      return (
        <pre className="log-lines">
          {JSON.stringify(d, null, 2).slice(0, 4000)}
        </pre>
      );
  }
}

function EdaView({ features, segmentDrift, driverBySeries }) {
  const [pick, setPick] = useState(features[0]?.feature);
  const f = features.find((x) => x.feature === pick) || features[0];
  return (
    <>
      <Rows
        rows={features.map((x) => ({
          feature: x.feature,
          unit: x.unit,
          train_mean: x.train.mean,
          prod_mean: x.production.mean,
          train_zero_pct: x.train.zeros_pct,
          prod_zero_pct: x.production.zeros_pct,
          psi: x.psi,
        }))}
        highlight={(r) => r.psi > 0.25}
      />
      {f && (
        <>
          <label>
            Distribution
            <select value={pick} onChange={(e) => setPick(e.target.value)}>
              {features.map((x) => (
                <option key={x.feature}>{x.feature}</option>
              ))}
            </select>
          </label>
          <EChart
            height={220}
            label={`${f.feature} distribution`}
            option={{
              legend: {},
              tooltip: {},
              xAxis: {
                type: "category",
                data: f.histogram.edges.slice(0, -1).map((e) => fmt(e, 2)),
              },
              yAxis: { type: "value" },
              series: [
                { type: "bar", name: "training", data: f.histogram.train },
                {
                  type: "bar",
                  name: "production",
                  data: f.histogram.production,
                },
              ],
            }}
          />
        </>
      )}
      {segmentDrift?.length > 0 && (
        <>
          <h4>Largest drift within segments</h4>
          <Rows rows={segmentDrift} highlight={(r) => r.psi > 0.6} />
        </>
      )}
      {driverBySeries && (
        <>
          <h4>Driver by series</h4>
          <Rows rows={driverBySeries} />
        </>
      )}
    </>
  );
}

export function LabCatalog({ user, onOpen, query = "" }) {
  const [catalog, setCatalog] = useState(null);
  const [labs, setLabs] = useState([]);
  const [group, setGroup] = useState("Fraud detection");
  const [error, setError] = useState("");
  const [custom, setCustom] = useState({
    profile: "credit_card_fraud",
    failures: [],
    count: 2,
  });
  useEffect(() => {
    Promise.all([api("/mllab/catalog"), api("/mllab/labs")])
      .then(([c, l]) => {
        setCatalog(c);
        setLabs(l);
      })
      .catch((e) => setError(e.message));
  }, []);
  async function start(body) {
    try {
      setError("");
      const lab = await api("/mllab/labs", body);
      onOpen(lab.id);
    } catch (e) {
      setError(e.message);
    }
  }
  if (!catalog)
    return <p className="muted">{error || "Loading the lab catalogue…"}</p>;
  const groups = [...new Set(catalog.scenarios.map((s) => s.group))];
  const family = catalog.profiles.find((p) => p.key === custom.profile)?.family;
  return (
    <>
      {error && <p className="error-banner">{error}</p>}
      <div className="filters">
        {groups.map((g) => (
          <button
            key={g}
            className={group === g ? "active" : ""}
            onClick={() => setGroup(g)}
          >
            {g}{" "}
            <small>
              {catalog.scenarios.filter((s) => s.group === g).length}
            </small>
          </button>
        ))}
      </div>
      <div className="scenario-grid">
        {catalog.scenarios
          .filter(
            (s) =>
              (query.trim() || s.group === group) &&
              [s.title, s.story, s.group]
                .join(" ")
                .toLowerCase()
                .includes(query.toLowerCase()),
          )
          .map((s) => (
            <button
              key={s.key}
              className="scenario-card"
              onClick={() => start({ scenario_key: s.key })}
            >
              <div className="card-top">
                <div className="scenario-icon purple">
                  <FlaskConical size={22} />
                </div>
                <span className="badge">
                  {s.failures === "random"
                    ? "HIDDEN FAILURES"
                    : `${s.failures.length} HIDDEN`}
                </span>
              </div>
              <div className="category-label">{s.group}</div>
              <h3>{s.title}</h3>
              <p>{s.story}</p>
              <div className="card-bottom">
                <span>Starting check · Investigate · Post-check</span>
                <ArrowRight size={16} />
              </div>
            </button>
          ))}
      </div>
      {user.role === "admin" && (
        <section className="panel padded">
          <h3>Trainer: build a custom failure mix</h3>
          <div className="form-grid">
            <label>
              Profile
              <select
                value={custom.profile}
                onChange={(e) =>
                  setCustom({
                    ...custom,
                    profile: e.target.value,
                    failures: [],
                  })
                }
              >
                {catalog.profiles.map((p) => (
                  <option key={p.key} value={p.key}>
                    {p.group} · {p.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Random failures (if none selected)
              <input
                type="number"
                min="1"
                max="5"
                value={custom.count}
                onChange={(e) =>
                  setCustom({ ...custom, count: Number(e.target.value) })
                }
              />
            </label>
          </div>
          <div className="chips">
            {catalog.failures
              .filter((f) => f.families.includes(family))
              .map((f) => (
                <button
                  key={f.key}
                  className={
                    custom.failures.includes(f.key) ? "chip active" : "chip"
                  }
                  onClick={() =>
                    setCustom({
                      ...custom,
                      failures: custom.failures.includes(f.key)
                        ? custom.failures.filter((x) => x !== f.key)
                        : [...custom.failures, f.key].slice(0, 5),
                    })
                  }
                >
                  {f.label}
                </button>
              ))}
          </div>
          <button
            className="primary"
            onClick={() =>
              start({
                profile: custom.profile,
                failures: custom.failures.length ? custom.failures : null,
                count: custom.count,
              })
            }
          >
            <Wand2 size={15} /> Create challenge
          </button>
        </section>
      )}
      {labs.length > 0 && (
        <section className="panel">
          <div className="panel-heading">
            <h3>Your labs</h3>
          </div>
          {labs.map((l) => (
            <button
              key={l.id}
              className="list-row"
              onClick={() => onOpen(l.id)}
            >
              <div className="list-icon">
                <FlaskConical size={18} />
              </div>
              <div>
                <strong>{l.title}</strong>
                <small>
                  {l.group} · {l.family} ·{" "}
                  {new Date(l.created * 1000).toLocaleString()}
                </small>
              </div>
              <span className="badge">
                {l.score != null ? `score ${l.score}` : "in progress"}
              </span>
              <ArrowRight size={16} />
            </button>
          ))}
        </section>
      )}
    </>
  );
}

function LabWorkspace({ id, user, onBack }) {
  const [lab, setLab] = useState(null);
  const [stage, setStage] = useState("production");
  const [checkState, setCheckState] = useState(null);
  const [skipBaseline, setSkipBaseline] = useState(false);
  const [probes, setProbes] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [chosen, setChosen] = useState([]);
  const [fixes, setFixes] = useState([]);
  const [ring, setRing] = useState("");
  const [agent, setAgent] = useState(null);
  const load = () =>
    api(`/mllab/labs/${id}`)
      .then(setLab)
      .catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, [id]);
  async function probe(name, record = true) {
    if (probes[name]) return probes[name];
    setBusy(true);
    try {
      const r = await api(
        `/mllab/labs/${id}/probes/${name}?record=${record}`,
        {},
      );
      setProbes((p) => ({ ...p, [name]: r }));
      if (record)
        setLab((l) => ({
          ...l,
          probes_used: [...new Set([...(l.probes_used || []), name])],
        }));
      return r;
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    const auto = {
      raw: "raw",
      eda: "eda",
      features: "features",
      train: "training",
      evaluate: "offline",
      deploy: "registry",
    }[stage];
    if (auto && lab?.probes) probe(auto, false);
  }, [stage, lab?.id]);
  if (!lab)
    return (
      <p className="muted">
        {error ||
          "Building the synthetic world, training the model and deploying it…"}
      </p>
    );
  const minutes = (lab.probes_used || []).reduce(
    (t, p) => t + ((lab.probes || []).find((x) => x.name === p)?.minutes || 0),
    0,
  );
  const submitted = lab.submission;
  const labReady = Boolean(lab.profile && lab.stages && lab.monitored);
  const observing = lab.owner !== user.id;
  const baselineGate =
    !observing &&
    !submitted &&
    !skipBaseline &&
    (!checkState || checkState.baseline_open);
  const check = (
    <LearningCheck
      resourceId={id}
      resourcePath={`/mllab/labs/${id}`}
      kind="ml"
      completed={Boolean(submitted)}
      activityKey={`${(lab.probes_used || []).length}:${skipBaseline}`}
      observing={observing}
      expanded
      onStateChange={setCheckState}
      onSaved={async () => {
        if (!labReady) await load();
      }}
    />
  );
  if (baselineGate || !labReady)
    return (
      <>
        <Heading
          eyebrow={`ML FAILURE LAB · ${lab.config.group.toUpperCase()}`}
          title={lab.config.title}
          subtitle={lab.config.story}
        >
          <button className="secondary" onClick={onBack}>
            All challenges
          </button>
        </Heading>
        {error && <p className="error-banner">{error}</p>}
        {check}
        {baselineGate ? (
          <section className="panel padded">
            <h3>Start with what you know</h3>
            <p>
              Answer the starting knowledge check before viewing model signals
              to compare your knowledge after practice. You can continue
              without it, but knowledge change will be unavailable.
            </p>
            <button
              className="secondary"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  setCheckState(
                    await api(`/mllab/labs/${id}/learning-check/skip`, {}),
                  );
                  await load();
                  setSkipBaseline(true);
                } catch (e) {
                  setError(e.message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              Continue without starting check
            </button>
          </section>
        ) : (
          <section className="panel padded" role="status">
            <p>Loading model workspace…</p>
            {error && (
              <button className="secondary" onClick={load}>
                Retry loading workspace
              </button>
            )}
          </section>
        )}
      </>
    );
  const stageProbe = {
    raw: "raw",
    eda: "eda",
    features: "features",
    train: "training",
    evaluate: "offline",
    deploy: "registry",
  }[stage];
  return (
    <>
      <Heading
        eyebrow={`ML FAILURE LAB · ${lab.config.group.toUpperCase()}`}
        title={lab.config.title}
        subtitle={lab.config.story}
      >
        <button className="secondary" onClick={onBack}>
          All challenges
        </button>
      </Heading>
      {error && <p className="error-banner">{error}</p>}
      {check}
      <div
        className="stepper"
        role="tablist"
        aria-label="Data-science pipeline"
      >
        {STAGES.map(([k, label], i) => (
          <button
            key={k}
            role="tab"
            aria-selected={stage === k}
            className={
              "step " +
              (stage === k ? "active" : "") +
              (k === "rescore" && submitted ? " done" : "")
            }
            onClick={() => setStage(k)}
          >
            <span>{i + 1}</span>
            {label}
          </button>
        ))}
      </div>
      <section className="panel padded">
        <div className="panel-heading">
          <div>
            <h3>{STAGES.find(([k]) => k === stage)[1]}</h3>
            <p>
              {lab.stages.find(
                (s) => s.key === (stage === "train" ? "train" : stage),
              )?.summary || ""}
            </p>
          </div>
          <span className="badge">
            {lab.profile.title} · {lab.family}
          </span>
        </div>
        {stageProbe &&
          (probes[stageProbe] ? (
            <ProbeView probe={probes[stageProbe]} family={lab.family} />
          ) : (
            <p className="muted">Loading…</p>
          ))}
        {stage === "raw" && lab.profile.visual && (
          <div className="image-strip">
            {Array.from({ length: 12 }).map((_, i) => (
              <img
                key={i}
                src={`/api/mllab/labs/${id}/image/${i < 6 ? i : i + 6}`}
                alt={`Sample inspection image ${i + 1}`}
                width="160"
                height="120"
                loading="lazy"
              />
            ))}
            <p className="tiny">
              First row: training period images. Second row: recent production
              images.
            </p>
          </div>
        )}
        {stage === "evaluate" && (
          <>
            <h4>Offline (validation)</h4>
            <MetricStrip metrics={lab.offline} primary={lab.primary} />
          </>
        )}
        {stage === "production" && (
          <>
            <p className="callout">
              Offline the model looked fine. In production the monitored{" "}
              {lab.primary === "wape" ? "forecast error" : "business cost"} is{" "}
              <strong>{fmt(lab.monitored[lab.primary])}</strong> vs{" "}
              <strong>{fmt(lab.offline[lab.primary])}</strong> offline. Find out
              why.
            </p>
            <MetricStrip metrics={lab.monitored} primary={lab.primary} />
            {lab.family === "forecasting" ? (
              <ProbeView
                probe={{ probe: "timeline", data: lab.monitoring }}
                family="forecasting"
              />
            ) : (
              <ProbeView
                probe={{ probe: "timeline", data: lab.monitoring }}
                family="classification"
              />
            )}
          </>
        )}
        {stage === "investigate" && (
          <>
            <p className="tiny">
              Investigation time used: <strong>{minutes}</strong> of{" "}
              {lab.budget_minutes} minutes (efficiency counts in the score).
            </p>
            <div className="probe-buttons">
              {lab.probes.map((p) => (
                <button
                  key={p.name}
                  className={
                    "chip " +
                    ((lab.probes_used || []).includes(p.name) ? "active" : "")
                  }
                  disabled={busy}
                  onClick={() => probe(p.name, true)}
                >
                  <Search size={13} /> {p.label} · {p.minutes}m
                </button>
              ))}
            </div>
            {Object.values(probes)
              .filter((p) => (lab.probes_used || []).includes(p.probe))
              .reverse()
              .map((p) => (
                <article key={p.probe} className="probe-result">
                  <h4>{p.label}</h4>
                  <ProbeView probe={p} family={lab.family} />
                </article>
              ))}
          </>
        )}
        {stage === "fix" &&
          (submitted ? (
            <p className="callout">Submitted. See Rescore.</p>
          ) : (
            <div className="fix-form">
              <h4>What went wrong? (select every failure you found)</h4>
              <div className="failure-options">
                {lab.failure_types.map((f) => (
                  <label
                    key={f.key}
                    className={"option " + (chosen.includes(f.key) ? "on" : "")}
                  >
                    <input
                      type="checkbox"
                      checked={chosen.includes(f.key)}
                      onChange={() =>
                        setChosen(
                          chosen.includes(f.key)
                            ? chosen.filter((x) => x !== f.key)
                            : [...chosen, f.key],
                        )
                      }
                    />
                    <strong>{f.label}</strong>
                    <small>{f.explain}</small>
                  </label>
                ))}
              </div>
              <h4>Fixes to apply before retraining and redeploying</h4>
              {fixes.map((fx, i) => {
                const def = lab.fixes.find((x) => x.key === fx.fix);
                return (
                  <div key={i} className="fix-row">
                    <select
                      aria-label="Fix"
                      value={fx.fix}
                      onChange={(e) =>
                        setFixes(
                          fixes.map((x, j) =>
                            j === i ? { fix: e.target.value } : x,
                          ),
                        )
                      }
                    >
                      {lab.fixes.map((f) => (
                        <option key={f.key} value={f.key}>
                          {f.label}
                        </option>
                      ))}
                    </select>
                    {def?.needs_feature && (
                      <select
                        aria-label="Feature"
                        value={fx.feature || ""}
                        onChange={(e) =>
                          setFixes(
                            fixes.map((x, j) =>
                              j === i ? { ...x, feature: e.target.value } : x,
                            ),
                          )
                        }
                      >
                        <option value="">Choose feature…</option>
                        {lab.fix_features.map((f) => (
                          <option key={f}>{f}</option>
                        ))}
                      </select>
                    )}
                    <button
                      className="secondary"
                      aria-label="Remove fix"
                      onClick={() => setFixes(fixes.filter((_, j) => j !== i))}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                );
              })}
              <button
                className="secondary"
                onClick={() => setFixes([...fixes, { fix: lab.fixes[0].key }])}
              >
                <Plus size={14} /> Add fix
              </button>
              {lab.ring_entity && (
                <label>
                  Suspected collusion ring ({lab.ring_entity} ids, comma
                  separated)
                  <input
                    value={ring}
                    onChange={(e) => setRing(e.target.value)}
                    placeholder="e.g. MER-017, MER-042"
                  />
                </label>
              )}
              <button
                className="primary"
                disabled={busy || !chosen.length}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await api(`/mllab/labs/${id}/submit`, {
                      failures: chosen,
                      fixes,
                      ring: ring
                        .split(",")
                        .map((x) => x.trim())
                        .filter(Boolean),
                    });
                    await load();
                    setStage("rescore");
                  } catch (e) {
                    setError(e.message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                <Check size={15} /> Retrain, redeploy & rescore
              </button>
            </div>
          ))}
        {stage === "rescore" &&
          (submitted ? (
            <Rescore lab={lab} id={id} agent={agent || lab.agent} />
          ) : (
            <p className="muted">
              Submit your diagnosis and fixes in the Fix step first.
            </p>
          ))}
        <div className="lab-footer">
          <button
            className="secondary"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                setAgent(await api(`/mllab/labs/${id}/agent`, {}));
              } catch (e) {
                setError(e.message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <Bot size={15} /> Run AI investigator
          </button>
          {agent && !agent.failures && (
            <span className="tiny">{agent.message}</span>
          )}
          <a className="secondary" href={`/api/mllab/labs/${id}/export`}>
            <Download size={15} /> Export lab data
          </a>
        </div>
      </section>
    </>
  );
}

function Rescore({ lab, id, agent }) {
  const s = lab.submission;
  const key = s.metric;
  const bars = [
    ["Before (with failures)", s.before.true[key]],
    ["After your fixes", s.after.true[key]],
    ["All correct fixes", s.oracle.true[key]],
  ];
  return (
    <>
      <div className="metrics four">
        <div className="metric">
          <div className="metric-top">Your score</div>
          <strong>{s.score} / 100</strong>
          <small>diagnosis 45 · recovery 35 · fixes 10 · efficiency 10</small>
        </div>
        <div className="metric">
          <div className="metric-top">Diagnosis F1</div>
          <strong>{fmt(s.parts.diagnosis_f1, 2)}</strong>
          <small>failures found vs injected</small>
        </div>
        <div className="metric">
          <div className="metric-top">Recovery</div>
          <strong>{Math.round(s.parts.recovery * 100)}%</strong>
          <small>of the achievable improvement</small>
        </div>
        <div className="metric">
          <div className="metric-top">Investigation</div>
          <strong>{s.minutes_used}m</strong>
          <small>{s.unnecessary_fixes.length} unnecessary fixes</small>
        </div>
      </div>
      <EChart
        height={220}
        label="Before and after"
        option={{
          tooltip: {},
          xAxis: { type: "category", data: bars.map((b) => b[0]) },
          yAxis: { type: "value", name: key },
          series: [
            {
              type: "bar",
              data: bars.map((b) => b[1]),
              itemStyle: {
                color: (p) => ["#e5484d", "#7761db", "#35a37b"][p.dataIndex],
              },
            },
          ],
        }}
      />
      <h4>Ground truth (ground_truth.json)</h4>
      <ul className="critic">
        {s.ground_truth.failures.map((f) => (
          <li key={f.key}>
            <strong>{f.label}</strong> — {f.explain}
          </li>
        ))}
      </ul>
      <p className="tiny">
        Correct fixes:{" "}
        {s.ground_truth.correct_fixes
          .map((f) => f.fix + (f.feature ? `(${f.feature})` : ""))
          .join(", ")}
        {s.ground_truth.ring?.length
          ? ` · ring: ${s.ground_truth.ring.join(", ")}`
          : ""}
      </p>
      {agent?.failures && (
        <div className="callout">
          <Bot size={18} />
          <div>
            <strong>AI investigator scored {agent.score}</strong> — found{" "}
            {agent.failures.join(", ") || "nothing"}.
            <ul className="critic">
              {agent.rationale.map((r, i) => (
                <li key={i}>
                  {r.failure}: {r.evidence}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
      <a className="secondary" href={`/api/mllab/labs/${id}/ground_truth.json`}>
        <Download size={15} /> ground_truth.json
      </a>
    </>
  );
}

export function MLLab({ user, openLab, setOpenLab, onCatalog }) {
  return (
    <>
      {!openLab && (
        <Heading
          eyebrow="FAILURE INJECTION FOR DATA SCIENCE"
          title="ML failure lab"
          subtitle="SafeSim generates realistic synthetic data, trains and deploys a real scikit-learn model, then secretly injects 1–5 production problems. Find out why the model is wrong, fix it, and rescore against the hidden ground truth."
        />
      )}
      {openLab ? (
        <LabWorkspace
          key={openLab}
          id={openLab}
          user={user}
          onBack={() => (onCatalog ? onCatalog() : setOpenLab(null))}
        />
      ) : (
        <LabCatalog user={user} onOpen={setOpenLab} />
      )}
    </>
  );
}

/* ================================================================== DATASET STUDIO */
const PARAM_HINTS = {
  id: { prefix: "ID" },
  int: { min: 0, max: 100 },
  float: { dist: "normal", mean: 0, std: 1 },
  bool: { p: 0.5 },
  category: { values: ["a", "b"] },
  datetime: { start: "2026-09-01T00:00", end: "2026-09-28T00:00" },
  date: { start: "2026-01-01", end: "2026-09-28" },
  text: { template: "{choice:low|high}" },
  faker: { provider: "name" },
  ref: { table: "", column: "" },
  shared: { kind: "Supplier" },
  formula: { expr: "a * b" },
  series: { base: 10, amplitude: 2, period: 24, noise: 0.5 },
  label: { weights: {}, bias: -3 },
  image: { kind: "surface", defect_rate: 0.3, lighting: 1.0 },
};

function ColumnEditor({ col, onChange, onRemove, types }) {
  const params = Object.fromEntries(
    Object.entries(col).filter(
      ([k]) => !["name", "type", "description"].includes(k),
    ),
  );
  const [text, setText] = useState(JSON.stringify(params));
  const [bad, setBad] = useState(false);
  useEffect(() => setText(JSON.stringify(params)), [col.type]);
  return (
    <div className="column-row">
      <input
        aria-label="Column name"
        value={col.name}
        onChange={(e) => onChange({ ...col, name: e.target.value })}
      />
      <select
        aria-label="Column type"
        value={col.type}
        onChange={(e) =>
          onChange({
            name: col.name,
            type: e.target.value,
            ...PARAM_HINTS[e.target.value],
          })
        }
      >
        {Object.keys(types).map((t) => (
          <option key={t}>{t}</option>
        ))}
      </select>
      <input
        aria-label="Column parameters (JSON)"
        className={bad ? "invalid" : ""}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          try {
            onChange({
              name: col.name,
              type: col.type,
              ...(col.description ? { description: col.description } : {}),
              ...JSON.parse(e.target.value || "{}"),
            });
            setBad(false);
          } catch {
            setBad(true);
          }
        }}
      />
      <button
        className="secondary"
        aria-label={`Remove column ${col.name}`}
        onClick={onRemove}
      >
        <Trash2 size={14} />
      </button>
    </div>
  );
}

export function DatasetStudio({ scenarios }) {
  const [meta, setMeta] = useState(null);
  const [schema, setSchema] = useState(null);
  const [guide, setGuide] = useState(null);
  const [tableIdx, setTableIdx] = useState(0);
  const [problems, setProblems] = useState([]);
  const [preview, setPreview] = useState(null);
  const [raw, setRaw] = useState(false);
  const [saved, setSaved] = useState([]);
  const [message, setMessage] = useState("");
  const [source, setSource] = useState("");
  const worlds = scenarios.filter((s) => s.kind === "world");
  useEffect(() => {
    api("/studio/templates").then(setMeta);
    api("/studio/datasets")
      .then(setSaved)
      .catch(() => {});
  }, []);
  useEffect(() => {
    if (!schema) return;
    const t = setTimeout(
      () =>
        api("/studio/validate", { dataset: stripGuide(schema) })
          .then((r) => setProblems(r.problems))
          .catch(() => {}),
      350,
    );
    return () => clearTimeout(t);
  }, [schema]);
  const stripGuide = (s) =>
    Object.fromEntries(Object.entries(s).filter(([k]) => k !== "guide"));
  async function loadRecommended(key) {
    setSource(key);
    const r = await api(`/studio/recommend/${key}`);
    setGuide(r.guide);
    setSchema(stripGuide(r));
    setTableIdx(0);
    setPreview(null);
  }
  async function loadTemplate(key) {
    setSource("template:" + key);
    setGuide(null);
    setSchema(await api(`/studio/templates/${key}`));
    setTableIdx(0);
    setPreview(null);
  }
  const table = schema?.tables?.[tableIdx];
  const updateTable = (t) =>
    setSchema({
      ...schema,
      tables: schema.tables.map((x, i) => (i === tableIdx ? t : x)),
    });
  return (
    <>
      <Heading
        eyebrow="SYNTHETIC DATA · SCHEMA → DATASET"
        title="Dataset studio"
        subtitle="Choose a use case, review the recommended linked datasets and why they exist, edit the schema, inject controlled anomalies and export data with ground truth."
      />
      <div className="studio-grid">
        <section className="panel padded">
          <h3>1 · Start from a use case</h3>
          <label>
            Simulation world (recommended datasets)
            <select
              value={source.startsWith("template:") ? "" : source}
              onChange={(e) =>
                e.target.value && loadRecommended(e.target.value)
              }
            >
              <option value="">Select a world…</option>
              {worlds.map((s) => (
                <option key={s.key} value={s.key}>
                  {s.category} · {s.title}
                </option>
              ))}
            </select>
          </label>
          <p className="tiny">or a template</p>
          <div className="chips">
            {meta?.templates.map((t) => (
              <button
                key={t.key}
                className={
                  source === "template:" + t.key ? "chip active" : "chip"
                }
                onClick={() => loadTemplate(t.key)}
                title={t.description}
              >
                {t.name}
              </button>
            ))}
          </div>
          {saved.length > 0 && (
            <>
              <p className="tiny">or a saved dataset</p>
              <div className="chips">
                {saved.map((d) => (
                  <button
                    key={d.id}
                    className="chip"
                    onClick={async () => {
                      const r = await api(`/studio/datasets/${d.id}`);
                      setSchema(r.dataset);
                      setGuide(null);
                      setSource("saved:" + d.id);
                      setTableIdx(0);
                    }}
                  >
                    {d.name}
                  </button>
                ))}
              </div>
            </>
          )}
          {guide && (
            <div className="guide">
              <h4>What to generate and why</h4>
              <p>{guide.what}</p>
              <ol>
                {guide.steps.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ol>
              {guide.tasks?.length > 0 && (
                <>
                  <h4>Learning tasks this data supports</h4>
                  <ul>
                    {guide.tasks.map((t) => (
                      <li key={t}>{t}</li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}
          {meta && (
            <details>
              <summary>Column types & anomaly types reference</summary>
              <table className="score-table">
                <tbody>
                  {Object.entries(meta.column_types).map(([k, v]) => (
                    <tr key={k}>
                      <td>
                        <code>{k}</code>
                      </td>
                      <td>{v}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <table className="score-table">
                <tbody>
                  {Object.entries(meta.anomaly_types).map(([k, v]) => (
                    <tr key={k}>
                      <td>
                        <code>{k}</code>
                      </td>
                      <td>{v}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="tiny">
                Limits: {meta.limits.tables} tables, {meta.limits.columns}{" "}
                columns/table, {meta.limits.rows.toLocaleString()} rows/table,{" "}
                {meta.limits.images} images.
              </p>
            </details>
          )}
        </section>
        <section className="panel padded">
          <div className="panel-heading">
            <h3>2 · Review & edit the schema</h3>
            {schema && (
              <button className="secondary" onClick={() => setRaw(!raw)}>
                {raw ? "Visual editor" : "Edit raw JSON"}
              </button>
            )}
          </div>
          {!schema && (
            <p className="muted">
              Pick a world or template to load an editable schema.
            </p>
          )}
          {schema && raw && (
            <textarea
              className="code-editor"
              rows="24"
              aria-label="Dataset schema JSON"
              defaultValue={JSON.stringify(schema, null, 2)}
              onBlur={(e) => {
                try {
                  setSchema(JSON.parse(e.target.value));
                  setMessage("");
                } catch (err) {
                  setMessage("Invalid JSON: " + err.message);
                }
              }}
            />
          )}
          {schema && !raw && (
            <>
              <label>
                Dataset name
                <input
                  value={schema.name || ""}
                  onChange={(e) =>
                    setSchema({ ...schema, name: e.target.value })
                  }
                />
              </label>
              <div className="tabs table-tabs">
                {schema.tables.map((t, i) => (
                  <button
                    key={i}
                    className={i === tableIdx ? "active" : ""}
                    onClick={() => setTableIdx(i)}
                  >
                    {t.name}
                    <small>{t.data ? t.data.length : t.rows}</small>
                  </button>
                ))}
                <button
                  onClick={() => {
                    setSchema({
                      ...schema,
                      tables: [
                        ...schema.tables,
                        {
                          name: `table_${schema.tables.length + 1}`,
                          rows: 100,
                          columns: [{ name: "id", type: "id", prefix: "T" }],
                        },
                      ],
                    });
                    setTableIdx(schema.tables.length);
                  }}
                >
                  <Plus size={13} /> table
                </button>
              </div>
              {table && (
                <div className="table-editor">
                  <div className="form-grid">
                    <label>
                      Table name
                      <input
                        value={table.name}
                        onChange={(e) =>
                          updateTable({ ...table, name: e.target.value })
                        }
                      />
                    </label>
                    {!table.data && (
                      <label>
                        Rows
                        <input
                          type="number"
                          min="1"
                          value={table.rows}
                          onChange={(e) =>
                            updateTable({
                              ...table,
                              rows: Number(e.target.value),
                            })
                          }
                        />
                      </label>
                    )}
                  </div>
                  {table.purpose && (
                    <p className="tiny">Purpose: {table.purpose}</p>
                  )}
                  {table.data ? (
                    <p className="tiny">
                      Fixed reference table with {table.data.length} rows (from
                      the scenario or shared master data).
                    </p>
                  ) : (
                    <>
                      <div className="column-row head">
                        <span>column</span>
                        <span>type</span>
                        <span>parameters (JSON)</span>
                        <span />
                      </div>
                      {table.columns.map((c, ci) => (
                        <ColumnEditor
                          key={ci + c.type}
                          col={c}
                          types={meta.column_types}
                          onChange={(nc) =>
                            updateTable({
                              ...table,
                              columns: table.columns.map((x, j) =>
                                j === ci ? nc : x,
                              ),
                            })
                          }
                          onRemove={() =>
                            updateTable({
                              ...table,
                              columns: table.columns.filter((_, j) => j !== ci),
                            })
                          }
                        />
                      ))}
                      <button
                        className="secondary"
                        onClick={() =>
                          updateTable({
                            ...table,
                            columns: [
                              ...table.columns,
                              {
                                name: `column_${table.columns.length + 1}`,
                                type: "float",
                                dist: "normal",
                                mean: 0,
                                std: 1,
                              },
                            ],
                          })
                        }
                      >
                        <Plus size={14} /> Add column
                      </button>
                    </>
                  )}
                  <button
                    className="secondary danger"
                    disabled={schema.tables.length < 2}
                    onClick={() => {
                      setSchema({
                        ...schema,
                        tables: schema.tables.filter((_, i) => i !== tableIdx),
                      });
                      setTableIdx(0);
                    }}
                  >
                    <Trash2 size={14} /> Remove table
                  </button>
                </div>
              )}
              <h4>Controlled anomalies (ground truth)</h4>
              {(schema.anomalies || []).map((a, i) => (
                <div key={i} className="column-row anomaly-row">
                  <select
                    aria-label="Anomaly type"
                    value={a.type}
                    onChange={(e) =>
                      setSchema({
                        ...schema,
                        anomalies: schema.anomalies.map((x, j) =>
                          j === i ? { ...x, type: e.target.value } : x,
                        ),
                      })
                    }
                  >
                    {Object.keys(meta?.anomaly_types || {}).map((t) => (
                      <option key={t}>{t}</option>
                    ))}
                  </select>
                  <input
                    aria-label="Anomaly settings (JSON)"
                    defaultValue={JSON.stringify(
                      Object.fromEntries(
                        Object.entries(a).filter(([k]) => k !== "type"),
                      ),
                    )}
                    onBlur={(e) => {
                      try {
                        setSchema({
                          ...schema,
                          anomalies: schema.anomalies.map((x, j) =>
                            j === i
                              ? { type: a.type, ...JSON.parse(e.target.value) }
                              : x,
                          ),
                        });
                      } catch {
                        setMessage("Anomaly settings must be JSON");
                      }
                    }}
                  />
                  <button
                    className="secondary"
                    aria-label="Remove anomaly"
                    onClick={() =>
                      setSchema({
                        ...schema,
                        anomalies: schema.anomalies.filter((_, j) => j !== i),
                      })
                    }
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
              <button
                className="secondary"
                onClick={() =>
                  setSchema({
                    ...schema,
                    anomalies: [
                      ...(schema.anomalies || []),
                      {
                        type: "missing",
                        table: schema.tables[0].name,
                        column: schema.tables[0].columns?.[0]?.name || "",
                        rate: 0.05,
                      },
                    ],
                  })
                }
              >
                <Plus size={14} /> Add anomaly
              </button>
            </>
          )}
          {schema && (
            <div
              className={"validation " + (problems.length ? "bad" : "good")}
              role="status"
            >
              {problems.length ? (
                <>
                  <strong>{problems.length} problem(s)</strong>
                  <ul>
                    {problems.map((p) => (
                      <li key={p}>{p}</li>
                    ))}
                  </ul>
                </>
              ) : (
                <strong>
                  <Check size={14} /> Schema is valid
                </strong>
              )}
            </div>
          )}
          {message && <p className="error">{message}</p>}
        </section>
      </div>
      {schema && (
        <section className="panel padded">
          <div className="panel-heading">
            <h3>3 · Preview, save & export</h3>
            <div className="actions">
              <button
                className="secondary"
                disabled={problems.length > 0}
                onClick={async () => {
                  try {
                    setPreview(
                      await api("/studio/preview", {
                        dataset: stripGuide(schema),
                      }),
                    );
                  } catch (e) {
                    setMessage(e.message);
                  }
                }}
              >
                <Database size={15} /> Preview
              </button>
              <button
                className="primary"
                disabled={problems.length > 0}
                onClick={async () => {
                  try {
                    const r = await api("/studio/datasets", {
                      name: schema.name || "Dataset",
                      dataset: stripGuide(schema),
                      scenario_key:
                        source && !source.includes(":") ? source : null,
                    });
                    setSaved(await api("/studio/datasets"));
                    setMessage("");
                    window.location.href = `/api/studio/datasets/${r.id}/export`;
                  } catch (e) {
                    setMessage(e.message);
                  }
                }}
              >
                <Download size={15} /> Save & export ZIP
              </button>
            </div>
          </div>
          <p className="tiny">
            Export: CSV + JSONL per table, SQLite database, schema.json,
            ground_truth.json (every injected anomaly and affected row),
            data_card.md, and PNG images with COCO annotations for image
            columns.
          </p>
          {preview && <DataPreview preview={preview} />}
        </section>
      )}
    </>
  );
}

function DataPreview({ preview }) {
  const names = Object.keys(preview.tables);
  // Open the largest generated table first; small reference tables are less informative.
  const [tab, setTab] = useState(
    names.reduce(
      (best, n) =>
        preview.profile[n].rows > preview.profile[best].rows ? n : best,
      names[0],
    ),
  );
  const prof = preview.profile[tab];
  const numeric = Object.entries(prof?.columns || {})
    .filter(([, c]) => c.kind === "numeric")
    .slice(0, 4);
  const categorical = Object.entries(prof?.columns || {})
    .filter(
      ([, c]) => c.kind === "categorical" && c.distinct > 1 && c.distinct <= 30,
    )
    .slice(0, 2);
  return (
    <>
      <div className="tabs table-tabs">
        {names.map((n) => (
          <button
            key={n}
            className={tab === n ? "active" : ""}
            onClick={() => setTab(n)}
          >
            {n}
            <small>{preview.profile[n].rows}</small>
          </button>
        ))}
      </div>
      <Rows
        rows={preview.tables[tab].map((r) =>
          Object.fromEntries(
            Object.entries(r).map(([k, v]) => [
              k,
              typeof v === "string" && v.startsWith("images/") ? v : v,
            ]),
          ),
        )}
      />
      <div className="grid-2">
        {numeric.map(([name, c]) => (
          <EChart
            key={name}
            height={170}
            label={`${name} histogram`}
            option={{
              title: { text: name, textStyle: { fontSize: 12 } },
              tooltip: {},
              xAxis: {
                type: "category",
                data: c.histogram.map((_, i) =>
                  fmt(c.min + ((c.max - c.min) * i) / 12, 2),
                ),
              },
              yAxis: { type: "value" },
              series: [{ type: "bar", data: c.histogram }],
            }}
          />
        ))}
        {categorical.map(([name, c]) => (
          <EChart
            key={name}
            height={170}
            label={`${name} counts`}
            option={{
              title: { text: name, textStyle: { fontSize: 12 } },
              tooltip: {},
              series: [
                {
                  type: "pie",
                  radius: ["35%", "65%"],
                  data: c.top.map(([k, v]) => ({ name: k, value: v })),
                },
              ],
            }}
          />
        ))}
      </div>
      {preview.ground_truth.anomalies.length > 0 && (
        <>
          <h4>Injected anomalies (ground truth)</h4>
          <Rows
            rows={preview.ground_truth.anomalies.map((a) => ({
              type: a.type,
              table: a.table,
              column: a.column,
              count: a.count,
              sample_rows: (a.sample_rows || []).slice(0, 4).join(", "),
              note: a.note,
            }))}
          />
        </>
      )}
    </>
  );
}

/* ================================================================== SCENARIO GRAPH */
export function ScenarioGraph({ onOpenScenario }) {
  const [data, setData] = useState(null);
  const [shared, setShared] = useState(null);
  const [pick, setPick] = useState(null);
  const [kind, setKind] = useState("Supplier");
  useEffect(() => {
    api("/scenario-graph").then(setData);
    api("/shared-entities").then(setShared);
  }, []);
  const colors = useMemo(() => ({}), []);
  if (!data) return <p className="muted">Loading the scenario graph…</p>;
  const cats = [...new Set(data.nodes.map((n) => n.category))];
  const palette = [
    "#7761db",
    "#2f9e8f",
    "#e2a336",
    "#e5484d",
    "#4a8fe7",
    "#9b6b3c",
    "#c05dbd",
    "#35a37b",
    "#8a90a6",
  ];
  cats.forEach((c, i) => (colors[c] = palette[i % palette.length]));
  return (
    <>
      <Heading
        eyebrow="CONNECTED BUT INDEPENDENT"
        title="Scenario graph"
        subtitle="Each scenario runs on its own. Optional links pass outcomes forward: Scenario A → signal → Scenario B. Shared master data lets scenarios refer to the same synthetic suppliers, machines and customers."
      />
      <section className="panel padded">
        <div className="legend-row">
          {cats.map((c) => (
            <span key={c}>
              <i className="dot" style={{ background: colors[c] }} /> {c}
            </span>
          ))}
        </div>
        <CyGraph
          height={620}
          layout="cose"
          label="Scenario dependency graph"
          onSelect={(n) => n.kind !== "signal" && setPick(n)}
          nodes={[
            ...data.nodes.map((n) => ({
              id: n.id,
              label: n.label,
              color: colors[n.category],
              size: n.kind === "lab" ? 14 : 22,
              kind: n.kind,
              emits: n.emits.join(", "),
              consumes: n.consumes.join(", "),
            })),
            ...data.signals.map((s) => ({
              id: "signal:" + s,
              label: s.replaceAll("_", " "),
              color: "#29314e",
              size: 18,
              shape: "diamond",
              kind: "signal",
            })),
          ]}
          edges={[
            ...data.nodes.flatMap((n) =>
              n.emits
                .filter((s) => data.signals.includes(s))
                .map((s) => ({
                  source: n.id,
                  target: "signal:" + s,
                  color: "#e2a336",
                  label: "",
                })),
            ),
            ...data.nodes.flatMap((n) =>
              n.consumes
                .filter((s) => data.signals.includes(s))
                .map((s) => ({
                  source: "signal:" + s,
                  target: n.id,
                  color: "#9aa3bd",
                  label: "",
                })),
            ),
          ]}
        />
        <p className="tiny">
          Diamonds are signals: orange arrows = scenario emits the signal; grey
          arrows = scenario can be triggered by it.
        </p>
        {pick && (
          <div className="node-detail">
            <strong>{pick.label}</strong>
            <span>
              {pick.kind} · emits: {pick.emits || "—"} · consumes:{" "}
              {pick.consumes || "—"}
            </span>
            {pick.kind === "world" && (
              <button
                className="secondary"
                onClick={() => onOpenScenario(pick.id)}
              >
                Open
              </button>
            )}
          </div>
        )}
        <p className="tiny">
          {data.nodes.length} connected scenarios · {data.edges.length} links ·
          signals: {data.signals.join(", ")}
        </p>
      </section>
      {shared && (
        <section className="panel padded">
          <h3>Shared synthetic entities</h3>
          <div className="chips">
            {Object.keys(shared.registry).map((k) => (
              <button
                key={k}
                className={kind === k ? "chip active" : "chip"}
                onClick={() => setKind(k)}
              >
                {k} <small>{shared.references[k].length} scenarios</small>
              </button>
            ))}
          </div>
          <p className="tiny">
            Used by: {shared.references[kind].join(", ") || "no scenario yet"}
          </p>
          <Rows rows={shared.registry[kind].slice(0, 16)} />
        </section>
      )}
    </>
  );
}
