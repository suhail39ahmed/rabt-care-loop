"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { STAFF_LOCALES, useLocale } from "@/lib/i18n";

type Safety = {
  benchmark: {
    cases?: Array<{ id: string; kind: string; expect: "blocked" | "allowed"; outcome: string; pass: boolean }>;
    attack_block_rate?: number;
    false_positive_rate?: number;
    passed?: number;
    total?: number;
  } | null;
  live: { injection_blocks: number; prompt_shield_blocks: number; gateway_safety_blocks: number; content_safety_blocks: number };
};

/** Prompt-injection and jailbreak defence: the offline benchmark plus what this replica blocked live. Counts only. */
export function SafetyPanel() {
  const L = useLocale({ allowed: STAFF_LOCALES });
  const { s } = L;
  const [d, setD] = useState<Safety | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    api<Safety>("/benchmark/safety")
      .then(setD)
      .catch(() => setFailed(true));
  }, []);

  if (failed) return <p className="muted">{s("Safety metrics unavailable.")}</p>;
  if (!d)
    return (
      <div className="skeleton-list" role="status" aria-label={s("Loading…")}>
        <span />
      </div>
    );
  const b = d.benchmark || {};
  const rows = b.cases || [];
  const attacks = rows.filter((r) => r.expect === "blocked").length;
  const benign = rows.filter((r) => r.expect === "allowed").length;
  const layers: Array<[string, number]> = [
    [s("Deny-list"), d.live.injection_blocks],
    [s("Prompt Shields"), d.live.prompt_shield_blocks],
    [s("Gateway (APIM)"), d.live.gateway_safety_blocks],
    [s("Content safety"), d.live.content_safety_blocks],
  ];
  const total = layers.reduce((a, [, n]) => a + n, 0);

  return (
    <div className="safety-grid">
      <div className="kpi-row compact">
        <div className="kpi">
          <span className="muted">{s("Benchmark block rate")}</span>
          <strong>{b.attack_block_rate != null ? L.num(b.attack_block_rate, { style: "percent" }) : "—"}</strong>
        </div>
        <div className="kpi">
          <span className="muted">{s("False positives")}</span>
          <strong>{b.false_positive_rate != null ? L.num(b.false_positive_rate, { style: "percent" }) : "—"}</strong>
        </div>
        <div className="kpi">
          <span className="muted">{s("Attack cases")}</span>
          <strong>{rows.length ? L.num(attacks) : "—"}</strong>
        </div>
        <div className="kpi">
          <span className="muted">{s("Benign cases")}</span>
          <strong>{rows.length ? L.num(benign) : "—"}</strong>
        </div>
      </div>
      <h3 className="small-title">
        {s("Blocked live (this replica)")} <span className="tag urgent">{L.num(total)}</span>
      </h3>
      <ul className="small counters" data-testid="safety-counter">
        {layers.map(([label, n]) => (
          <li key={label}>
            <span>{label}</span>
            <strong>{L.num(n)}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}
