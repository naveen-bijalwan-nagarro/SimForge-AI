import React, { useEffect, useRef, useState } from "react";
import { Bot, ExternalLink, LogOut, RefreshCw } from "lucide-react";
import { api } from "./client";

// One connection panel for Scenario Studio, SOP Factory and the MCP sandbox.
export function CodexConnection({ admin = true, onChange }) {
  const [status, setStatus] = useState(null);
  const [login, setLogin] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [catalogue, setCatalogue] = useState(null);
  const [model, setModel] = useState("");
  const [effort, setEffort] = useState("");
  const [modelError, setModelError] = useState("");
  const changed = useRef(onChange);
  changed.current = onChange;
  function accept(next) {
    setStatus(next);
    changed.current?.(next);
  }
  async function refresh() {
    const next = await api(
      admin ? "/authoring/status?refresh=true" : "/factory/status?refresh=true",
    );
    accept(admin ? next : next.codex);
  }
  async function loadModels(force = false) {
    setModelError("");
    try {
      const next = await api(
        "/authoring/models" + (force ? "?refresh=true" : ""),
      );
      setCatalogue(next);
      const selected =
        next.models.find((m) => m.id === status?.model) ||
        next.models.find((m) => m.id === next.configured_model) ||
        next.models.find((m) => m.default) ||
        next.models[0];
      setModel(selected?.id || "");
      setEffort(
        selected?.efforts.includes(status?.effort)
          ? status.effort
          : selected?.default_effort || selected?.efforts[0] || "",
      );
      await refresh();
    } catch (e) {
      setModelError(e.message);
    }
  }
  useEffect(() => {
    if (
      admin &&
      status?.installed &&
      status?.authenticated &&
      status?.can_configure
    )
      loadModels();
  }, [admin, status?.installed, status?.authenticated, status?.can_configure]);
  useEffect(() => {
    let alive = true,
      timer;
    async function poll() {
      try {
        const [next, session] = await Promise.all([
          api(admin ? "/authoring/status" : "/factory/status"),
          admin ? api("/authoring/login") : Promise.resolve(null),
        ]);
        if (alive) {
          accept(admin ? next : next.codex);
          setLogin(session);
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
  }, [admin]);
  async function act(fn) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const pending = login?.status === "pending";
  return (
    <section
      className="codex-connection"
      aria-label="Codex connection"
      data-testid="codex-connection"
    >
      <div className="codex-connection-heading">
        <Bot size={19} />
        <strong>Local Codex connection</strong>
      </div>
      <div className="codex-status" aria-live="polite">
        <span className={"pill " + (status?.ready ? "ok" : "")}>
          {status ? status.reason : "Checking Codex…"}
        </span>
        {status?.installed && (
          <span className="pill">{status.version || "CLI installed"}</span>
        )}
        {status?.installed && (
          <span className={"pill " + (status.authenticated ? "ok" : "bad")}>
            {status.authenticated ? "Signed in" : "Not signed in"}
          </span>
        )}
      </div>
      <p className="tiny">
        Uses the Codex CLI and account on the machine running the backend.
        ChatGPT plan usage limits apply. SimForge never stores your OAuth
        tokens.
      </p>
      <div className="actions">
        {admin && status?.can_configure && status?.installed && (
          <button
            className="secondary"
            disabled={busy}
            onClick={() =>
              act(async () =>
                accept(
                  await api("/authoring/settings", {
                    enabled: !status.enabled,
                  }),
                ),
              )
            }
          >
            {status.enabled
              ? "Disable Codex authoring"
              : "Enable Codex authoring"}
          </button>
        )}
        {admin &&
          status?.can_launch_login &&
          !status.authenticated &&
          !pending && (
            <>
              <button
                className="primary"
                disabled={busy}
                onClick={() =>
                  act(async () =>
                    setLogin(
                      await api("/authoring/login", { method: "browser" }),
                    ),
                  )
                }
              >
                Sign in to Codex
              </button>
              <button
                className="secondary"
                disabled={busy}
                onClick={() =>
                  act(async () =>
                    setLogin(
                      await api("/authoring/login", { method: "device" }),
                    ),
                  )
                }
              >
                Use device-code sign-in
              </button>
            </>
          )}
        {admin && pending && (
          <button
            className="secondary"
            disabled={busy}
            onClick={() =>
              act(async () =>
                setLogin(await api("/authoring/login/cancel", {})),
              )
            }
          >
            Cancel sign-in
          </button>
        )}
        {admin && status?.can_launch_login && status.authenticated && (
          <button
            className="secondary"
            disabled={busy}
            onClick={() => {
              if (
                window.confirm(
                  "Sign out of local Codex? This removes the CLI's saved credentials and affects other apps using this local Codex profile. Your SimForge session stays signed in.",
                )
              ) {
                act(async () => {
                  accept(await api("/authoring/logout", {}));
                  setLogin(null);
                  setMessage("Signed out of local Codex.");
                });
              }
            }}
          >
            <LogOut size={14} />
            Sign out of Codex
          </button>
        )}
        <button
          className="secondary"
          disabled={busy}
          onClick={() => act(refresh)}
        >
          <RefreshCw size={14} />
          Refresh Codex status
        </button>
      </div>
      {login && (
        <div className="codex-login-progress" role="status">
          <p>{login.message}</p>
          {pending && login.auth_url && (
            <a href={login.auth_url} target="_blank" rel="noopener noreferrer">
              Open official OpenAI sign-in <ExternalLink size={14} />
            </a>
          )}
          {pending && login.device_code && (
            <p>
              Enter this one-time code yourself on the official OpenAI page:{" "}
              <code>{login.device_code}</code>. Do not share it.
            </p>
          )}
          {pending && (
            <p className="tiny">
              Sign-in completes in your browser and this panel refreshes
              automatically. You can navigate between the admin tools while it
              runs.
            </p>
          )}
        </div>
      )}
      {admin &&
        status?.installed &&
        status?.authenticated &&
        status?.can_configure && (
          <div className="codex-model-settings">
            <div className="form-grid">
              <label>
                Codex model
                <select
                  value={model}
                  onChange={(e) => {
                    setModel(e.target.value);
                    const selected = catalogue?.models.find(
                      (m) => m.id === e.target.value,
                    );
                    setEffort(
                      selected?.default_effort || selected?.efforts[0] || "",
                    );
                  }}
                >
                  <option value="">Choose an available model</option>
                  {catalogue?.models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}
                      {m.default ? " (CLI recommended)" : ""}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Reasoning effort
                <select
                  value={effort}
                  onChange={(e) => setEffort(e.target.value)}
                >
                  <option value="">Choose effort</option>
                  {catalogue?.models
                    .find((m) => m.id === model)
                    ?.efforts.map((e) => (
                      <option key={e} value={e}>
                        {e}
                      </option>
                    ))}
                </select>
              </label>
            </div>
            {catalogue?.configured_model &&
              !catalogue.models.some(
                (m) => m.id === catalogue.configured_model,
              ) &&
              !status.model && (
                <p className="callout">
                  Your CLI default, {catalogue.configured_model}, is not listed
                  for this account. Save a listed model for SimForge below.
                </p>
              )}
            <p className="tiny">
              Active in SimForge: {status.model || "local CLI defaults"}
              {status.effort ? ` · ${status.effort}` : ""}. Saving here affects
              Scenario Studio, SOP factory and Codex sandbox; your global Codex
              configuration stays unchanged.
            </p>
            <div className="actions">
              <button
                className="secondary"
                disabled={busy || !model || !effort}
                onClick={() =>
                  act(async () => {
                    accept(await api("/authoring/model", { model, effort }));
                    setMessage("SimForge model settings saved.");
                  })
                }
              >
                Save SimForge model
              </button>
              <button
                className="secondary"
                disabled={busy}
                onClick={() => act(() => loadModels(true))}
              >
                Refresh available models
              </button>
            </div>
            {modelError && (
              <p role="alert" className="error-banner">
                {modelError}
              </p>
            )}
          </div>
        )}
      {!admin && status && !status.ready && (
        <p className="tiny">
          Ask an administrator to connect Codex in Scenario Studio. The built-in
          scenario engineer remains available.
        </p>
      )}
      {message && <p role="status">{message}</p>}
      {error && (
        <p className="error-banner" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
