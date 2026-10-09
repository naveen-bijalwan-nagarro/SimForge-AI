import React, { useEffect, useState } from "react";
import { api } from "./client";

const scoreLabels = {
  knowledge: "Knowledge check",
  diagnosis: "Correct diagnosis",
  evidence: "Investigation before response",
  decision: "Targeted repair",
};

export function LearningCheck({
  run,
  observing,
  onSaved,
  expanded = false,
  onOpen,
}) {
  const [state, setState] = useState(null),
    [choices, setChoices] = useState({});
  const [questionIndex, setQuestionIndex] = useState(0);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [retry, setRetry] = useState(0);
  const completed = run.tick >= run.horizon;
  useEffect(() => {
    setState(null);
    setChoices({});
    setQuestionIndex(0);
    setError("");
  }, [run.id, completed]);
  useEffect(() => {
    let active = true;
    api("/runs/" + run.id + "/learning-check")
      .then((data) => {
        if (active) {
          setState(data);
          setError("");
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [run.id, completed, run.tick === 0, run.clock?.running, retry]);

  const phase = completed ? "after" : "before";
  const open = state?.[completed ? "post_open" : "baseline_open"];
  const questions = state?.[phase + "_questions"] || [];
  const question = questions[questionIndex];
  const ready =
    questions.length === 3 &&
    questions.every((q) => choices[q.id] !== undefined);
  async function submit() {
    setBusy(true);
    setError("");
    try {
      setState(
        await api("/runs/" + run.id + "/learning-check/" + phase, {
          choices: questions.map((q) => choices[q.id]),
        }),
      );
      setChoices({});
      setQuestionIndex(0);
      await onSaved?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      className="panel padded learning-check learner-learning"
      aria-label="Learning assessment"
    >
      <div className="panel-heading">
        <h2>Knowledge & learning</h2>
        <span className="badge">
          {state?.after
            ? "Objective practice results"
            : completed
              ? "Post-check due"
              : "Quick knowledge check"}
        </span>
      </div>
      <div
        className="learning-summary"
        aria-label="Learning scores"
        aria-live="polite"
      >
        <div>
          <small>Starting knowledge</small>
          <strong>
            {state?.before ? state.before.score + "%" : "Not recorded"}
          </strong>
          {state?.before && <small>{state.before.correct}/3 correct</small>}
        </div>
        <div>
          <small>Knowledge check</small>
          <strong>{state?.after ? state.after.score + "%" : "Pending"}</strong>
          {state?.after && <small>{state.after.correct}/3 correct</small>}
        </div>
        <div>
          <small>Learning score</small>
          <strong>
            {state?.learning_score != null
              ? state.learning_score + "/100"
              : "Pending"}
          </strong>
          <small>Practice performance</small>
        </div>
        <div>
          <small>Knowledge change</small>
          <strong>
            {state?.gain_pp == null
              ? "Unavailable"
              : (state.gain_pp > 0 ? "+" : "") + state.gain_pp + " pp"}
          </strong>
          <small>Before → after check</small>
        </div>
      </div>
      {error && (
        <p className="error-banner" role="alert">
          {error}{" "}
          <button className="secondary" onClick={() => setRetry((v) => v + 1)}>
            Retry learning check
          </button>
        </p>
      )}
      {!state && !error && <p role="status">Loading learning check…</p>}
      {open && !observing && expanded && question && (
        <div className="quick-check">
          <div className="question-progress">
            <strong>{completed ? "Post-run check" : "Starting check"}</strong>
            <span>Question {questionIndex + 1} of 3</span>
            <progress
              value={questionIndex + 1}
              max={3}
              aria-label="Knowledge check progress"
            />
          </div>
          <fieldset key={phase + "-" + question.id}>
            <legend>{question.prompt}</legend>
            {question.options.map((option, index) => (
              <label key={index} className="quiz-option">
                <input
                  type="radio"
                  name={phase + "-" + run.id + "-" + question.id}
                  checked={choices[question.id] === index}
                  onChange={() =>
                    setChoices((old) => ({ ...old, [question.id]: index }))
                  }
                  disabled={busy}
                />
                {option}
              </label>
            ))}
          </fieldset>
          <div className="actions">
            {questionIndex > 0 && (
              <button
                className="secondary"
                disabled={busy}
                onClick={() => setQuestionIndex((i) => i - 1)}
              >
                Previous question
              </button>
            )}
            {questionIndex < 2 ? (
              <button
                className="primary"
                disabled={busy || choices[question.id] === undefined}
                onClick={() => setQuestionIndex((i) => i + 1)}
              >
                Next question
              </button>
            ) : (
              <button
                className="primary"
                disabled={busy || !ready}
                onClick={submit}
              >
                {completed
                  ? "Show my learning score"
                  : "Save starting knowledge"}
              </button>
            )}
          </div>
          <p className="tiny">
            Three objective questions. One submission per phase; answers are
            reviewed after the post-check.
          </p>
        </div>
      )}
      {open && !observing && !expanded && (
        <button className="secondary" onClick={onOpen}>
          Take knowledge check
        </button>
      )}
      {!completed && state?.before && expanded && (
        <p role="status">
          Baseline saved: {state.before.correct}/3. Explore evidence, diagnose
          the issue and choose a response.
        </p>
      )}
      {!completed && state && !state.before && !open && expanded && (
        <p className="tiny">
          The starting check is closed. You can still complete the post-check;
          knowledge change will be unavailable.
        </p>
      )}
      {completed && state?.after && expanded && (
        <>
          <section
            className="learning-breakdown"
            aria-label="Objective score breakdown"
          >
            <h3>How your practice score was calculated</h3>
            <div className="score-components">
              {Object.entries(state.score_components || {}).map(
                ([key, value]) => (
                  <div key={key}>
                    <span>{scoreLabels[key]}</span>
                    <strong>
                      {value}/{state.max_points[key]}
                    </strong>
                  </div>
                ),
              )}
            </div>
          </section>
          <div className="learning-insights">
            <section>
              <h3>What you demonstrated</h3>
              {state.learning_journey.strengths.length ? (
                <ul>
                  {state.learning_journey.strengths.map((x) => (
                    <li key={x}>{x}</li>
                  ))}
                </ul>
              ) : (
                <p>No positive evidence recorded yet.</p>
              )}
            </section>
            <section>
              <h3>Practise next</h3>
              <ul>
                {state.learning_journey.next_steps.map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
            </section>
          </div>
          <details>
            <summary>Review answers and recorded actions</summary>
            {state.after_questions.map((q) => (
              <div className="answer-review" key={q.id}>
                <strong>{q.prompt}</strong>
                <p>Your answer: {q.options[state.after.choices[q.id]]}</p>
                <p>
                  {state.after.choices[q.id] === state.answer_keys.after[q.id]
                    ? "Correct."
                    : "Expected: " + q.options[state.answer_keys.after[q.id]]}
                </p>
              </div>
            ))}
            <ul>
              <li>
                Investigation before response:{" "}
                {state.evidence.inspected_before_response
                  ? "recorded"
                  : "not recorded"}
              </li>
              <li>
                Correct diagnosis before debrief:{" "}
                {state.evidence.diagnosis_correct ? "recorded" : "not recorded"}
              </li>
              <li>
                Targeted repair with time to take effect:{" "}
                {state.evidence.targeted_repair ? "recorded" : "not recorded"}
              </li>
            </ul>
          </details>
        </>
      )}
      <p className="tiny">
        Practice evidence, not certification. Simulation impact is separate;
        transfer and retention require a later unseen exercise.
      </p>
    </section>
  );
}
