"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { AiPanel } from "@/components/AiPanel";
import { KbReview } from "@/components/KbReview";
import { LangSwitcher } from "@/components/LangSwitcher";
import { SafetyPanel } from "@/components/SafetyPanel";
import { STAFF_LOCALES, useLocale } from "@/lib/i18n";

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

function humanState(x: string): string {
  return x.replace(/([a-z])([A-Z])/g, "$1 $2");
}

export default function AdminPage() {
  const L = useLocale({ allowed: STAFF_LOCALES });
  const { s } = L;
  const [k, setK] = useState<Kpis | null>(null);
  const [fair, setFair] = useState<Fairness | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    Promise.all([api<Kpis>("/kpis"), api<Fairness>("/benchmark/fairness")])
      .then(([kpis, fairness]) => {
        setK(kpis);
        setFair(fairness);
      })
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  }, []);

  const pct = (x: number | null | undefined) => (x == null ? "—" : L.num(x, { style: "percent" }));

  return (
    <main className="shell">
      <div className="topbar">
        <div className="brand-mark">
          <div className="mark" aria-hidden="true">
            ر
          </div>
          <div>
            <h1 style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "1.05rem", margin: 0 }}>
              {s("Loop-leak view")}
            </h1>
            <div className="muted" style={{ fontSize: "0.82rem" }}>
              {s("Programme manager")}
            </div>
          </div>
        </div>
        <div className="actions" style={{ marginTop: 0 }}>
          <Link className="btn secondary" href="/board">
            {s("Board")}
          </Link>
          <Link className="btn secondary" href="/insurer">
            {s("Insurer")}
          </Link>
          <LangSwitcher L={L} compact />
        </div>
      </div>

      <div className={`banner ${failed ? "error" : ""}`} role="status">
        {loading ? s("Waking up the demo (up to ~20 s)…") : failed ? s("Could not load metrics.") : s(k?.note || "Synthetic KPIs")}
      </div>

      <div className="kpi-row">
        {(
          [
            ["Cases", k ? L.num(k.total_cases) : "—"],
            ["Closed", k ? L.num(k.closed) : "—"],
            ["Verified closure", k ? pct(k.verified_closure_rate || 0) : "—"],
            [
              "Median time-to-owner",
              k?.time_to_owner_median_hours != null
                ? s("{n} h", { n: L.num(k.time_to_owner_median_hours, { maximumFractionDigits: 1, minimumFractionDigits: 1 }) })
                : "—",
            ],
            ["Critical recall", k ? pct(k.critical_escalation_recall) : "—"],
            ["False closures", k ? L.num(k.false_closures) : "—"],
          ] as Array<[string, string]>
        ).map(([label, value]) => (
          <div className={`kpi ${loading ? "loading" : ""}`} key={label}>
            <span className="muted">{s(label)}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>

      <section className="panel soft" style={{ marginTop: "1rem" }} aria-labelledby="funnel-title">
        <h2 id="funnel-title" style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>
          {s("Leak funnel")}
        </h2>
        <div className="chip-row">
          {(k?.leak_funnel || Object.entries(k?.states || {}).map(([state, count]) => ({ state, count }))).map((row) => (
            <span key={row.state} className="tag role">
              {s(humanState(row.state))}: {L.num(row.count)}
            </span>
          ))}
        </div>
      </section>

      <section className="panel soft" style={{ marginTop: "1rem" }} aria-labelledby="equity-title">
        <h2 id="equity-title" style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>
          {s("Equity panel")}
        </h2>
        <p className="muted">
          {s(fair?.label || "Simulated slices")} ·{" "}
          {s("cells with N < {n} suppressed", { n: L.num(fair?.small_cell_threshold ?? 10) })}
        </p>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">{s("Slice")}</th>
                <th scope="col">{s("Value")}</th>
                <th scope="col" className="num">
                  N
                </th>
                <th scope="col" className="num">
                  {s("Recall")}
                </th>
                <th scope="col" className="num">
                  {s("Hours to next")}
                </th>
              </tr>
            </thead>
            <tbody>
              {(fair?.slices || []).map((row) => (
                <tr key={`${row.slice}-${row.value}`}>
                  <td>{s(row.slice)}</td>
                  <td>{s(row.value)}</td>
                  <td className="num">{row.suppressed ? s(row.n_display) : L.num(row.n)}</td>
                  <td className="num">{row.suppressed ? "—" : pct(row.critical_recall || 0)}</td>
                  <td className="num">
                    {row.suppressed || row.median_hours_to_next_step == null ? "—" : L.num(row.median_hours_to_next_step)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel soft" style={{ marginTop: "1rem" }} aria-labelledby="safety-title">
        <h2 id="safety-title" style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>
          {s("Safety")}
        </h2>
        <p className="muted small" style={{ marginTop: 0 }}>
          {s("Prompt-injection and jailbreak defence")}
        </p>
        <SafetyPanel />
      </section>

      <section className="panel soft" style={{ marginTop: "1rem" }} aria-labelledby="ai-title">
        <h2 id="ai-title" style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>
          {s("AI layer")}
        </h2>
        <p className="muted small" style={{ marginTop: 0 }}>
          {s(
            "Kill switch, safety services, small/strong routing, reviewed prompts, token budget and cache, from this API replica. Counts only, no patient text."
          )}
        </p>
        <AiPanel />
      </section>

      <section className="panel soft" style={{ marginTop: "1rem" }} aria-labelledby="kb-title">
        <h2 id="kb-title" style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>
          {s("Knowledge base review")}
        </h2>
        <KbReview />
      </section>
    </main>
  );
}
