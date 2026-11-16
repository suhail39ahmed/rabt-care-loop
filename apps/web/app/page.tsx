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
          <Link className="btn secondary" href="/insurer">
            Insurer
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

      <section className="panel soft rise d3" style={{ marginTop: "1rem" }} aria-labelledby="tour">
        <h2 id="tour" style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>
          Demo tour: from result to closure
        </h2>
        <p className="muted">Follow one loop end to end with stable demo cases. Each step opens in this app.</p>
        <ol className="tour">
          <li>
            <Link href={`/patient/${demo?.cases?.gc01_fatima_hba1c || "case-gc01-fatima"}?lang=ar`}>Result card in Arabic</Link>
            <span className="muted"> · Fatima sees her HbA1c, &quot;not a diagnosis&quot;, and can listen to it</span>
          </li>
          <li>
            <Link href={`/patient/${demo?.cases?.gc01_fatima_hba1c || "case-gc01-fatima"}?lang=en`}>Understanding (teach-back)</Link>
            <span className="muted"> · two questions before any booking; ask the approved knowledge base</span>
          </li>
          <li>
            <Link href={`/patient/${demo?.cases?.gc05_fit || "case-gc05-fit"}?lang=en`}>Navigator: cashless or pay-and-claim</Link>
            <span className="muted"> · Ravi&apos;s options, cashless network first, with how to claim money back</span>
          </li>
          <li>
            <Link href={`/patient/${demo?.cases?.gc10_closure || "case-gc10-closure"}?lang=en`}>Booking</Link>
            <span className="muted"> · Omar&apos;s appointment and what he pays at the clinic</span>
          </li>
          <li>
            <Link href={`/board?focus=${demo?.cases?.gc02_critical_bp || "case-gc02-bp"}`}>Board: owner, critical ladder, two-person close</Link>
            <span className="muted"> · humans on every safety gate; closure needs evidence</span>
          </li>
          <li>
            <Link href="/insurer">Insurer agent (A2A)</Link>
            <span className="muted"> · signed exchanges, untrusted replies checked</span>
          </li>
          <li>
            <Link href="/admin">Impact metrics and equity</Link>
            <span className="muted"> · false closures, critical recall, fairness slices</span>
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
