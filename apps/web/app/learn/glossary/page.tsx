import Link from "next/link";
import { ABBREVIATIONS, ABBREV_GROUPS } from "@/lib/learn-glossary";

export default function GlossaryPage() {
  return (
    <main className="shell" style={{ maxWidth: 860 }}>
      <div className="topbar">
        <div className="brand-mark">
          <div className="mark">A–Z</div>
          <div>
            <div style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>Abbreviations</div>
            <div className="muted" style={{ fontSize: "0.82rem" }}>
              Every short form used in Rabt learn
            </div>
          </div>
        </div>
        <div className="actions" style={{ marginTop: 0 }}>
          <Link className="btn secondary" href="/learn/features">
            Features
          </Link>
          <Link className="btn secondary" href="/learn">
            Path
          </Link>
        </div>
      </div>

      <p className="hero-copy">
        Use this while reading F1–F8. Feature pages also list the abbreviations used on that page.
      </p>

      {ABBREV_GROUPS.map((g) => {
        const rows = ABBREVIATIONS.filter((a) => a.group === g.id).sort((a, b) =>
          a.abbr.localeCompare(b.abbr)
        );
        return (
          <section key={g.id} className="panel soft" style={{ marginBottom: "1rem" }}>
            <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>{g.label}</h2>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.92rem" }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "start", padding: "0.45rem", borderBottom: "1px solid var(--line)" }}>
                      Abbr
                    </th>
                    <th style={{ textAlign: "start", padding: "0.45rem", borderBottom: "1px solid var(--line)" }}>
                      Full form
                    </th>
                    <th style={{ textAlign: "start", padding: "0.45rem", borderBottom: "1px solid var(--line)" }}>
                      Meaning in Rabt
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((a) => (
                    <tr key={a.abbr}>
                      <td style={{ padding: "0.5rem 0.45rem", borderBottom: "1px solid var(--line)", verticalAlign: "top" }}>
                        <code className="code-pill">{a.abbr}</code>
                      </td>
                      <td style={{ padding: "0.5rem 0.45rem", borderBottom: "1px solid var(--line)", verticalAlign: "top" }}>
                        <strong>{a.full}</strong>
                      </td>
                      <td style={{ padding: "0.5rem 0.45rem", borderBottom: "1px solid var(--line)" }}>{a.meaning}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        );
      })}
    </main>
  );
}
