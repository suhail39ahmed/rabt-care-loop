"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Metrics = {
  ai_enabled: boolean;
  llm_configured: boolean;
  content_safety: boolean;
  router: { small: string | null; strong: string | null; tasks: Record<string, { tier: string; max_tokens: number; cacheable: boolean }> };
  prompts: Array<{ id: string; version: string; reviewed: boolean }>;
  counters: Record<string, number>;
  tokens_by_deployment: Record<string, { prompt?: number; completion?: number; total?: number } | number>;
  budget: { day: string; used: number; limit: number; left: number };
  cache_hit_rate: number | null;
};

function Pill({ on, label }: { on: boolean; label: string }) {
  return (
    <span className={`tag ${on ? "ok" : "role"}`}>
      {label}: {on ? "on" : "off"}
    </span>
  );
}

/** AI gateway usage seen by this API replica: kill switch, safety, router, prompts, tokens, cache. No text. */
export function AiPanel() {
  const [m, setM] = useState<Metrics | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api<Metrics>("/ai/metrics")
      .then(setM)
      .catch(() => setErr("AI metrics unavailable."));
  }, []);

  if (err) return <p className="muted">{err}</p>;
  if (!m) return <p className="muted">Loading AI metrics…</p>;
  const pct = m.budget.limit ? Math.min(100, Math.round((m.budget.used / m.budget.limit) * 100)) : 0;
  const counters = Object.entries(m.counters).sort((a, b) => b[1] - a[1]);
  const latest = new Map<string, string>();
  m.prompts.filter((p) => p.reviewed).forEach((p) => latest.set(p.id, p.version));

  return (
    <div className="ai-grid">
      <div>
        <div className="chip-row" style={{ marginBottom: "0.6rem" }}>
          <Pill on={m.ai_enabled} label="AI (kill switch)" />
          <Pill on={m.llm_configured} label="Gateway" />
          <Pill on={m.content_safety} label="Content Safety" />
        </div>
        <p className="small" style={{ margin: "0 0 0.25rem" }}>
          Daily token budget: <strong>{m.budget.used.toLocaleString()}</strong> / {m.budget.limit.toLocaleString()}
        </p>
        <div className="meter" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} aria-label="Token budget used">
          <span style={{ width: `${pct}%` }} />
        </div>
        <p className="small muted" style={{ margin: "0.5rem 0 0" }}>
          Cache hit rate: {m.cache_hit_rate == null ? "no cacheable calls yet" : `${Math.round(m.cache_hit_rate * 100)}%`}
        </p>
        {counters.length ? (
          <ul className="small counters">
            {counters.slice(0, 8).map(([k, v]) => (
              <li key={k}>
                <span>{k.replace(/_/g, " ")}</span>
                <strong>{v}</strong>
              </li>
            ))}
          </ul>
        ) : (
          <p className="small muted">No AI events yet.</p>
        )}
      </div>
      <div className="table-scroll">
        <table className="data-table">
          <caption className="sr-only">Router policy</caption>
          <thead>
            <tr>
              <th scope="col">Task</th>
              <th scope="col">Model</th>
              <th scope="col">Max tokens</th>
              <th scope="col">Prompt</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(m.router.tasks).map(([task, r]) => (
              <tr key={task}>
                <td>{task.replace(/_/g, " ")}</td>
                <td>
                  {r.tier}
                  {r.cacheable ? " · cached" : ""}
                  <div className="muted small">{(r.tier === "small" ? m.router.small : m.router.strong) || "not configured"}</div>
                </td>
                <td>{r.max_tokens}</td>
                <td>{latest.has(task) ? `v${latest.get(task)}` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
