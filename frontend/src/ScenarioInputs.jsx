import React, { useEffect, useRef, useState } from "react";
import { api } from "./client";

export function VoiceDictation({ onText, disabled }) {
  const [language, setLanguage] = useState("en-IN");
  const [consent, setConsent] = useState(false);
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [message, setMessage] = useState("");
  const recognition = useRef(null);
  const append = useRef(onText);
  append.current = onText;
  const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
  useEffect(
    () => () => {
      const current = recognition.current;
      if (current) {
        current.onresult = current.onerror = current.onend = null;
        current.abort();
      }
    },
    [],
  );
  function start() {
    setMessage("");
    try {
      recognition.current?.abort();
      const current = new Speech();
      recognition.current = current;
      current.lang = language;
      current.continuous = true;
      current.interimResults = true;
      const committed = new Set();
      current.onresult = (event) => {
        if (recognition.current !== current) return;
        let preview = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          if (result.isFinal && !committed.has(i)) {
            committed.add(i);
            append.current(result[0].transcript);
          } else if (!result.isFinal) preview += result[0].transcript + " ";
        }
        setInterim(preview.trim());
      };
      current.onerror = (event) => {
        if (recognition.current !== current) return;
        setMessage(
          `Dictation stopped: ${event.error}. Check microphone permission/network, or type instead.`,
        );
        setListening(false);
        setInterim("");
        current.abort();
      };
      current.onend = () => {
        if (recognition.current !== current) return;
        setListening(false);
        setInterim("");
        recognition.current = null;
      };
      current.start();
      setListening(true);
    } catch {
      setMessage(
        "Dictation could not start. Allow microphone access on HTTPS/localhost, or type instead.",
      );
      setListening(false);
    }
  }
  return (
    <section className="scenario-input" aria-label="Voice dictation controls">
      <h3>Write with your voice (optional)</h3>
      <p className="tiny">
        Your browser may send audio to its speech service; offline operation is
        not guaranteed. SimForge stores no audio. Do not dictate sensitive
        information. Review the editable text before generating; speech never
        publishes or executes commands.
      </p>
      {!Speech && (
        <p role="status">
          Voice dictation is not supported in this browser. Type your
          description instead.
        </p>
      )}
      <label>
        Dictation language
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          disabled={listening}
        >
          <option value="en-IN">English (India)</option>
          <option value="en-US">English (US)</option>
          <option value="hi-IN">Hindi (India)</option>
        </select>
      </label>
      <label className="voice-consent">
        <input
          type="checkbox"
          checked={consent}
          disabled={listening}
          onChange={(e) => setConsent(e.target.checked)}
        />{" "}
        I agree to browser speech processing
      </label>
      {listening ? (
        <button
          className="secondary"
          onClick={() => recognition.current?.stop()}
        >
          Stop dictation
        </button>
      ) : (
        <button
          className="secondary"
          disabled={!Speech || !consent || disabled}
          onClick={start}
        >
          Start voice dictation
        </button>
      )}
      {listening && (
        <p role="status">
          Listening… {interim || "Speak your training goal and workflow."}
        </p>
      )}
      {message && <p role="alert">{message}</p>}
    </section>
  );
}

function encoded(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1]);
    reader.onerror = () =>
      reject(new Error("Could not read the selected document"));
    reader.readAsDataURL(file);
  });
}

export function ScenarioDocuments({ selected, onSelect, disabled }) {
  const [documents, setDocuments] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => {
    api("/scenario-documents")
      .then(setDocuments)
      .catch((e) => setError(e.message));
  }, []);
  async function upload(event) {
    const files = Array.from(event.target.files || []);
    event.target.value = "";
    if (!files.length) return;
    setError("");
    setMessage("");
    if (
      files.length > 8 ||
      files.some((f) => f.size > 2 * 1024 * 1024) ||
      files.reduce((n, f) => n + f.size, 0) > 8 * 1024 * 1024
    ) {
      setError("Select up to 8 files, at most 2 MiB each and 8 MiB total.");
      return;
    }
    setBusy(true);
    try {
      const result = await api("/scenario-documents", {
        files: await Promise.all(
          files.map(async (file) => ({
            name: file.name,
            content: await encoded(file),
          })),
        ),
      });
      setDocuments((old) => [...result.documents, ...old]);
      onSelect(
        [...new Set([...selected, ...result.documents.map((d) => d.id)])].slice(
          0,
          8,
        ),
      );
      setMessage(
        `${result.documents.length} documents extracted locally. Select up to 8 references for the next draft.`,
      );
      if (result.errors.length)
        setError(
          result.errors.map((e) => `${e.name}: ${e.message}`).join(" · "),
        );
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="scenario-input"
      aria-label="Scenario reference documents"
    >
      <h3>Upload scenario documents</h3>
      <p>
        Upload multiple SOPs, workflow descriptions or training guides together:
        PDF, DOCX, TXT and Markdown. Up to 8 files per batch; 2 MiB per file, 8
        MiB total. Text PDFs only; no OCR or macros.
      </p>
      <p className="tiny">
        Only extracted, bounded text is kept locally; originals are not
        retained. Common PII patterns are redacted, but detection is not
        complete. Preview every reference and use synthetic/non-sensitive
        documents. Nothing is sent to an AI provider until you explicitly
        generate a draft. Templates do not automatically incorporate reference
        text.
      </p>
      <label>
        Scenario documents (multiple files)
        <input
          type="file"
          multiple
          accept=".pdf,.docx,.txt,.md"
          disabled={busy || disabled}
          onChange={upload}
        />
      </label>
      {busy && <p role="status">Extracting document text locally…</p>}
      {error && (
        <p className="error-banner" role="alert">
          {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      <p className="tiny">
        {selected.length}/8 references selected. Long references are excerpted
        fairly into a 24,000-character context budget; full extracted previews
        remain available.
      </p>
      {documents.map((d) => (
        <article className="document-reference" key={d.id}>
          <label className="voice-consent">
            <input
              type="checkbox"
              checked={selected.includes(d.id)}
              disabled={
                disabled || (!selected.includes(d.id) && selected.length >= 8)
              }
              onChange={(e) =>
                onSelect(
                  e.target.checked
                    ? [...selected, d.id]
                    : selected.filter((id) => id !== d.id),
                )
              }
            />{" "}
            {d.name}
          </label>
          <small>
            {d.text.length.toLocaleString()} extracted characters ·{" "}
            {d.redactions.total} detected PII matches redacted
          </small>
          {d.warnings.map((warning) => (
            <p className="tiny" key={warning}>
              {warning}
            </p>
          ))}
          <details>
            <summary>Preview extracted text: {d.name}</summary>
            <pre className="document-text">{d.text}</pre>
          </details>
        </article>
      ))}
    </section>
  );
}

export function ScenarioCleanup({ onChanged }) {
  const [preview, setPreview] = useState(null);
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function refresh() {
    setPreview(await api("/scenario-cleanup"));
  }
  useEffect(() => {
    refresh().catch((e) => setError(e.message));
  }, []);
  async function act(fn) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await refresh();
      setConfirmation("");
      await onChanged?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <details
      className="panel padded"
      onToggle={(e) => {
        if (e.currentTarget.open) refresh().catch((x) => setError(x.message));
      }}
    >
      <summary>Fresh demo: archive previous custom scenarios</summary>
      <p>
        Archive old custom publications, draft records and generation history.
        They disappear from the active queue/library and their old
        notifications/assignments are hidden. Built-in exercises, learner runs,
        prepared datasets and source documents remain. Existing saved
        runs/environments still work. Archives can be restored.
      </p>
      {preview && (
        <>
          <p>
            {preview.counts.scenario} custom publications ·{" "}
            {preview.counts.scenario_draft} draft records ·{" "}
            {preview.counts.authoring_job} generation jobs
          </p>
          <ul>
            {preview.records.map((r) => (
              <li key={r.id}>
                {r.title} ({r.kind})
              </li>
            ))}
          </ul>
          <label>
            Type ARCHIVE to confirm cleanup
            <input
              value={confirmation}
              onChange={(e) => setConfirmation(e.target.value)}
            />
          </label>
          <button
            className="secondary"
            disabled={
              busy || confirmation !== "ARCHIVE" || !preview.records.length
            }
            onClick={() =>
              act(async () => {
                const result = await api("/scenario-cleanup", {
                  token: preview.token,
                  confirmation,
                });
                setMessage(
                  `${result.count} records archived. Your next draft starts a fresh publication queue.`,
                );
              })
            }
          >
            Archive previous scenarios and drafts
          </button>
          {preview.history.map((batch) => (
            <p key={batch.id}>
              {new Date(batch.at * 1000).toLocaleString()} · {batch.count}{" "}
              archived records ·{" "}
              {batch.restored ? (
                "restored"
              ) : (
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() =>
                    act(async () => {
                      const result = await api(
                        `/scenario-cleanup/${batch.id}/restore`,
                        {},
                      );
                      setMessage(`${result.count} records restored.`);
                    })
                  }
                >
                  Restore archive {batch.id.slice(0, 6)}
                </button>
              )}
            </p>
          ))}
        </>
      )}
      {error && (
        <p role="alert" className="error-banner">
          {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
    </details>
  );
}
