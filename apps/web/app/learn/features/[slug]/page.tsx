import Link from "next/link";
import { notFound } from "next/navigation";
import { FEATURES } from "@/lib/learn-features";
import { ABBREVIATIONS } from "@/lib/learn-glossary";

export function generateStaticParams() {
  return FEATURES.map((f) => ({ slug: f.slug }));
}

export default async function FeatureDeepPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const f = FEATURES.find((x) => x.slug === slug);
  if (!f) notFound();
  const idx = FEATURES.findIndex((x) => x.slug === slug);
  const prev = idx > 0 ? FEATURES[idx - 1] : null;
  const next = idx < FEATURES.length - 1 ? FEATURES[idx + 1] : null;

  return (
    <main className="shell" style={{ maxWidth: 820 }}>
      <div className="topbar">
        <div className="brand-mark">
          <div className="mark">{f.num.replace("F", "")}</div>
          <div>
            <div style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>{f.num}</div>
            <div className="muted" style={{ fontSize: "0.82rem" }}>
              Feature deep dive
            </div>
          </div>
        </div>
        <div className="actions" style={{ marginTop: 0 }}>
          <Link className="btn ghost" href="/learn/glossary">
            Abbr
          </Link>
          <Link className="btn secondary" href="/learn/features">
            All features
          </Link>
        </div>
      </div>

      <div className="chip-row" style={{ marginBottom: "0.75rem" }}>
        <span className="tag role">
          {idx + 1} / {FEATURES.length}
        </span>
        {f.relatedState ? <span className="tag calculated">{f.relatedState}</span> : null}
      </div>

      <h1 style={{ fontFamily: "var(--font-display)", letterSpacing: "-0.03em", fontSize: "clamp(1.5rem, 4vw, 2rem)" }}>
        {f.title}
      </h1>
      <p className="hero-copy">{f.oneLiner}</p>

      <section className="panel soft" style={{ marginBottom: "0.85rem" }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>1. What is this?</h2>
        <p style={{ margin: 0, lineHeight: 1.55 }}>{f.what}</p>
      </section>

      <section className="panel soft" style={{ marginBottom: "0.85rem" }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>2. How we tackle it</h2>
        <p style={{ margin: 0, lineHeight: 1.55 }}>{f.tackle}</p>
      </section>

      <section className="panel soft" style={{ marginBottom: "0.85rem" }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>3. Technology we use</h2>
        <ul style={{ margin: 0, paddingInlineStart: "1.2rem" }}>
          {f.tech.map((t) => (
            <li key={t} style={{ marginBottom: "0.35rem" }}>
              {t}
            </li>
          ))}
        </ul>
      </section>

      <section className="panel soft" style={{ marginBottom: "0.85rem" }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>4. Scripts / files</h2>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.92rem" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "start", borderBottom: "1px solid var(--line)", padding: "0.45rem" }}>
                  Path
                </th>
                <th style={{ textAlign: "start", borderBottom: "1px solid var(--line)", padding: "0.45rem" }}>
                  Role
                </th>
              </tr>
            </thead>
            <tbody>
              {f.scripts.map((s) => (
                <tr key={s.path}>
                  <td style={{ padding: "0.5rem 0.45rem", borderBottom: "1px solid var(--line)", verticalAlign: "top" }}>
                    <code className="code-pill">{s.path}</code>
                  </td>
                  <td style={{ padding: "0.5rem 0.45rem", borderBottom: "1px solid var(--line)" }}>{s.role}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel soft" style={{ marginBottom: "0.85rem" }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>5. How it resolves</h2>
        <p style={{ margin: 0, lineHeight: 1.55 }}>{f.resolve}</p>
      </section>

      <section className="panel soft" style={{ marginBottom: "0.85rem" }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>6. Abbreviations on this page</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          Full glossary: <Link href="/learn/glossary">/learn/glossary</Link>
        </p>
        <ul style={{ margin: 0, paddingInlineStart: "1.2rem" }}>
          {f.abbrUsed.map((code) => {
            const row = ABBREVIATIONS.find((a) => a.abbr === code);
            return (
              <li key={code} style={{ marginBottom: "0.4rem" }}>
                <code className="code-pill">{code}</code>
                {row ? (
                  <>
                    {" "}
                    — <strong>{row.full}</strong>: {row.meaning}
                  </>
                ) : null}
              </li>
            );
          })}
        </ul>
      </section>

      <section className="panel" style={{ marginBottom: "0.85rem", background: "var(--cyan-soft)" }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>Try it in the demo</h2>
        <p style={{ margin: 0 }}>{f.demo}</p>
      </section>

      <div className="actions">
        {prev ? (
          <Link className="btn secondary" href={`/learn/features/${prev.slug}`}>
            ← {prev.num}
          </Link>
        ) : (
          <Link className="btn secondary" href="/learn/features">
            ← Hub
          </Link>
        )}
        {next ? (
          <Link className="btn" href={`/learn/features/${next.slug}`}>
            Next {next.num}: {next.title} →
          </Link>
        ) : (
          <>
            <Link className="btn" href="/learn/game">
              Practice game →
            </Link>
            <Link className="btn secondary" href="/learn/assessment">
              Assessment
            </Link>
          </>
        )}
      </div>
    </main>
  );
}
