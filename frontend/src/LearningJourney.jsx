import React from "react";

export function LearningJourney({ run, observing, onView, onStart, busy }) {
  const progress = run.learning_progress || {};
  const completed = run.tick >= run.horizon;
  const started =
    run.tick > 0 || !!run.clock?.started_at || run.decisions.length > 0;
  const stages = [
    ["Mission", "Understand your role and goal", "brief"],
    [
      "Knowledge check",
      progress.baseline_recorded
        ? "Starting point recorded"
        : started
          ? "Baseline not recorded"
          : "3 questions before practice",
      "Learning",
    ],
    [
      "Simulation",
      completed
        ? "Run completed"
        : started
          ? "Inspect, diagnose and respond"
          : "Investigate, diagnose and respond",
      "World map",
    ],
    [
      "Results & learning",
      progress.post_submitted
        ? "Objective results available"
        : completed
          ? "Check what you learned"
          : "After the simulation",
      "Debrief",
    ],
  ];
  const next = completed
    ? [
        progress.post_submitted ? "View my learning" : "Check what I learned",
        () => onView("Learning"),
      ]
    : !started && !progress.baseline_recorded
      ? ["Take quick knowledge check", () => onView("Learning")]
      : !started
        ? ["Start simulation", onStart]
        : ["Review evidence", () => onView("Evidence locker")];
  return (
    <section className="panel learning-journey" aria-label="Learning journey">
      <div className="journey-mission" id="learning-mission">
        <div>
          <span className="eyebrow">
            {observing
              ? "LEARNER JOURNEY · OBSERVATION"
              : "YOUR LEARNING JOURNEY"}
          </span>
          <h2>{run.briefing?.role || "Your mission"}</h2>
          <p>{run.briefing?.mission}</p>
          <p className="mission-success">
            <strong>Success:</strong> {run.briefing?.success}
          </p>
        </div>
        {!observing && (
          <button className="primary" disabled={busy} onClick={next[1]}>
            {next[0]}
          </button>
        )}
      </div>
      <ol className="journey-steps">
        {stages.map(([title, subtitle, view], index) => (
          <li key={title}>
            <button
              className="journey-step"
              disabled={view === "Debrief" && !completed}
              onClick={() => {
                if (view === "brief")
                  document
                    .getElementById("learning-mission")
                    ?.scrollIntoView({ behavior: "smooth", block: "center" });
                else onView(view);
              }}
            >
              <span className="journey-number">{index + 1}</span>
              <span>
                <strong>{title}</strong>
                <small>{subtitle}</small>
              </span>
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}
