import Link from "next/link";
import { MODULES } from "@/lib/learn-content";

export default function LearnHubPage() {
  return (
    <main className="shell">
      <div className="topbar">
        <div className="brand-mark">
          <div className="mark">ر</div>
          <div>
            <div style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>Learn Rabt</div>
            <div className="muted" style={{ fontSize: "0.82rem" }}>
              Lessons → practice → assessment
            </div>
          </div>
        </div>
        <Link className="btn secondary" href="/">
          Demo home
        </Link>
      </div>

      <h1 className="brand" style={{ fontSize: "clamp(1.8rem, 4vw, 2.6rem)", marginTop: "0.5rem" }}>
        Understand what we are building
      </h1>
      <p className="hero-copy">
        Go deep bit by bit: the care-loop product, each capability we add (intake → audit), the
        state-machine workflow, delegation, HITL — then practice and a scored assessment.
      </p>

      <div className="banner">
        Suggested path: lessons 1–5 → <strong>What Rabt adds (F1–F8)</strong> → practice game → assessment
        (pass ≥ 80%). Sources in <code className="code-pill">learn/</code>.
      </div>

      <section className="panel soft" style={{ marginBottom: "1rem", background: "var(--cyan-soft)" }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>Deep dive · What Rabt adds</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          For every capability: what it is, how we tackle it, technology, scripts, and how the case resolves.
        </p>
        <div className="actions" style={{ marginTop: "0.75rem" }}>
          <Link className="btn" href="/learn/features">
            Open F1–F8 deep dive
          </Link>
          <Link className="btn secondary" href="/learn/glossary">
            Abbreviations A–Z
          </Link>
        </div>
      </section>

      <section className="panel soft" style={{ marginBottom: "1rem" }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>Your learning path</h2>
        <ol style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {MODULES.map((m, i) => (
            <li key={m.slug} style={{ marginBottom: "0.65rem" }}>
              <Link
                href={`/learn/modules/${m.slug}`}
                className="panel"
                style={{
                  display: "grid",
                  gridTemplateColumns: "auto 1fr auto",
                  gap: "0.85rem",
                  alignItems: "center",
                  boxShadow: "none",
                  padding: "0.85rem 1rem",
                }}
              >
                <span className="step-num">{i + 1}</span>
                <span>
                  <strong style={{ fontFamily: "var(--font-display)" }}>{m.title}</strong>
                  <div className="muted" style={{ fontSize: "0.9rem" }}>
                    {m.summary} · ~{m.minutes} min
                  </div>
                </span>
                <span className="go" style={{ color: "var(--cyan-deep)", fontWeight: 600 }}>
                  Open →
                </span>
              </Link>
            </li>
          ))}
          <li style={{ marginBottom: "0.65rem" }}>
            <Link
              href="/learn/game"
              className="panel"
              style={{
                display: "grid",
                gridTemplateColumns: "auto 1fr auto",
                gap: "0.85rem",
                alignItems: "center",
                boxShadow: "none",
                padding: "0.85rem 1rem",
                background: "var(--cyan-soft)",
              }}
            >
              <span className="step-num">6</span>
              <span>
                <strong style={{ fontFamily: "var(--font-display)" }}>Practice game</strong>
                <div className="muted" style={{ fontSize: "0.9rem" }}>
                  Close the Loop — workflow, delegation, HITL + boss round
                </div>
              </span>
              <span style={{ color: "var(--cyan-deep)", fontWeight: 600 }}>Play →</span>
            </Link>
          </li>
          <li>
            <Link
              href="/learn/assessment"
              className="panel"
              style={{
                display: "grid",
                gridTemplateColumns: "auto 1fr auto",
                gap: "0.85rem",
                alignItems: "center",
                boxShadow: "none",
                padding: "0.85rem 1rem",
                background: "#fff7f4",
                borderColor: "#f2d2c8",
              }}
            >
              <span className="step-num" style={{ background: "var(--coral)" }}>
                7
              </span>
              <span>
                <strong style={{ fontFamily: "var(--font-display)" }}>Assessment</strong>
                <div className="muted" style={{ fontSize: "0.9rem" }}>
                  15 questions · pass at 80% · topic breakdown + review
                </div>
              </span>
              <span style={{ color: "#a54731", fontWeight: 600 }}>Assess →</span>
            </Link>
          </li>
        </ol>
      </section>

      <section className="panel">
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>After you pass</h2>
        <p className="muted">
          Apply it on the live synthetic demo: Fatima (workflow + teach-back), Coordinator board (HITL
          critical), GC-10 Try close (evidence gate).
        </p>
        <div className="actions">
          <Link className="btn" href="/learn/modules/what-is-rabt">
            Start lesson 1
          </Link>
          <Link className="btn secondary" href="/">
            Guest demo
          </Link>
        </div>
      </section>
    </main>
  );
}
