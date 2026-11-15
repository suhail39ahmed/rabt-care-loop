"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ASSESSMENT } from "@/lib/learn-content";

type Phase = "ready" | "quiz" | "report";

export default function AssessmentPage() {
  const qs = ASSESSMENT.questions;
  const [phase, setPhase] = useState<Phase>("ready");
  const [idx, setIdx] = useState(0);
  const [answers, setAnswers] = useState<(number | null)[]>(() => qs.map(() => null));
  const [picked, setPicked] = useState<number | null>(null);

  const current = qs[idx];

  const report = useMemo(() => {
    const detail = qs.map((q, i) => {
      const a = answers[i];
      const ok = a === q.answer;
      return { ...q, chosen: a, ok };
    });
    const correct = detail.filter((d) => d.ok).length;
    const percent = Math.round((correct / qs.length) * 100);
    const byTopic: Record<string, { c: number; t: number }> = {};
    for (const d of detail) {
      byTopic[d.topic] ??= { c: 0, t: 0 };
      byTopic[d.topic].t++;
      if (d.ok) byTopic[d.topic].c++;
    }
    return {
      correct,
      total: qs.length,
      percent,
      passed: percent >= ASSESSMENT.passPercent,
      detail,
      byTopic,
    };
  }, [answers, qs]);

  const select = (choice: number) => {
    setPicked(choice);
    setAnswers((prev) => {
      const next = [...prev];
      next[idx] = choice;
      return next;
    });
  };

  const goNext = () => {
    if (picked === null && answers[idx] === null) return;
    if (idx + 1 >= qs.length) {
      setPhase("report");
      return;
    }
    setIdx((i) => i + 1);
    setPicked(answers[idx + 1]);
  };

  const restart = () => {
    setPhase("ready");
    setIdx(0);
    setAnswers(qs.map(() => null));
    setPicked(null);
  };

  return (
    <main className="shell" style={{ maxWidth: 760 }}>
      <div className="topbar">
        <div className="brand-mark">
          <div className="mark">✓</div>
          <div>
            <div style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>Assessment</div>
            <div className="muted" style={{ fontSize: "0.82rem" }}>
              Pass ≥ {ASSESSMENT.passPercent}%
            </div>
          </div>
        </div>
        <Link className="btn secondary" href="/learn">
          Path
        </Link>
      </div>

      {phase === "ready" ? (
        <section className="panel soft rise">
          <h1 className="brand" style={{ fontSize: "clamp(1.6rem, 4vw, 2.2rem)", margin: 0 }}>
            {ASSESSMENT.title}
          </h1>
          <p className="hero-copy">{ASSESSMENT.instructions}</p>
          <ul className="muted">
            <li>{qs.length} questions · ~{ASSESSMENT.timeHintMin} minutes</li>
            <li>Topics: product, workflow, delegation, HITL, architecture</li>
            <li>Suggested order: lessons → practice game → this assessment</li>
          </ul>
          <div className="actions">
            <button
              className="btn"
              type="button"
              onClick={() => {
                setPhase("quiz");
                setIdx(0);
                setPicked(null);
              }}
            >
              Start assessment
            </button>
            <Link className="btn secondary" href="/learn/game">
              Practice first
            </Link>
          </div>
        </section>
      ) : null}

      {phase === "quiz" && current ? (
        <section className="rise">
          <div className="chip-row" style={{ marginBottom: "0.75rem" }}>
            <span className="tag role">
              Q {idx + 1} / {qs.length}
            </span>
            <span className="tag calculated">{current.topic}</span>
          </div>
          <div
            style={{
              height: 8,
              borderRadius: 99,
              background: "var(--line)",
              marginBottom: "1rem",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${((idx + (answers[idx] !== null ? 1 : 0)) / qs.length) * 100}%`,
                height: "100%",
                background: "linear-gradient(90deg, var(--cyan), var(--cyan-deep))",
              }}
            />
          </div>
          <div className="panel">
            <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0, fontSize: "1.25rem" }}>
              {current.q}
            </h2>
            <div className="choices">
              {current.choices.map((c, i) => (
                <button
                  key={c}
                  type="button"
                  className={`choice ${picked === i || answers[idx] === i ? "selected" : ""}`}
                  onClick={() => select(i)}
                >
                  {c}
                </button>
              ))}
            </div>
            <div className="actions">
              <button
                className="btn"
                type="button"
                disabled={answers[idx] === null}
                onClick={goNext}
              >
                {idx + 1 >= qs.length ? "Submit" : "Next"}
              </button>
            </div>
          </div>
        </section>
      ) : null}

      {phase === "report" ? (
        <section className="rise">
          <div
            className="panel soft"
            style={{
              borderColor: report.passed ? "#b7e0c8" : "#f2d2c8",
              background: report.passed ? "linear-gradient(180deg,#fff,#eefaf3)" : "linear-gradient(180deg,#fff,#fff7f4)",
            }}
          >
            <span className={`tag ${report.passed ? "ok" : "urgent"}`}>
              {report.passed ? "PASSED" : "NOT YET"}
            </span>
            <h1 style={{ fontFamily: "var(--font-display)", letterSpacing: "-0.02em" }}>
              {report.percent}% · {report.correct}/{report.total}
            </h1>
            <p className="muted">
              {report.passed
                ? "You understand the Rabt loop: workflow, delegation, HITL, and architecture."
                : `Need ${ASSESSMENT.passPercent}% to pass. Review weak topics below, replay the game, then retry.`}
            </p>
            <div className="kpi-row">
              {Object.entries(report.byTopic).map(([topic, v]) => (
                <div className="kpi" key={topic}>
                  <span className="muted">{topic}</span>
                  <strong>
                    {v.c}/{v.t}
                  </strong>
                </div>
              ))}
            </div>
          </div>

          <div className="panel" style={{ marginTop: "1rem" }}>
            <h3 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>Bit-by-bit review</h3>
            {report.detail.map((d, i) => (
              <div
                key={d.id}
                style={{
                  padding: "0.75rem 0",
                  borderBottom: i < report.detail.length - 1 ? "1px solid var(--line)" : undefined,
                }}
              >
                <div className="chip-row" style={{ marginBottom: "0.35rem" }}>
                  <span className={`tag ${d.ok ? "ok" : "urgent"}`}>{d.ok ? "correct" : "review"}</span>
                  <span className="tag fact">{d.topic}</span>
                </div>
                <strong>{d.q}</strong>
                {!d.ok ? (
                  <p className="muted" style={{ margin: "0.35rem 0 0" }}>
                    Your answer: {d.chosen === null ? "—" : d.choices[d.chosen]}
                    <br />
                    Correct: {d.choices[d.answer]}
                    <br />
                    Why: {d.why}
                  </p>
                ) : (
                  <p className="muted" style={{ margin: "0.35rem 0 0" }}>
                    {d.why}
                  </p>
                )}
              </div>
            ))}
          </div>

          <div className="actions">
            <button className="btn" type="button" onClick={restart}>
              Retake
            </button>
            <Link className="btn secondary" href="/learn">
              Back to path
            </Link>
            <Link className="btn secondary" href="/">
              Try live demo
            </Link>
          </div>
        </section>
      ) : null}
    </main>
  );
}
