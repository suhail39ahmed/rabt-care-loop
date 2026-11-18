"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { STAFF_LOCALES, useLocale } from "@/lib/i18n";

type Metrics = {
  ai_enabled: boolean;
  llm_configured: boolean;
  content_safety: boolean;
  router: {
    small: string | null;
    strong: string | null;
    mode?: string;
    azure_model_router?: string | null;
    tasks: Record<string, { tier: string; max_tokens: number; cacheable: boolean }>;
  };
  prompts: Array<{ id: string; version: string; reviewed: boolean }>;
  counters: Record<string, number>;
  tokens_by_deployment: Record<string, { prompt?: number; completion?: number; total?: number } | number>;
  budget: { day: string; used: number; limit: number; left: number };
  cache_hit_rate: number | null;
};

function Pill({ on, label, onText, offText }: { on: boolean; label: string; onText: string; offText: string }) {
  return (
    <span className={`tag ${on ? "ok" : "role"}`}>
      {label}: {on ? onText : offText}
    </span>
  );
}

/** AI gateway usage seen by this API replica: kill switch, safety, router, prompts, tokens, cache. No text. */
export function AiPanel() {
  const L = useLocale({ allowed: STAFF_LOCALES });
  const { s } = L;
  const [m, setM] = useState<Metrics | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    api<Metrics>("/ai/metrics")
      .then(setM)
      .catch(() => setFailed(true));
  }, []);

  if (failed) return <p className="muted">{s("AI metrics unavailable.")}</p>;
  if (!m)
    return (
      <div className="skeleton-list" role="status" aria-label={s("Loading AI metrics…")}>
        <span />
        <span />
      </div>
    );
  const pct = m.budget.limit ? Math.min(100, Math.round((m.budget.used / m.budget.limit) * 100)) : 0;
  const counters = Object.entries(m.counters).sort((a, b) => b[1] - a[1]);
  const latest = new Map<string, string>();
  m.prompts.filter((p) => p.reviewed).forEach((p) => latest.set(p.id, p.version));
  const on = s("on");
  const off = s("off");

  return (
    <div className="ai-grid">
      <div>
        <div className="chip-row" style={{ marginBottom: "0.6rem" }}>
          <Pill on={m.ai_enabled} label={s("AI (kill switch)")} onText={on} offText={off} />
          <Pill on={m.llm_configured} label={s("Gateway")} onText={on} offText={off} />
          <Pill on={m.content_safety} label={s("Content safety")} onText={on} offText={off} />
          <span className="tag role">
            {s("Router mode")}: {s(m.router.mode || "python")}
          </span>
        </div>
        <p className="small" style={{ margin: "0 0 0.25rem" }}>
          {s("Daily token budget:")} <strong>{L.num(m.budget.used)}</strong> / {L.num(m.budget.limit)}
        </p>
        <div className="meter" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} aria-label={s("Token budget used")}>
          <span style={{ width: `${pct}%` }} />
        </div>
        <p className="small muted" style={{ margin: "0.5rem 0 0" }}>
          {s("Cache hit rate:")}{" "}
          {m.cache_hit_rate == null ? s("no cacheable calls yet") : L.num(m.cache_hit_rate, { style: "percent" })}
        </p>
        {counters.length ? (
          <ul className="small counters">
            {counters.slice(0, 8).map(([k, v]) => (
              <li key={k}>
                <span>{s(k.replace(/_/g, " "))}</span>
                <strong>{L.num(v)}</strong>
              </li>
            ))}
          </ul>
        ) : (
          <p className="small muted">{s("No AI events yet.")}</p>
        )}
      </div>
      <div className="table-scroll">
        <table className="data-table">
          <caption className="sr-only">{s("Router policy")}</caption>
          <thead>
            <tr>
              <th scope="col">{s("Task")}</th>
              <th scope="col">{s("Model")}</th>
              <th scope="col">{s("Max tokens")}</th>
              <th scope="col">{s("Prompt")}</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(m.router.tasks).map(([task, r]) => (
              <tr key={task}>
                <td>{s(task.replace(/_/g, " "))}</td>
                <td>
                  {s(r.tier)}
                  {r.cacheable ? ` · ${s("cached")}` : ""}
                  <div className="muted small" dir="ltr" data-src="record">
                    {(m.router.mode === "azure" ? m.router.azure_model_router : r.tier === "small" ? m.router.small : m.router.strong) ||
                      s("not configured")}
                  </div>
                </td>
                <td>{L.num(r.max_tokens)}</td>
                <td dir="ltr">{latest.has(task) ? `v${latest.get(task)}` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
