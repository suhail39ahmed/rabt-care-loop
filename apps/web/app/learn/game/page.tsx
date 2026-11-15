"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { GAME } from "@/lib/learn-game";

type Phase = "intro" | "level" | "boss" | "done";

export default function LearnGamePage() {
  const [phase, setPhase] = useState<Phase>("intro");
  const [levelIdx, setLevelIdx] = useState(0);
  const [roundIdx, setRoundIdx] = useState(0);
  const [score, setScore] = useState(0);
  const [streak, setStreak] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [bossStep, setBossStep] = useState(0);
  const [lives, setLives] = useState(3);

  const level = GAME.levels[levelIdx];
  const round = level?.rounds[roundIdx];
  const totalRounds = useMemo(
    () => GAME.levels.reduce((n, l) => n + l.rounds.length, 0),
    []
  );

  const start = () => {
    setPhase("level");
    setLevelIdx(0);
    setRoundIdx(0);
    setScore(0);
    setStreak(0);
    setPicked(null);
    setRevealed(false);
    setBossStep(0);
    setLives(3);
  };

  const choose = (i: number) => {
    if (revealed || !round) return;
    setPicked(i);
    setRevealed(true);
    if (i === round.answer) {
      const bonus = 10 + streak * 2;
      setScore((s) => s + bonus);
      setStreak((s) => s + 1);
    } else {
      setStreak(0);
      setLives((l) => Math.max(0, l - 1));
    }
  };

  const next = () => {
    if (!level) return;
    if (lives <= 0 && picked !== round?.answer) {
      setPhase("done");
      return;
    }
    if (roundIdx + 1 < level.rounds.length) {
      setRoundIdx((r) => r + 1);
      setPicked(null);
      setRevealed(false);
      return;
    }
    if (levelIdx + 1 < GAME.levels.length) {
      setLevelIdx((l) => l + 1);
      setRoundIdx(0);
      setPicked(null);
      setRevealed(false);
      return;
    }
    setPhase("boss");
    setBossStep(0);
  };

  const advanceBoss = () => {
    if (bossStep + 1 >= GAME.boss.steps.length) {
      setScore((s) => s + 25);
      setPhase("done");
      return;
    }
    setBossStep((s) => s + 1);
  };

  const maxScore = totalRounds * 10 + (totalRounds - 1) * 2 + 25; // rough upper bound

  return (
    <main className="shell" style={{ maxWidth: 820 }}>
      <div className="topbar">
        <div className="brand-mark">
          <div className="mark">ر</div>
          <div>
            <div style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>{GAME.title}</div>
            <div className="muted" style={{ fontSize: "0.82rem" }}>
              Learning game
            </div>
          </div>
        </div>
        <div className="actions" style={{ marginTop: 0 }}>
          <Link className="btn ghost" href="/learn">
            Notes
          </Link>
          <Link className="btn secondary" href="/">
            Home
          </Link>
        </div>
      </div>

      {phase !== "intro" && phase !== "done" ? (
        <div className="chip-row rise" style={{ marginBottom: "0.85rem" }}>
          <span className="tag role">Score {score}</span>
          <span className="tag calculated">Streak {streak}</span>
          <span className="tag urgent">Lives {"♥".repeat(lives)}{"♡".repeat(3 - lives)}</span>
        </div>
      ) : null}

      {phase === "intro" ? (
        <section className="panel soft rise">
          <h1 className="brand" style={{ fontSize: "clamp(1.7rem, 4vw, 2.4rem)", margin: 0 }}>
            {GAME.title}
          </h1>
          <p className="hero-copy">{GAME.tagline}</p>
          <div className="flow" style={{ marginBottom: "1rem" }}>
            <span className="node det">Workflow</span>
            <span className="arrow">→</span>
            <span className="node ai">Delegation</span>
            <span className="arrow">→</span>
            <span className="node human">HITL</span>
            <span className="arrow">→</span>
            <span className="node det">Boss: close Fatima’s loop</span>
          </div>
          <p className="muted">
            Remember: <strong>deterministic code decides</strong>, the LLM explains, humans gate unsafe paths.
            Not LangChain — Coordinator + state machine (+ Foundry optional for text).
          </p>
          <div className="actions">
            <button className="btn" type="button" onClick={start}>
              Play
            </button>
            <Link className="btn secondary" href="/learn">
              Read first
            </Link>
          </div>
        </section>
      ) : null}

      {phase === "level" && level && round ? (
        <section className="rise">
          <div className="panel soft" style={{ marginBottom: "0.85rem" }}>
            <div className="chip-row">
              <span className="tag role">
                Level {levelIdx + 1}/{GAME.levels.length}
              </span>
              <span className="tag fact">
                Q {roundIdx + 1}/{level.rounds.length}
              </span>
            </div>
            <h2 style={{ fontFamily: "var(--font-display)", letterSpacing: "-0.02em", margin: "0.55rem 0" }}>
              {level.title}
            </h2>
            <p className="muted" style={{ marginTop: 0 }}>
              {level.blurb}
            </p>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={level.diagram}
              alt={level.title}
              style={{
                width: "100%",
                borderRadius: "0.85rem",
                border: "1px solid var(--line)",
                background: "white",
                marginTop: "0.35rem",
              }}
            />
          </div>

          <div className="panel">
            <h3 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>{round.q}</h3>
            <div className="choices">
              {round.choices.map((c, i) => {
                let cls = "choice";
                if (revealed && i === round.answer) cls += " selected";
                if (revealed && picked === i && i !== round.answer) cls += " wrong";
                return (
                  <button key={c} type="button" className={cls} onClick={() => choose(i)} disabled={revealed}>
                    {c}
                  </button>
                );
              })}
            </div>
            {revealed ? (
              <div
                className="banner"
                style={{
                  marginTop: "1rem",
                  marginBottom: 0,
                  background: picked === round.answer ? "#e3f6ec" : "#fff7f4",
                  borderColor: picked === round.answer ? "#b7e0c8" : "#f2d2c8",
                  color: picked === round.answer ? "#1f5c3a" : "#7a3b2c",
                }}
              >
                {picked === round.answer ? "Correct — " : "Not quite — "}
                {round.why}
              </div>
            ) : null}
            {revealed ? (
              <div className="actions">
                <button className="btn" type="button" onClick={next}>
                  {lives <= 0 && picked !== round.answer
                    ? "See results"
                    : roundIdx + 1 >= level.rounds.length && levelIdx + 1 >= GAME.levels.length
                      ? "Boss round"
                      : "Next"}
                </button>
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      {phase === "boss" ? (
        <section className="panel soft rise">
          <span className="tag calculated">Boss</span>
          <h2 style={{ fontFamily: "var(--font-display)" }}>{GAME.boss.title}</h2>
          <p className="muted">Tap each step in order to close Fatima’s HbA1c loop (SC-01).</p>
          <ol style={{ paddingInlineStart: "1.1rem" }}>
            {GAME.boss.steps.map((s, i) => (
              <li
                key={s.label}
                style={{
                  marginBottom: "0.55rem",
                  opacity: i > bossStep ? 0.35 : 1,
                  fontWeight: i === bossStep ? 700 : 400,
                }}
              >
                {s.label}
                {i < bossStep ? (
                  <span className="tag ok" style={{ marginInlineStart: "0.45rem" }}>
                    {s.ok}
                  </span>
                ) : null}
              </li>
            ))}
          </ol>
          <div className="panel" style={{ boxShadow: "none", marginBottom: "0.75rem" }}>
            <strong>Now:</strong> {GAME.boss.steps[bossStep].label}
            <div className="muted">{GAME.boss.steps[bossStep].ok}</div>
          </div>
          <button className="btn" type="button" onClick={advanceBoss}>
            {bossStep + 1 >= GAME.boss.steps.length ? "Close the loop" : "Advance state →"}
          </button>
        </section>
      ) : null}

      {phase === "done" ? (
        <section className="panel soft rise">
          <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>
            {lives > 0 ? GAME.boss.win : "Loop paused — try again"}
          </h2>
          <div className="kpi-row">
            <div className="kpi">
              <span className="muted">Score</span>
              <strong>{score}</strong>
            </div>
            <div className="kpi">
              <span className="muted">Lives left</span>
              <strong>{lives}</strong>
            </div>
            <div className="kpi">
              <span className="muted">Target ~</span>
              <strong>{maxScore}</strong>
            </div>
          </div>
          <p className="muted" style={{ marginTop: "1rem" }}>
            Next: open the real demo — Fatima (workflow), Coordinator (HITL), GC-10 Try close (closure gate).
          </p>
          <div className="actions">
            <button className="btn" type="button" onClick={start}>
              Play again
            </button>
            <Link className="btn secondary" href="/">
              Guest demo
            </Link>
            <Link className="btn secondary" href="/learn">
              Concept notes
            </Link>
          </div>
        </section>
      ) : null}

      </main>
  );
}
