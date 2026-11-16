"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

type Kpis = {
  total_cases: number;
  closed: number;
  critical_total: number;
  critical_escalation_recall: number;
  false_closures: number;
  states: Record<string, number>;
  note: string;
};

function humanState(s: string): string {
  const map: Record<string, string> = {
    PatientNotified: "Patient notified",
    OnHoldConsent: "On hold (consent)",
    ClosurePending: "Closure pending",
    ClosedByHuman: "Closed by human",
    AwaitingOwner: "Awaiting owner",
    DataQuery: "Data query",
    HumanCallback: "Human callback",
    ReferralRejected: "Referral rejected",
  };
  if (map[s]) return map[s];
  return s.replace(/([a-z])([A-Z])/g, "$1 $2");
}

export default function AdminPage() {
  const [k, setK] = useState<Kpis | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<Kpis>("/kpis")
      .then(setK)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="shell">
      <div className="topbar">
        <div className="brand-mark">
          <div className="mark">ر</div>
          <div>
            <h1 style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "1.05rem", margin: 0 }}>
              Loop-leak view
            </h1>
            <div className="muted" style={{ fontSize: "0.82rem" }}>Programme manager</div>
          </div>
        </div>
        <Link className="btn secondary" href="/board">
          Board
        </Link>
      </div>

      <div className="banner">
        {loading ? "Waking up the demo (up to ~20 s)…" : k?.note || "Synthetic KPIs"}
      </div>

      <div className="kpi-row">
        <div className="kpi">
          <span className="muted">Cases</span>
          <strong>{k?.total_cases ?? "—"}</strong>
        </div>
        <div className="kpi">
          <span className="muted">Closed</span>
          <strong>{k?.closed ?? "—"}</strong>
        </div>
        <div className="kpi">
          <span className="muted">Critical recall</span>
          <strong>{k ? `${Math.round(k.critical_escalation_recall * 100)}%` : "—"}</strong>
        </div>
        <div className="kpi">
          <span className="muted">False closures</span>
          <strong>{k?.false_closures ?? "—"}</strong>
        </div>
      </div>

      <section className="panel soft" style={{ marginTop: "1rem" }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>States in flight</h2>
        <div className="chip-row">
          {Object.entries(k?.states || {}).map(([s, n]) => (
            <span key={s} className="tag role">
              {humanState(s)}: {n}
            </span>
          ))}
        </div>
      </section>
    </main>
  );
}
