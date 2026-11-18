"use client";

import { useCallback, useEffect, useState } from "react";
import { api, setApiPersona } from "@/lib/api";
import type { LocaleApi } from "@/lib/i18n";

export type FollowupFlag = {
  flag: "overdue" | "missed_visit" | "result_delayed" | "unowned";
  reason: string;
  since?: number;
};

type Row = {
  case_id: string;
  patient?: string;
  result_display?: string;
  state: string;
  urgency?: string;
  assisted?: boolean;
  owner_id?: string | null;
  owner_name?: string | null;
  time_in_state_s: number;
  sla_s?: number | null;
  flags: FollowupFlag[];
};

type Payload = {
  counts: Record<string, number>;
  cases: Row[];
};

type FlagFilter = "flagged" | "overdue" | "missed_visit" | "result_delayed" | "unowned" | "open";

export const FLAG_LABEL: Record<FollowupFlag["flag"], string> = {
  overdue: "Overdue",
  missed_visit: "Missed visit",
  result_delayed: "Result delayed",
  unowned: "Unowned",
};

export const FLAG_CLASS: Record<FollowupFlag["flag"], string> = {
  overdue: "warn",
  missed_visit: "urgent",
  result_delayed: "calculated",
  unowned: "human",
};

const REASON_TEXT: Record<string, string> = {
  sla: "In this step longer than its target",
  no_show: "Did not attend — rebooking offered",
  past_appointment: "Appointment time passed with no attendance recorded",
  rebook_pending: "Missed visit — rebooking pending",
  no_outcome: "Attended — outcome not received",
  data_query: "Data query on the result still open",
  no_owner: "No accountable owner yet",
};

const OWNERS = [
  { id: "human:coordinator-sara", owner: "Practitioner/coordinator-sara", label: "Coordinator Sara" },
  { id: "human:gp-aisha", owner: "Practitioner/gp-aisha", label: "Dr Aisha" },
  { id: "human:gp-khan", owner: "Practitioner/gp-khan", label: "Dr Khan" },
  { id: "human:supervisor", owner: "Practitioner/supervisor-oncall", label: "Supervisor" },
] as const;

export function duration(L: LocaleApi, seconds: number): string {
  const s = Math.max(0, seconds);
  if (s < 3600) return L.s("{n} min", { n: L.num(Math.max(1, Math.round(s / 60))) });
  if (s < 48 * 3600) return L.s("{n} h", { n: L.num(Math.round(s / 360) / 10) });
  return L.s("{n} d", { n: L.num(Math.round(s / 8640) / 10) });
}

/** Follow-up tracker: every open case with its named owner, time in the current step against its target,
 * and flags for overdue steps, missed visits, delayed results and missing owners. */
export function FollowupTracker({
  L,
  persona,
  live,
  stateLabel,
  onOpen,
  onChanged,
}: {
  L: LocaleApi;
  persona: string;
  live: boolean;
  stateLabel: (state: string) => string;
  onOpen: (caseId: string) => void;
  onChanged: (caseId: string, message: string) => void;
}) {
  const { s } = L;
  const [data, setData] = useState<Payload | null>(null);
  const [filter, setFilter] = useState<FlagFilter>("flagged");
  const [pick, setPick] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    const d = await api<Payload>("/followups");
    setData(d);
    setErr("");
  }, []);

  useEffect(() => {
    load().catch(() => setErr(s("Could not load the follow-up tracker. Retrying…")));
    if (!live) return;
    const t = window.setInterval(() => {
      if (document.visibilityState === "visible") load().catch(() => setErr(s("Could not load the follow-up tracker. Retrying…")));
    }, 3000);
    return () => window.clearInterval(t);
  }, [load, live, s]);

  const assign = async (caseId: string, owner?: string) => {
    setBusy(caseId);
    try {
      setApiPersona(persona);
      await api(`/cases/${caseId}/owner`, { method: "POST", body: JSON.stringify(owner ? { owner } : {}) });
      await load();
      onChanged(caseId, s("Ownership updated"));
    } catch {
      setErr(s("Could not update ownership"));
    } finally {
      setBusy("");
    }
  };

  const rows = (data?.cases || []).filter((r) =>
    filter === "open" ? true : filter === "flagged" ? r.flags.length > 0 : r.flags.some((f) => f.flag === filter)
  );
  const counts = data?.counts || {};
  const chips: Array<[FlagFilter, string]> = [
    ["flagged", s("All flagged")],
    ["overdue", s("Overdue")],
    ["missed_visit", s("Missed visit")],
    ["result_delayed", s("Result delayed")],
    ["unowned", s("Unowned")],
    ["open", s("Open cases")],
  ];

  return (
    <section className="panel soft tracker rise d3" aria-labelledby="tracker-title">
      <div className="tracker-head">
        <h2 id="tracker-title" style={{ fontFamily: "var(--font-display)", margin: 0 }}>
          {s("Follow-up tracker")}
        </h2>
        <p className="muted small" style={{ margin: 0 }}>
          {s("Every open case has a named owner. A new flag adds a coordinator queue item; nothing here closes a case.")}
        </p>
      </div>
      <div className="filter-row" role="group" aria-label={s("Filter")}>
        {chips.map(([id, label]) => (
          <button key={id} type="button" className={`chip ${filter === id ? "active" : ""}`} aria-pressed={filter === id} onClick={() => setFilter(id)}>
            {label} <span className="count">{L.num(counts[id] ?? 0)}</span>
          </button>
        ))}
      </div>
      {err ? (
        <div className="banner error" role="alert">
          {err}
        </div>
      ) : null}
      {!data ? (
        <div className="skeleton-list" role="status" aria-label={s("Loading cases…")}>
          <span />
          <span />
        </div>
      ) : null}
      {data && rows.length === 0 ? <p className="muted">{s("No cases match this filter")}</p> : null}
      {rows.length ? (
        <table className="fu-table">
          <caption className="sr-only">{s("Follow-up tracker")}</caption>
          <thead>
            <tr>
              <th scope="col">{s("Patient · result")}</th>
              <th scope="col">{s("Step")}</th>
              <th scope="col">{s("Owner")}</th>
              <th scope="col">{s("Time in step")}</th>
              <th scope="col">{s("Flags")}</th>
              <th scope="col">{s("Action")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const mine = OWNERS.find((o) => o.id === persona)?.owner === r.owner_id;
              const selected = pick[r.case_id] || OWNERS.find((o) => o.owner === r.owner_id)?.id || OWNERS[0].id;
              const over = r.sla_s != null && r.time_in_state_s > r.sla_s;
              return (
                <tr key={r.case_id} className={r.flags.length ? "flagged" : ""} data-case={r.case_id}>
                  <td data-label={s("Patient · result")}>
                    <button type="button" className="linkish" onClick={() => onOpen(r.case_id)}>
                      <strong data-src="record">{r.patient || r.case_id}</strong>
                    </button>
                    <div className="muted small" data-src="record">
                      {r.result_display} · {r.case_id}
                    </div>
                  </td>
                  <td data-label={s("Step")}>{s(stateLabel(r.state))}</td>
                  <td data-label={s("Owner")}>
                    {r.owner_name ? <span data-src="record">{r.owner_name}</span> : <span className="tag human">{s("Unowned")}</span>}
                  </td>
                  <td data-label={s("Time in step")}>
                    <span className={over ? "fu-over" : ""}>{duration(L, r.time_in_state_s)}</span>
                    <div className="muted small">{r.sla_s != null ? s("target {t}", { t: duration(L, r.sla_s) }) : s("no target")}</div>
                  </td>
                  <td data-label={s("Flags")}>
                    {r.flags.length ? (
                      <ul className="plain fu-flags">
                        {r.flags.map((f) => (
                          <li key={f.flag}>
                            <span className={`tag ${FLAG_CLASS[f.flag]}`}>{s(FLAG_LABEL[f.flag])}</span>{" "}
                            <span className="muted small">{s(REASON_TEXT[f.reason] || f.reason)}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <span className="tag ok">{s("On track")}</span>
                    )}
                  </td>
                  <td data-label={s("Action")}>
                    <div className="fu-actions">
                      {!mine ? (
                        <button type="button" className="btn small-btn" disabled={busy === r.case_id} onClick={() => assign(r.case_id)}>
                          {s("Take ownership")}
                        </button>
                      ) : (
                        <span className="tag ok">{s("You own this")}</span>
                      )}
                      <span className="fu-reassign">
                        <select
                          aria-label={s("Reassign {case} to", { case: r.patient || r.case_id })}
                          value={selected}
                          onChange={(e) => setPick((p) => ({ ...p, [r.case_id]: e.target.value }))}
                        >
                          {OWNERS.map((o) => (
                            <option key={o.id} value={o.id}>
                              {s(o.label)}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          className="btn ghost small-btn"
                          disabled={busy === r.case_id}
                          onClick={() => assign(r.case_id, selected)}
                        >
                          {s("Reassign")}
                        </button>
                      </span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
