"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { AiPanel } from "@/components/AiPanel";
import { KbReview } from "@/components/KbReview";

type Kpis = {
  total_cases: number;
  closed: number;
  critical_total: number;
  critical_escalation_recall: number;
  false_closures: number;
  verified_closure_rate?: number;
  time_to_owner_median_hours?: number | null;
  leak_funnel?: Array<{ state: string; count: number }>;
  states: Record<string, number>;
  note: string;
};

type Fairness = {
  label: string;
  small_cell_threshold: number;
  slices: Array<{
    slice: string;
    value: string;
    n: number;
    n_display: string;
    suppressed: boolean;
    critical_recall: number | null;
    false_closures: number | null;
    median_hours_to_next_step: number | null;
  }>;
};

function humanState(s: string): string {
  return s.replace(/([a-z])([A-Z])/g, "$1 $2");
}

export default function AdminPage() {
  const [k, setK] = useState<Kpis | null>(null);
  const [fair, setFair] = useState<Fairness | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api<Kpis>("/kpis"), api<Fairness>("/benchmark/fairness")])
      .then(([kpis, fairness]) => {
        setK(kpis);
        setFair(fairness);
      })
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
        <div className="actions" style={{ marginTop: 0 }}>
          <Link className="btn secondary" href="/board">
            Board
          </Link>
          <Link className="btn secondary" href="/insurer">
            Insurer
          </Link>
        </div>
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
          <span className="muted">Verified closure</span>
          <strong>{k ? `${Math.round((k.verified_closure_rate || 0) * 100)}%` : "—"}</strong>
        </div>
        <div className="kpi">
          <span className="muted">Median time-to-owner</span>
          <strong>
            {k?.time_to_owner_median_hours != null ? `${k.time_to_owner_median_hours.toFixed(1)} h` : "—"}
          </strong>
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
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>Leak funnel</h2>
        <div className="chip-row">
          {(k?.leak_funnel || Object.entries(k?.states || {}).map(([state, count]) => ({ state, count }))).map(
            (row) => (
              <span key={row.state} className="tag role">
                {humanState(row.state)}: {row.count}
              </span>
            )
          )}
        </div>
      </section>

      <section className="panel soft" style={{ marginTop: "1rem" }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>Equity panel</h2>
        <p className="muted">{fair?.label || "Simulated slices"} · cells with N &lt; {fair?.small_cell_threshold ?? 10} suppressed</p>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
          <thead>
            <tr>
              <th align="left">Slice</th>
              <th align="left">Value</th>
              <th align="right">N</th>
              <th align="right">Recall</th>
              <th align="right">Hours to next</th>
            </tr>
          </thead>
          <tbody>
            {(fair?.slices || []).map((s) => (
              <tr key={`${s.slice}-${s.value}`}>
                <td>{s.slice}</td>
                <td>{s.value}</td>
                <td align="right">{s.n_display}</td>
                <td align="right">
                  {s.suppressed ? "—" : `${Math.round((s.critical_recall || 0) * 100)}%`}
                </td>
                <td align="right">{s.suppressed ? "—" : s.median_hours_to_next_step}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="panel soft" style={{ marginTop: "1rem" }} aria-labelledby="ai-title">
        <h2 id="ai-title" style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>AI layer</h2>
        <p className="muted small" style={{ marginTop: 0 }}>
          Kill switch, safety services, small/strong routing, reviewed prompts, token budget and cache, from this API
          replica. Counts only, no patient text.
        </p>
        <AiPanel />
      </section>

      <section className="panel soft" style={{ marginTop: "1rem" }} aria-labelledby="kb-title">
        <h2 id="kb-title" style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>Knowledge base review</h2>
        <KbReview />
      </section>
    </main>
  );
}
