import React, { useEffect, useState } from "react";
import { api } from "./client";

export function OpenAIConnection({ onChange }) {
  const [state, setState] = useState(null),
    [key, setKey] = useState(""),
    [model, setModel] = useState("gpt-4.1-mini"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  function accept(next) {
    setState(next);
    setModel(next.model);
    onChange?.(next);
  }
  useEffect(() => {
    let active = true;
    api("/authoring/openai")
      .then((next) => {
        if (active) accept(next);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, []);
  async function configure(clear = false) {
    setBusy(true);
    setError("");
    setMessage("");
    const submitted = key;
    setKey(""); // Never retain a submitted credential in the rendered form.
    try {
      const next = await api(
        clear ? "/authoring/openai/clear" : "/authoring/openai/config",
        clear ? {} : { api_key: submitted || null, model },
      );
      accept(next);
      setMessage(
        clear
          ? "Memory-only key removed. Any private-file or environment key is managed by the server."
          : "Settings saved. Generate a draft to verify model access; API usage is billed separately.",
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="codex-connection"
      data-testid="openai-connection"
      aria-label="OpenAI API connection"
    >
      <h3>OpenAI API backup · admin only</h3>
      <p>{state?.reason || "Loading API settings…"}</p>
      <p className="tiny">
        Only Admin / Trainer can configure this connection. The browser sends
        the key to your own backend; it never calls OpenAI directly, stores the
        key in browser storage or retrieves it again.
      </p>
      <label>
        OpenAI API key
        <input
          type="password"
          autoComplete="off"
          spellCheck={false}
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder={
            state?.configured
              ? "Configured; enter a replacement if needed"
              : "Enter your API key"
          }
        />
      </label>
      <label>
        OpenAI API model
        <input
          value={model}
          onChange={(e) => setModel(e.target.value)}
          maxLength={100}
        />
      </label>
      <div className="actions">
        <button
          className="secondary"
          disabled={busy || !state?.enabled || (!key && !state?.configured)}
          onClick={() => configure()}
        >
          Save API connection
        </button>
        <button
          className="secondary"
          disabled={busy || state?.key_source !== "server memory"}
          onClick={() => configure(true)}
        >
          Remove memory-only key
        </button>
      </div>
      <p className="tiny">
        {state?.persistence} Key source: {state?.key_source || "…"}. In
        production set SIMFORGE_OPENAI_ENABLED=1 and use HTTPS. Generated drafts
        are labelled OpenAI API, not Codex CLI.
      </p>
      {message && <p role="status">{message}</p>}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </section>
  );
}
