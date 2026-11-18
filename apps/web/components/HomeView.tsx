"use client";

import Link from "next/link";
import { LangSwitcher } from "@/components/LangSwitcher";
import { STAFF_LOCALES, useLocale } from "@/lib/i18n";

export type Demo = {
  banner: string;
  personas: Array<{ id: string; label: string; role: string; case_id?: string; locale?: string }>;
  cases?: Record<string, string>;
};

const ROLE_HINT: Record<string, string> = {
  patient: "Arabic result card · teach-back · book",
  physician: "Accept ownership · e-consult · close",
  coordinator: "Critical ladder · queue · HITL",
};

export function HomeView({ demo }: { demo: Demo | null }) {
  const L = useLocale({ allowed: STAFF_LOCALES });
  const { s } = L;
  const c = demo?.cases || {};
  const fatima = c.gc01_fatima_hba1c || "case-gc01-fatima";
  const tour: Array<{ href: string; title: string; hint: string }> = [
    { href: `/patient/${fatima}?lang=ar`, title: "Result card in Arabic", hint: 'Fatima sees her HbA1c, "not a diagnosis", and can listen to it' },
    { href: `/patient/${fatima}?lang=en`, title: "Understanding (teach-back)", hint: "two questions before any booking; ask the approved knowledge base" },
    { href: `/patient/${c.gc05_fit || "case-gc05-fit"}?lang=en`, title: "Navigator: cashless or pay-and-claim", hint: "Ravi's options, cashless network first, with how to claim money back" },
    { href: `/patient/${c.gc10_closure || "case-gc10-closure"}?lang=en`, title: "Booking", hint: "Omar's appointment and what he pays at the clinic" },
    { href: `/patient/${c.gc11_senior || "case-gc11-senior"}?lang=ar&easy=1`, title: "Senior easy mode", hint: "Saeed, 68: large text, one step at a time, call me instead" },
    { href: `/board?focus=${c.gc02_critical_bp || "case-gc02-bp"}`, title: "Board: owner, critical ladder, two-person close", hint: "humans on every safety gate; closure needs evidence" },
    { href: "/demo/split", title: "Split-screen demo", hint: "patient phone and coordinator board side by side, live" },
    { href: "/insurer", title: "Insurer agent (A2A)", hint: "signed exchanges, untrusted replies checked" },
    { href: "/admin", title: "Impact metrics and equity", hint: "false closures, critical recall, fairness slices" },
  ];

  return (
    <main className="shell">
      <div className="topbar rise">
        <div className="brand-mark">
          <div className="mark" aria-hidden="true">
            ر
          </div>
          <div>
            <div style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "1.05rem" }}>
              <span lang="ar">ربط</span> · <span lang="en">Rabt</span>
            </div>
            <div className="muted" style={{ fontSize: "0.82rem" }}>
              {s("Care-loop demo for screening follow-up")}
            </div>
          </div>
        </div>
        <div className="actions" style={{ marginTop: 0 }}>
          <Link className="btn" href="/board">
            {s("Board")}
          </Link>
          <Link className="btn secondary" href="/admin">
            {s("KPIs")}
          </Link>
          <Link className="btn secondary" href="/insurer">
            {s("Insurer")}
          </Link>
          <LangSwitcher L={L} compact />
        </div>
      </div>

      <section className="rise d2" style={{ marginTop: "1.5rem" }}>
        <div className="chip-row">
          <span className="tag role">{s("Guest demo")}</span>
          <span className="tag fact">{s("FHIR-native")}</span>
          <span className="tag calculated">{s("Deterministic safety")}</span>
        </div>
        <h1 className="brand" style={{ marginTop: "0.85rem" }}>
          {s("Rabt")}
          <small>{s("No result left behind")}</small>
        </h1>
        <p className="hero-copy">
          {s(
            "A care-loop layer that sits with the patient app: every screening result gets an owner, an in-network next step, and documented closure — with humans on the safety path."
          )}
        </p>
      </section>

      <div className="banner rise d3">
        {s(demo?.banner || "Synthetic data. Demo only. Shared demo — data resets on restart.")}
      </div>

      <section className="panel soft rise d3" style={{ marginTop: "1rem" }} aria-labelledby="tour">
        <h2 id="tour" style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>
          {s("Demo tour: from result to closure")}
        </h2>
        <p className="muted">{s("Follow one loop end to end with stable demo cases. Each step opens in this app.")}</p>
        <ol className="tour">
          {tour.map((t) => (
            <li key={t.title}>
              <Link href={t.href}>{s(t.title)}</Link>
              <span className="muted"> · {s(t.hint)}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="persona-grid rise d3">
        {(demo?.personas || []).map((p) => {
          const href = p.role === "patient" ? `/patient/${p.case_id}?lang=${p.locale || "en"}` : `/board?focus=${p.case_id || ""}`;
          return (
            <Link key={p.id} href={href} className="panel persona soft">
              <span className="tag role">{s(p.role)}</span>
              <h2>{s(p.label)}</h2>
              <p className="muted" style={{ margin: 0, fontSize: "0.92rem" }}>
                {s(ROLE_HINT[p.role] || "Open demo case")}
              </p>
              <span className="go">{s("Enter →")}</span>
            </Link>
          );
        })}
      </section>

      <section className="panel rise d4" style={{ marginTop: "1.25rem" }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0, letterSpacing: "-0.02em" }}>{s("Where the agents live")}</h2>
        <div className="flow" style={{ marginBottom: "0.85rem" }}>
          {(
            [
              ["det", "DQ"],
              ["det", "Triage"],
              ["det", "Ownership"],
              ["ai", "Comms"],
              ["human", "HITL"],
              ["det", "Closure"],
            ] as Array<[string, string]>
          ).map(([cls, label], i) => (
            <span key={label} style={{ display: "contents" }}>
              {i ? (
                <span className="arrow" aria-hidden="true">
                  →
                </span>
              ) : null}
              <span className={`node ${cls}`}>{s(label)}</span>
            </span>
          ))}
        </div>
        <p className="muted" style={{ margin: 0 }}>
          {s(
            "Yellow = deterministic · Violet = AI-generated text (only when an LLM ran) · Coral = human gate. Designed to sit alongside a patient app such as Sehatna (mocked here — no affiliation implied)."
          )}
        </p>
        <div className="actions">
          <Link className="btn" href="/board">
            {s("Open HITL board")}
          </Link>
          <Link className="btn secondary" href="/admin">
            {s("Programme KPIs")}
          </Link>
        </div>
      </section>
    </main>
  );
}
