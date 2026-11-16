import Link from "next/link";
import { api } from "@/lib/api";

type Demo = {
  banner: string;
  personas: Array<{
    id: string;
    label: string;
    role: string;
    case_id?: string;
    locale?: string;
  }>;
  cases?: Record<string, string>;
};

export default async function HomePage() {
  let demo: Demo | null = null;
  try {
    demo = await api<Demo>("/demo");
  } catch {
    demo = null;
  }

  const roleHint: Record<string, string> = {
    patient: "Arabic result card · teach-back · book",
    physician: "Accept ownership · e-consult · close",
    coordinator: "Critical ladder · queue · HITL",
  };

  return (
    <main className="shell">
      <div className="topbar rise">
        <div className="brand-mark">
          <div className="mark">ر</div>
          <div>
            <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "1.05rem" }}>
              ربط · Rabt
            </div>
            <div className="muted" style={{ fontSize: "0.82rem" }}>
              Care-loop demo for screening follow-up
            </div>
          </div>
        </div>
        <div className="actions" style={{ marginTop: 0 }}>
          <Link className="btn" href="/board">
            Board
          </Link>
          <Link className="btn secondary" href="/admin">
            KPIs
          </Link>
        </div>
      </div>

      <section className="rise d2" style={{ marginTop: "1.5rem" }}>
        <div className="chip-row">
          <span className="tag role">Guest demo</span>
          <span className="tag fact">FHIR-native</span>
          <span className="tag calculated">Deterministic safety</span>
        </div>
        <h1 className="brand" style={{ marginTop: "0.85rem" }}>
          Rabt
          <small>No result left behind</small>
        </h1>
        <p className="hero-copy">
          A care-loop layer that sits with the patient app: every screening result gets an owner,
          an in-network next step, and documented closure — with humans on the safety path.
        </p>
      </section>

      <div className="banner rise d3">
        {demo?.banner || "Synthetic data. Demo only. Shared demo — data resets on restart."}
      </div>

      <section className="panel soft rise d3" style={{ marginTop: "1rem" }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>Judge mode — 6-step tour</h2>
        <p className="muted">One-click path through the live care loop using stable demo IDs.</p>
        <ol style={{ margin: 0, paddingInlineStart: "1.2rem" }}>
          <li>
            <Link href={`/patient/${demo?.cases?.gc01_fatima_hba1c || "case-gc01-fatima"}?lang=ar`}>
              Fatima patient card (AR)
            </Link>
          </li>
          <li>
            <Link href={`/board?focus=${demo?.cases?.gc03_owner || "case-gc03-owner"}`}>
              Accept ownership (Dr Aisha)
            </Link>
          </li>
          <li>
            <Link href={`/board?focus=${demo?.cases?.gc02_critical_bp || "case-gc02-bp"}`}>
              Critical ladder + expert call
            </Link>
          </li>
          <li>
            <Link href="/board">HITL queue &amp; two-person close</Link>
          </li>
          <li>
            <Link href="/admin">Impact metrics &amp; equity</Link>
          </li>
          <li>
            <Link href={`/board?focus=${demo?.cases?.gc01_fatima_hba1c || "case-gc01-fatima"}`}>
              Why? panel + evidence pack
            </Link>
          </li>
        </ol>
      </section>

      <section className="persona-grid rise d3">
        {(demo?.personas || []).map((p) => {
          const href =
            p.role === "patient"
              ? `/patient/${p.case_id}?lang=${p.locale || "en"}`
              : `/board?focus=${p.case_id || ""}`;
          return (
            <Link key={p.id} href={href} className="panel persona soft">
              <span className="tag role">{p.role}</span>
              <h2>{p.label}</h2>
              <p className="muted" style={{ margin: 0, fontSize: "0.92rem" }}>
                {roleHint[p.role] || "Open demo case"}
              </p>
              <span className="go">Enter →</span>
            </Link>
          );
        })}
      </section>

      <section className="panel rise d4" style={{ marginTop: "1.25rem" }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0, letterSpacing: "-0.02em" }}>
          Where the agents live
        </h2>
        <div className="flow" style={{ marginBottom: "0.85rem" }}>
          <span className="node det">DQ</span>
          <span className="arrow">→</span>
          <span className="node det">Triage</span>
          <span className="arrow">→</span>
          <span className="node det">Ownership</span>
          <span className="arrow">→</span>
          <span className="node ai">Comms</span>
          <span className="arrow">→</span>
          <span className="node human">HITL</span>
          <span className="arrow">→</span>
          <span className="node det">Closure</span>
        </div>
        <p className="muted" style={{ margin: 0 }}>
          Yellow = deterministic · Violet = AI-generated text (only when an LLM ran) · Coral = human gate.
          Designed to sit alongside a patient app such as Sehatna (mocked here — no affiliation implied).
        </p>
        <div className="actions">
          <Link className="btn" href="/board">
            Open HITL board
          </Link>
          <Link className="btn secondary" href="/admin">
            Programme KPIs
          </Link>
        </div>
      </section>
    </main>
  );
}
