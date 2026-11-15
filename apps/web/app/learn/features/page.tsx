import Link from "next/link";
import { FEATURES } from "@/lib/learn-features";

export default function FeaturesHubPage() {
  return (
    <main className="shell">
      <div className="topbar">
        <div className="brand-mark">
          <div className="mark">F</div>
          <div>
            <div style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>What Rabt adds</div>
            <div className="muted" style={{ fontSize: "0.82rem" }}>
              Full deep-dive · 8 capabilities
            </div>
          </div>
        </div>
        <div className="actions" style={{ marginTop: 0 }}>
          <Link className="btn" href="/learn/glossary">
            Abbreviations A–Z
          </Link>
          <Link className="btn secondary" href="/learn">
            Path
          </Link>
        </div>
      </div>

      <h1 className="brand" style={{ fontSize: "clamp(1.7rem, 4vw, 2.4rem)" }}>
        Feature deep dive
      </h1>
      <p className="hero-copy">
        Each card is one capability: what it means, how we tackle it, which technology and scripts, and how
        the case resolves. Abbreviations are expanded in the text — full list in the glossary.
        Work them in order F1 → F8, then practice + assessment.
      </p>
      <div className="banner">
        Stuck on a short form? Open <Link href="/learn/glossary"><strong>Abbreviations A–Z</strong></Link> —
        covers FHIR, HITL, LLM, AR/EN, HbA1c, MCP, Foundry, and more.
      </div>

      <div className="persona-grid">
        {FEATURES.map((f) => (
          <Link key={f.slug} href={`/learn/features/${f.slug}`} className="panel persona soft">
            <span className="tag role">{f.num}</span>
            <h2>{f.title}</h2>
            <p className="muted" style={{ margin: 0, fontSize: "0.92rem" }}>
              {f.oneLiner}
            </p>
            <span className="go">Deep dive →</span>
          </Link>
        ))}
      </div>

      <div className="actions" style={{ marginTop: "1.25rem" }}>
        <Link className="btn" href={`/learn/features/${FEATURES[0].slug}`}>
          Start F1 · Intake & triage
        </Link>
        <Link className="btn secondary" href="/learn/game">
          Practice game
        </Link>
        <Link className="btn secondary" href="/learn/assessment">
          Assessment
        </Link>
      </div>
    </main>
  );
}
