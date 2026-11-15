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

export default function AdminPage() {
  const [k, setK] = useState<Kpis | null>(null);

  useEffect(() => {
    api<Kpis>("/kpis").then(setK).catch(console.error);
  }, []);

  return (
    <main className="shell">
      <div className="topbar">
        <div className="brand-mark">
          <div className="mark">ر</div>
          <div>
            <div style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>Loop-leak view</div>
            <div className="muted" style={{ fontSize: "0.82rem" }}>Programme manager</div>
          </div>
        </div>
        <Link className="btn secondary" href="/board">
          Board
        </Link>
      </div>

      <div className="banner">{k?.note || "Synthetic KPIs"}</div>

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
              {s}: {n}
            </span>
          ))}
        </div>
      </section>
    </main>
  );
}
