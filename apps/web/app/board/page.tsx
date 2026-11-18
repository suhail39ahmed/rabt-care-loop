"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { api, setApiPersona } from "@/lib/api";
import { LiveTranslate } from "@/components/LiveTranslate";
import { LangSwitcher } from "@/components/LangSwitcher";
import { FLAG_CLASS, FLAG_LABEL, FollowupTracker, type FollowupFlag } from "@/components/FollowupTracker";
import { STAFF_LOCALES, useLocale } from "@/lib/i18n";

/** Board refresh interval while live updates are on (ms). */
const POLL_MS = 3000;

type Evidence = {
  attended_encounter?: boolean;
  outcome_document?: boolean;
  outcome_ref?: string;
  outcome_note?: string;
  attendance_note?: string;
  pending_approval_token?: string;
  approvers?: string[];
  call_outcome?: string;
  age?: number;
  assisted?: boolean;
  callback_requested?: boolean;
  reminder_channels?: string[];
  caregiver?: { name: string; relation: string; phone_last4?: string };
  documents?: Array<{ doc_id?: string | null; name?: string; status: string; flags?: string[]; stripped?: string[]; scanner?: string }>;
  expert_call_script?: string;
  coverage?: Record<string, unknown>;
  payment_mode?: string;
  claim?: {
    status: string;
    provider_name?: string;
    amount_claimed_aed?: number;
    expected_reimbursement_aed?: number;
    insurer_ack?: { claim_reference?: string };
  };
};

type Case = {
  case_id: string;
  state: string;
  urgency?: string;
  patient_id: string;
  result_display?: string;
  owner_name?: string;
  owner_id?: string | null;
  followup?: { flags: FollowupFlag[]; time_in_state_s?: number; sla_s?: number | null };
  ladder_step?: number;
  evidence?: Evidence & { patient_display_name?: string };
  timeline: Array<{ kind: string; label: string; detail: string; actor: string; at?: number }>;
  provenance?: Array<{
    from?: string;
    to?: string;
    actor?: string;
    reason?: string;
    evidence?: Record<string, unknown>;
  }>;
  messages?: Array<{
    channel?: string;
    text?: string;
    text_ar?: string;
    includes_values?: boolean;
    ai_generated?: boolean;
  }>;
  options?: Array<{
    id: string;
    name: string;
    score: number;
    in_network?: boolean;
    payment?: { mode: string; patient_upfront_aed?: number; expected_reimbursement_aed?: number };
    distance_km?: number;
    earliest_slot_hours?: number;
    language_match?: boolean;
  }>;
  result_value?: string | number;
  coverage?: {
    covered?: boolean;
    preauth_required?: boolean;
    preauth_status?: string;
    patient_cost_aed?: number | null;
    plan_name?: string;
    reason_code?: string;
    scenario?: string;
  };
};

type QueueItem = {
  id: string;
  case_id: string;
  kind: string;
  urgency?: string;
  title: string;
  detail?: string;
  ladder_step?: number;
};

type Approval = {
  token: string;
  case_id: string;
  action: string;
  required: number;
  requested_by?: string;
  approve_count: number;
  votes: Array<{ user_id: string; decision: string; reason?: string }>;
};

const PERSONAS = [
  { id: "human:coordinator-sara", label: "Coordinator Sara" },
  { id: "human:gp-aisha", label: "Dr Aisha" },
  { id: "human:gp-khan", label: "Dr Khan" },
  { id: "human:supervisor", label: "Supervisor" },
] as const;

function boardStateLabel(c: Case): string {
  const ev = c.evidence as
    | { attended_encounter?: boolean; outcome_document?: boolean }
    | undefined;
  if (
    (c.state === "Attended" || c.state === "Owned") &&
    ev?.attended_encounter &&
    !ev?.outcome_document
  ) {
    return "Attended — outcome needed";
  }
  return humanizeState(c.state);
}

const STATE_TEXT: Record<string, string> = {
  OnHoldConsent: "On hold (consent)",
  DataQuery: "Data query",
  AwaitingOwner: "Awaiting owner",
  PatientNotified: "Patient notified",
  HumanCallback: "Human callback",
  ReferralRejected: "Referral rejected",
  ClosurePending: "Closure pending",
  ClosedByHuman: "Closed by human",
  NoShow: "No-show",
};

function humanizeState(state: string): string {
  return STATE_TEXT[state] || state.replace(/([a-z])([A-Z])/g, "$1 $2");
}

function urgencyTag(u?: string): { cls: string; text: string } {
  if (u === "CRITICAL") return { cls: "urgent", text: "Critical" };
  if (u === "URGENT") return { cls: "calculated", text: "Urgent" };
  if (u === "ROUTINE") return { cls: "role", text: "Routine" };
  return { cls: "role", text: "Not triaged" };
}

type Filter = "all" | "assisted" | "documents";

function isAssisted(c: Case) {
  return !!c.evidence?.assisted;
}

function hasFlaggedDocument(c: Case) {
  return (c.evidence?.documents || []).some((d) => d.status === "quarantined");
}

/** A short fingerprint of what a coordinator sees for a case; a change highlights the row. */
function signature(c: Case) {
  return [
    c.state,
    c.urgency,
    c.ladder_step,
    c.owner_name,
    c.timeline.length,
    c.evidence?.claim?.status,
    (c.followup?.flags || []).map((f) => f.flag).join(","),
  ].join("|");
}

export default function BoardPage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [selected, setSelected] = useState<Case | null>(null);
  const [persona, setPersona] = useState<string>(PERSONAS[0].id);
  const [err, setErr] = useState("");
  const [flash, setFlash] = useState("");
  const L = useLocale({ allowed: STAFF_LOCALES });
  const { s } = L;
  const [live, setLive] = useState(true);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);
  const [changed, setChanged] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState<Filter>("all");
  const [loaded, setLoaded] = useState(false);
  const [view, setView] = useState<"cases" | "tracker">("cases");
  const seen = useRef<Map<string, string>>(new Map());
  const selectedId = useRef<string | null>(null);

  const refresh = useCallback(async () => {
    const [cs, q, ap] = await Promise.all([
      api<Case[]>("/cases"),
      api<QueueItem[]>("/queue"),
      api<Approval[]>("/approvals?action=exceptional_closure"),
    ]);
    const next = new Map(cs.map((c) => [c.case_id, signature(c)]));
    if (seen.current.size) {
      const diff = new Set<string>();
      next.forEach((sig, id) => {
        if (seen.current.get(id) !== sig) diff.add(id);
      });
      if (diff.size) setChanged(diff);
    }
    seen.current = next;
    setCases(cs);
    setQueue(q);
    setUpdatedAt(Date.now());
    setLoaded(true);
    setErr("");
    if (selectedId.current) {
      const fresh = cs.find((c) => c.case_id === selectedId.current);
      if (fresh) setSelected(fresh);
    }
    // 4-eyes panel is closure-only; critical ladder items stay in the escalation queue
    setApprovals(ap.filter((a) => a.action === "exceptional_closure"));
    return cs;
  }, []);

  useEffect(() => {
    setApiPersona(persona);
    refresh().catch((e) => setErr(String(e)));
  }, [refresh, persona]);

  useEffect(() => {
    selectedId.current = selected?.case_id || null;
  }, [selected]);

  // Live board: poll while the tab is visible so patient actions show up without a reload.
  useEffect(() => {
    if (!live) return;
    const tick = () => {
      if (document.visibilityState === "visible") refresh().catch(() => setErr(s("Could not load the board. Retrying…")));
    };
    const t = window.setInterval(tick, POLL_MS);
    document.addEventListener("visibilitychange", tick);
    return () => {
      window.clearInterval(t);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [live, refresh, s]);

  useEffect(() => {
    if (!changed.size) return;
    const t = window.setTimeout(() => setChanged(new Set()), 2600);
    return () => window.clearTimeout(t);
  }, [changed]);

  const shown = useMemo(
    () => cases.filter((c) => (filter === "assisted" ? isAssisted(c) : filter === "documents" ? hasFlaggedDocument(c) : true)),
    [cases, filter]
  );
  const counts = useMemo(
    () => ({ all: cases.length, assisted: cases.filter(isAssisted).length, documents: cases.filter(hasFlaggedDocument).length }),
    [cases]
  );

  // Deep links from the demo tour: /board?focus=<case_id>
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("view") === "tracker") setView("tracker");
    const focus = params.get("focus");
    if (focus) openCase(focus).catch(() => setErr(s("Case {id} not found (the demo may have been reset).", { id: focus })));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openCase = async (id: string) => {
    const c = await api<Case>(`/cases/${id}`);
    setSelected(c);
    if (typeof window !== "undefined" && window.innerWidth < 860) {
      requestAnimationFrame(() => document.getElementById("case-detail")?.scrollIntoView({ behavior: "smooth", block: "start" }));
    }
  };

  const afterAction = async (id: string, message?: string) => {
    const cs = await refresh();
    const fresh = cs.find((c) => c.case_id === id);
    if (fresh) setSelected(fresh);
    else await openCase(id);
    if (message) setFlash(message);
  };

  const accept = async (id: string) => {
    await api(`/cases/${id}/accept?actor=${encodeURIComponent(persona)}`, { method: "POST" });
    await afterAction(id);
  };

  const notify = async (id: string) => {
    await api(`/cases/${id}/notify`, { method: "POST" });
    await afterAction(id, s("Patient notified"));
  };

  const markUnreachable = async (id: string) => {
    await api(`/cases/${id}/unreachable`, { method: "POST" });
    await afterAction(id, s("Marked unreachable"));
  };

  const resumeConsent = async (id: string) => {
    await api(`/cases/${id}/consent/resume`, { method: "POST" });
    await afterAction(id, s("Consent resumed"));
  };

  const resolveDataQuery = async (id: string) => {
    await api(`/cases/${id}/data-query/resolve`, { method: "POST" });
    await afterAction(id, s("Data query resolved"));
  };

  const callbackDone = async (id: string) => {
    await api(`/cases/${id}/callback/done`, { method: "POST" });
    await afterAction(id, s("Callback completed"));
  };

  const resolveQueue = async (qid: string, caseId: string) => {
    await api(`/queue/${qid}/resolve`, { method: "POST" });
    await afterAction(caseId, s("Queue item resolved"));
  };

  const handleEscalation = async (id: string) => {
    await api(`/cases/${id}/escalation/handle?actor=${encodeURIComponent(persona)}`, { method: "POST" });
    await afterAction(id);
  };

  const logCallOutcome = async (id: string, outcome: string) => {
    await api(`/cases/${id}/call/outcome`, {
      method: "POST",
      body: JSON.stringify({ outcome }),
    });
    await afterAction(id, s("Call outcome: {outcome}", { outcome: s(outcome) }));
  };

  const updateClaim = async (id: string, status: string) => {
    await api(`/cases/${id}/claim`, { method: "POST", body: JSON.stringify({ status }) });
    await afterAction(id, s("Claim: {status}", { status: s(status) }));
  };

  const attend = async (id: string) => {
    await api(`/cases/${id}/attend`, { method: "POST" });
    await afterAction(id, s("Attendance recorded — outcome still required to close."));
  };

  const noShow = async (id: string) => {
    await api(`/cases/${id}/no-show`, { method: "POST" });
    await afterAction(id, s("No-show recorded — rebooking offered and a follow-up added to the queue."));
  };

  const recordOutcome = async (id: string) => {
    await api(`/cases/${id}/outcome`, {
      method: "POST",
      body: JSON.stringify({
        outcome_ref: `Encounter/demo-${id.slice(-6)}`,
        outcome_note: "Follow-up plan documented",
      }),
    });
    await afterAction(id, s("Outcome linked — evidence gate re-checked."));
  };

  const tryClose = async (id: string) => {
    await api(`/cases/${id}/close`, {
      method: "POST",
      body: JSON.stringify({
        human_reason_code: "exceptional_closure",
        human_signer: persona,
      }),
    });
    await afterAction(id, s("Close requested — check pending approvals if evidence is incomplete."));
  };

  const vote = async (token: string, decision: "approved" | "rejected", caseId: string) => {
    setErr("");
    try {
      setApiPersona(persona);
      const result = await api<{ status: string; case?: Case }>(`/approvals/${token}/decision`, {
        method: "POST",
        body: JSON.stringify({ decision }),
      });
      await refresh();
      if (result.case) setSelected(result.case);
      else await openCase(caseId);
      setFlash(
        result.status === "approved"
          ? s("Approved — case is now {state}.", { state: s(humanizeState(result.case?.state || "updated")) })
          : s("Vote recorded ({status}).", { status: s(result.status) })
      );
    } catch (e) {
      setErr(String(e));
    }
  };

  const evidenceBits = (ev?: Evidence) => {
    const attended = ev?.attended_encounter ? s("Attendance ✓") : s("Attendance missing");
    const outcome = ev?.outcome_document
      ? `${s("Outcome ✓")}${ev.outcome_ref ? ` (${ev.outcome_ref})` : ""}`
      : s("Outcome missing");
    return `${attended} · ${outcome}`;
  };

  return (
    <main className="shell">
      <div className="topbar rise">
        <div className="brand-mark">
          <div className="mark">ر</div>
          <div>
            <h1 style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "1.05rem", margin: 0 }}>
              {s("Rabt board")}
            </h1>
            <div className="muted" style={{ fontSize: "0.82rem" }}>
              {s("HITL queue · ownership · two-person closure")}
            </div>
          </div>
        </div>
        <div className="actions" style={{ marginTop: 0, alignItems: "center" }}>
          <label className="muted" style={{ fontSize: "0.82rem" }}>
            {s("Acting as")}{" "}
            <select
              value={persona}
              onChange={(e) => {
                setPersona(e.target.value);
                setApiPersona(e.target.value);
              }}
              style={{
                marginInlineStart: "0.35rem",
                padding: "0.35rem 0.55rem",
                borderRadius: "8px",
                border: "1px solid var(--line, #d7cfc6)",
                background: "#fff",
              }}
            >
              {PERSONAS.map((p) => (
                <option key={p.id} value={p.id}>
                  {s(p.label)}
                </option>
              ))}
            </select>
          </label>
          <button
            className="btn ghost"
            type="button"
            onClick={async () => {
              await api("/demo/advance?minutes=15", { method: "POST" });
              await refresh();
              if (selected) await openCase(selected.case_id);
              setFlash(s("Demo clock +15 minutes — ladder tick ran."));
            }}
          >
            {s("Advance +15m")}
          </button>
          <button
            className="btn ghost"
            type="button"
            onClick={async () => {
              setSelected(null);
              await api("/demo/reset", { method: "POST" });
              await refresh();
              setFlash(s("Demo reset — {n} seeded cases restored.", { n: L.num(10) }));
            }}
          >
            {s("Reset demo")}
          </button>
          <Link className="btn secondary" href="/">
            {s("Demo home")}
          </Link>
          <LangSwitcher L={L} compact />
        </div>
      </div>

      <div className="banner rise d2">
        {s("Shared demo — data resets on restart or Reset demo. Switch persona to cast the second approval vote.")}
      </div>
      <div className="live-bar" role="status" aria-live="polite">
        <span className={`live-dot ${live ? "on" : ""}`} aria-hidden="true" />
        <strong>{live ? s("Live") : s("Paused")}</strong>
        {updatedAt ? (
          <span className="muted">{s("Updated {time}", { time: L.date(updatedAt, { hour: "2-digit", minute: "2-digit", second: "2-digit" }) })}</span>
        ) : null}
        <button type="button" className="btn ghost small-btn" onClick={() => setLive((v) => !v)} aria-pressed={!live}>
          {live ? s("Pause live updates") : s("Resume live updates")}
        </button>
      </div>
      {err ? (
        <div className="banner error" role="alert">
          {err}
        </div>
      ) : null}
      {flash ? (
        <div className="banner success" role="status">
          {flash}
        </div>
      ) : null}

      <div className="view-toggle" role="group" aria-label={s("Board view")}>
        <button type="button" aria-pressed={view === "cases"} onClick={() => setView("cases")}>
          {s("Cases and queue")}
        </button>
        <button type="button" aria-pressed={view === "tracker"} onClick={() => setView("tracker")}>
          {s("Follow-up tracker")}
          <span className="count">{L.num(cases.filter((c) => (c.followup?.flags || []).length > 0).length)}</span>
        </button>
      </div>
      {view === "tracker" ? (
        <FollowupTracker
          L={L}
          persona={persona}
          live={live}
          stateLabel={humanizeState}
          onOpen={(id) => {
            openCase(id).catch((e) => setErr(String(e)));
            requestAnimationFrame(() => document.getElementById("case-detail")?.scrollIntoView({ behavior: "smooth", block: "start" }));
          }}
          onChanged={(id, msg) => {
            afterAction(id, msg).catch((e) => setErr(String(e)));
          }}
        />
      ) : null}

      <div className="board-layout rise d3">
        <section className="panel soft">
          <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>
            {s("Pending approvals")}{" "}
            <span className="tag human" style={{ marginInlineStart: "0.4rem" }}>
              {s("4-eyes")}
            </span>
          </h2>
          {approvals.length === 0 ? <p className="muted">{s("No open approval requests")}</p> : null}
          {approvals.map((a) => {
            const isRequester = a.requested_by === persona;
            return (
              <div
                key={a.token}
                className="choice"
                style={{ width: "100%", marginBottom: "0.5rem", background: "#fff7f4", borderColor: "#f2d2c8" }}
              >
                <button type="button" style={{ all: "unset", cursor: "pointer", display: "block", width: "100%" }} onClick={() => openCase(a.case_id)}>
                  <strong>{s(a.action.replace(/_/g, " "))}</strong>
                  <div className="muted">
                    {s("Case {id} · {votes}/{required} votes · requested by {by}", {
                      id: a.case_id,
                      votes: L.num(a.approve_count),
                      required: L.num(a.required),
                      by: a.requested_by || "—",
                    })}
                  </div>
                  <div className="muted" style={{ fontSize: "0.78rem" }}>
                    {a.votes.map((v) => `${v.user_id}: ${v.decision}`).join(" · ") || s("No votes yet")}
                  </div>
                </button>
                <div className="actions" style={{ marginTop: "0.55rem" }}>
                  <button
                    className="btn"
                    type="button"
                    disabled={isRequester}
                    title={isRequester ? s("Requester cannot approve their own request") : s("Approve")}
                    onClick={() => vote(a.token, "approved", a.case_id)}
                  >
                    {s("Approve")}
                  </button>
                  <button
                    className="btn danger"
                    type="button"
                    disabled={isRequester}
                    onClick={() => vote(a.token, "rejected", a.case_id)}
                  >
                    {s("Reject")}
                  </button>
                </div>
                {isRequester ? (
                  <p className="muted" style={{ fontSize: "0.78rem", marginBottom: 0 }}>
                    {s("Switch persona — you requested this closure.")}
                  </p>
                ) : null}
              </div>
            );
          })}

          <h2 style={{ fontFamily: "var(--font-display)" }}>
            {s("Escalation queue")} <span className="tag human" style={{ marginInlineStart: "0.4rem" }}>{s("HITL")}</span>
          </h2>
          {queue.length === 0 ? <p className="muted">{s("No open queue items")}</p> : null}
          {queue.map((q) => (
            <div
              key={q.id}
              className="choice"
              style={{ width: "100%", marginBottom: "0.5rem", background: "#fff7f4", borderColor: "#f2d2c8" }}
            >
              <button type="button" style={{ all: "unset", cursor: "pointer", display: "block", width: "100%" }} onClick={() => openCase(q.case_id)}>
                <strong data-src="record">{q.title}</strong>
                <div className="muted queue-meta">
                  <span data-src="record">
                    {(() => {
                      const qc = cases.find((x) => x.case_id === q.case_id);
                      const who = (qc?.evidence as { patient_display_name?: string } | undefined)?.patient_display_name;
                      return qc ? `${qc.result_display || q.case_id}${who ? ` · ${who}` : ""} · ` : "";
                    })()}
                  </span>
                  {s(urgencyTag(q.urgency).text)} · {q.kind.startsWith("followup_") && q.kind.slice(9) in FLAG_LABEL
                    ? `${s("Follow-up")}: ${s(FLAG_LABEL[q.kind.slice(9) as FollowupFlag["flag"]])}`
                    : s(q.kind.replace(/_/g, " "))}
                  {q.ladder_step ? ` · ${s("ladder step {n}", { n: L.num(q.ladder_step) })}` : ""}
                </div>
              </button>
              <button
                className="btn secondary"
                type="button"
                style={{ marginTop: "0.4rem" }}
                onClick={() => resolveQueue(q.id, q.case_id).catch((e) => setErr(String(e)))}
              >
                {s("Resolve queue item")}
              </button>
            </div>
          ))}

          <h2 style={{ fontFamily: "var(--font-display)" }}>{s("All cases")}</h2>
          <div className="filter-row" role="group" aria-label={s("Filter")}>
            {(
              [
                ["all", s("All")],
                ["assisted", s("Senior / assisted")],
                ["documents", s("Document flagged")],
              ] as Array<[Filter, string]>
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={`chip ${filter === id ? "active" : ""}`}
                aria-pressed={filter === id}
                onClick={() => setFilter(id)}
              >
                {label} <span className="count">{L.num(counts[id])}</span>
              </button>
            ))}
          </div>
          {!loaded ? (
            <div className="skeleton-list" role="status" aria-label={s("Loading cases…")}>
              <span />
              <span />
              <span />
            </div>
          ) : null}
          {loaded && shown.length === 0 ? <p className="muted">{s("No cases match this filter")}</p> : null}
          {shown.map((c) => (
            <button
              key={c.case_id}
              type="button"
              className={`choice case-row ${changed.has(c.case_id) ? "changed" : ""} ${selected?.case_id === c.case_id ? "current" : ""}`}
              style={{ width: "100%", marginBottom: "0.5rem" }}
              onClick={() => openCase(c.case_id)}
              aria-current={selected?.case_id === c.case_id ? "true" : undefined}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem" }}>
                <strong data-src="record">{c.result_display || c.case_id}</strong>
                <span className={`tag ${urgencyTag(c.urgency).cls}`}>{s(urgencyTag(c.urgency).text)}</span>
              </div>
              {isAssisted(c) || hasFlaggedDocument(c) || c.evidence?.callback_requested || changed.has(c.case_id) || (c.followup?.flags || []).length ? (
                <div className="chip-row tight">
                  {(c.followup?.flags || []).map((f) => (
                    <span key={f.flag} className={`tag ${FLAG_CLASS[f.flag]}`}>
                      {s(FLAG_LABEL[f.flag])}
                    </span>
                  ))}
                  {isAssisted(c) ? <span className="tag assisted">{s("Assisted")}</span> : null}
                  {c.evidence?.callback_requested ? <span className="tag human">{s("Call requested")}</span> : null}
                  {hasFlaggedDocument(c) ? <span className="tag urgent">{s("Document quarantined")}</span> : null}
                  {changed.has(c.case_id) ? <span className="tag ok">{s("Changed")}</span> : null}
                </div>
              ) : null}
              <div className="muted">
                {s(boardStateLabel(c))} ·{" "}
                <span data-src="record">
                  {(c.evidence as { patient_display_name?: string } | undefined)?.patient_display_name || c.patient_id}
                </span>
                {c.ladder_step ? ` · L${c.ladder_step}` : ""}
              </div>
              <div className="muted row-owner">
                {s("Owner")}:{" "}
                {c.owner_name ? <span data-src="record">{c.owner_name}</span> : <strong>{s("Unowned")}</strong>}
              </div>
            </button>
          ))}
        </section>

        <section className="panel" id="case-detail" aria-label={s("Case detail")}>
          {!selected ? (
            <div className="empty-state">
              <h2 className="section-title">{s("No case selected")}</h2>
              <p className="muted" style={{ margin: 0 }}>
                {s("Pick a case or a queue item to see its timeline (fact, calculated, AI) and the actions open to the persona you are acting as.")}
              </p>
              {queue[0] ? (
                <button type="button" className="btn" onClick={() => openCase(queue[0].case_id)}>
                  {s("Open the top queue item")}
                </button>
              ) : null}
            </div>
          ) : null}
          {selected ? (
            <>
              <div className="chip-row">
                <span className="tag role">{s(boardStateLabel(selected))}</span>
                <span className={`tag ${urgencyTag(selected.urgency).cls}`}>{s(urgencyTag(selected.urgency).text)}</span>
                {selected.ladder_step ? (
                  <span className="tag calculated">
                    {s("Ladder")} {L.num(selected.ladder_step)}
                  </span>
                ) : null}
                {isAssisted(selected) ? <span className="tag assisted">{s("Senior / assisted")}</span> : null}
              </div>
              <h2 style={{ fontFamily: "var(--font-display)", letterSpacing: "-0.02em" }} data-src="record">
                {selected.result_display}
              </h2>
              <p className="muted">
                <span data-src="record">{selected.case_id}</span> · {s("Owner")}{" "}
                {selected.owner_name ? <span data-src="record">{selected.owner_name}</span> : <strong>{s("Unowned")}</strong>}
              </p>
              {(selected.followup?.flags || []).length || !selected.owner_id ? (
                <div className="chip-row" style={{ alignItems: "center", marginBottom: "0.6rem" }}>
                  {(selected.followup?.flags || []).map((f) => (
                    <span key={f.flag} className={`tag ${FLAG_CLASS[f.flag]}`}>
                      {s(FLAG_LABEL[f.flag])}
                    </span>
                  ))}
                  {!["Closed", "ClosedByHuman"].includes(selected.state) ? (
                    <button
                      type="button"
                      className="btn small-btn"
                      onClick={async () => {
                        try {
                          setApiPersona(persona);
                          await api(`/cases/${selected.case_id}/owner`, { method: "POST", body: "{}" });
                          await afterAction(selected.case_id, s("Ownership updated"));
                        } catch (e) {
                          setErr(String(e));
                        }
                      }}
                    >
                      {s("Take ownership")}
                    </button>
                  ) : null}
                </div>
              ) : null}
              {isAssisted(selected) ? (
                <div className="panel soft assisted-panel">
                  <strong>{s("Senior / assisted")}</strong>
                  <ul className="small plain">
                    {selected.evidence?.age ? <li>{s("Age {n}", { n: L.num(selected.evidence.age) })}</li> : null}
                    <li>{s("Reminders: phone call and SMS, not app-only")}</li>
                    <li>{s("Slower patient-response ladder; a coordinator calls first")}</li>
                    {selected.evidence?.callback_requested ? <li>{s("Patient asked for a phone call")}</li> : null}
                    {selected.evidence?.caregiver ? (
                      <li>
                        {s("Caregiver")}: <span data-src="record">{selected.evidence.caregiver.name}</span> (
                        {s(selected.evidence.caregiver.relation)}) · {s("consent recorded")}
                      </li>
                    ) : null}
                  </ul>
                </div>
              ) : null}
              {selected.evidence?.documents?.length ? (
                <div className="panel soft" style={{ marginBottom: "0.75rem", boxShadow: "none" }}>
                  <strong>{s("Documents")}</strong>
                  <ul className="small plain">
                    {selected.evidence.documents.map((d, i) => (
                      <li key={`${d.doc_id || d.name}-${i}`}>
                        <span className={`tag ${d.status === "quarantined" ? "urgent" : "ok"}`}>
                          {d.status === "quarantined" ? s("Document quarantined") : s("Document checked")}
                        </span>{" "}
                        <span data-src="record">{d.name}</span>
                        {d.flags?.length ? <span className="muted"> · {d.flags.map((r) => s(r.replace(/_/g, " "))).join(", ")}</span> : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <p style={{ marginTop: 0 }}>
                <strong>{s("Evidence:")}</strong>{" "}
                <span className="muted">{evidenceBits(selected.evidence)}</span>
              </p>
              {(selected.coverage || selected.evidence?.coverage) && (
                <div className="panel soft" style={{ marginBottom: "0.75rem", boxShadow: "none" }}>
                  <strong>{s("Coverage (Demo Health Insurance)")}</strong>
                  <p className="muted small" style={{ margin: "0.25rem 0 0", overflowWrap: "anywhere" }} data-src="record" dir="ltr">
                    {JSON.stringify(selected.coverage || selected.evidence?.coverage)}
                  </p>
                  {(selected.coverage || selected.evidence?.coverage)?.preauth_status === "pending" ? (
                    <p className="muted">{s("Booking blocked until pre-auth clears.")}</p>
                  ) : null}
                </div>
              )}
              {selected.evidence?.claim ? (
                <div className="panel soft" style={{ marginBottom: "0.75rem", boxShadow: "none" }}>
                  <strong>{s("Reimbursement claim")}</strong>
                  <p className="muted" style={{ margin: "0.25rem 0" }}>
                    <span data-src="record">{selected.evidence.claim.provider_name}</span> ·{" "}
                    {s("status {status}", { status: s(selected.evidence.claim.status.replace(/_/g, " ")) })} ·{" "}
                    {s("claimed AED {amount}", { amount: L.num(selected.evidence.claim.amount_claimed_aed ?? 0) })} ·{" "}
                    {s("expected back AED {amount}", { amount: L.num(selected.evidence.claim.expected_reimbursement_aed ?? 0) })}
                    {selected.evidence.claim.insurer_ack?.claim_reference ? (
                      <>
                        {" "}
                        · {s("ref")} <span data-src="record">{selected.evidence.claim.insurer_ack.claim_reference}</span>
                      </>
                    ) : null}
                  </p>
                  {selected.evidence.claim.status === "submitted" ? (
                    <div className="actions">
                      <button className="btn" type="button" onClick={() => updateClaim(selected.case_id, "approved")}>
                        {s("Insurer approved")}
                      </button>
                      <button className="btn secondary" type="button" onClick={() => updateClaim(selected.case_id, "rejected")}>
                        {s("Insurer rejected")}
                      </button>
                    </div>
                  ) : null}
                  {selected.evidence.claim.status === "approved" ? (
                    <button className="btn" type="button" onClick={() => updateClaim(selected.case_id, "paid")}>
                      {s("Mark paid back")}
                    </button>
                  ) : null}
                </div>
              ) : null}
              <div className="actions">
                {selected.state === "AwaitingOwner" ? (
                  <button className="btn" type="button" onClick={() => accept(selected.case_id)}>
                    {s("Accept ownership")}
                  </button>
                ) : null}
                {selected.state === "Owned" ? (
                  <button className="btn" type="button" onClick={() => notify(selected.case_id)}>
                    {s("Notify patient")}
                  </button>
                ) : null}
                {selected.state === "PatientNotified" ? (
                  <button className="btn secondary" type="button" onClick={() => markUnreachable(selected.case_id)}>
                    {s("Mark unreachable")}
                  </button>
                ) : null}
                {selected.state === "OnHoldConsent" ? (
                  <button className="btn" type="button" onClick={() => resumeConsent(selected.case_id)}>
                    {s("Resume consent")}
                  </button>
                ) : null}
                {selected.state === "DataQuery" ? (
                  <button className="btn" type="button" onClick={() => resolveDataQuery(selected.case_id)}>
                    {s("Resolve data query")}
                  </button>
                ) : null}
                {selected.state === "HumanCallback" ? (
                  <button className="btn" type="button" onClick={() => callbackDone(selected.case_id)}>
                    {s("Callback done")}
                  </button>
                ) : null}
                {selected.state === "Escalated" && selected.urgency === "CRITICAL" ? (
                  <>
                    {selected.evidence?.expert_call_script ? (
                      <details style={{ width: "100%", marginBottom: "0.5rem" }}>
                        <summary>{s("Approved call script")}</summary>
                        <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>
                          {selected.evidence.expert_call_script}
                        </pre>
                      </details>
                    ) : null}
                    <button
                      className="btn secondary"
                      type="button"
                      onClick={() => logCallOutcome(selected.case_id, "reached_going_now")}
                    >
                      {s("Call: going now")}
                    </button>
                    <button
                      className="btn secondary"
                      type="button"
                      onClick={() => logCallOutcome(selected.case_id, "reached_refusing")}
                    >
                      {s("Call: refusing")}
                    </button>
                    <button
                      className="btn secondary"
                      type="button"
                      onClick={() => logCallOutcome(selected.case_id, "not_reached")}
                    >
                      {s("Call: not reached")}
                    </button>
                  </>
                ) : null}
                {selected.state === "Escalated" ? (
                  <button className="btn" type="button" onClick={() => handleEscalation(selected.case_id)}>
                    {s("Handle escalation (HITL)")}
                  </button>
                ) : null}
                {selected.state === "Booked" ? (
                  <button className="btn" type="button" onClick={() => attend(selected.case_id)}>
                    {s("Mark attended")}
                  </button>
                ) : null}
                {selected.state === "Booked" ? (
                  <button className="btn ghost" type="button" onClick={() => noShow(selected.case_id)}>
                    {s("Did not attend")}
                  </button>
                ) : null}
                {(selected.state === "Owned" || selected.state === "ClosurePending" || selected.state === "Attended") &&
                selected.evidence?.attended_encounter &&
                !selected.evidence?.outcome_document ? (
                  <button className="btn" type="button" onClick={() => recordOutcome(selected.case_id)}>
                    {s("Record outcome")}
                  </button>
                ) : null}
                {selected.state !== "Closed" && selected.state !== "ClosedByHuman" ? (
                  selected.urgency === "CRITICAL" && selected.state === "Escalated" ? (
                    <button
                      className="btn danger"
                      type="button"
                      disabled
                      title={s("Handle escalation first")}
                    >
                      {s("Request close (handle escalation first)")}
                    </button>
                  ) : (
                    <button className="btn danger" type="button" onClick={() => tryClose(selected.case_id)}>
                      {s("Request close (2-person if no evidence)")}
                    </button>
                  )
                ) : null}
                <Link className="btn secondary" href={`/patient/${selected.case_id}?lang=en`}>
                  {s("Patient view")}
                </Link>
                <a
                  className="btn secondary"
                  href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/cases/${selected.case_id}/evidence-pack`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {s("Download evidence pack")}
                </a>
              </div>
              <details style={{ marginTop: "1rem" }}>
                <summary style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}>{s("Why?")}</summary>
                <p className="muted">
                  {s("Illustrative thresholds pending clinician / DoH sign-off. Values are fact / calculated / AI-generated from timeline kinds — no LLM text for deterministic steps.")}
                </p>
                <ul>
                  {(selected.provenance || []).map((p, i) => (
                    <li key={`${p.to}-${i}`}>
                      <strong>
                        {s(humanizeState(p.from || "—"))} → {s(humanizeState(p.to || "—"))}
                      </strong>{" "}
                      · <span data-src="record">{p.reason}</span>
                      {p.evidence?.rule_id ? (
                        <div className="muted">
                          {s("rule")} <span data-src="record">{String(p.evidence.rule_id)} v{String(p.evidence.rule_version || "—")}</span>
                          {selected.result_value != null ? (
                            <>
                              {" "}
                              · {s("input")} <span data-src="record">{String(selected.result_value)}</span>
                            </>
                          ) : null}
                        </div>
                      ) : null}
                    </li>
                  ))}
                </ul>
                {selected.options?.length ? (
                  <div>
                    <strong>{s("Navigator score breakdown")}</strong>
                    <ul>
                      {selected.options.map((o) => (
                        <li key={o.id}>
                          <span data-src="record">{o.name}</span>: {s("score {n}", { n: L.num(o.score) })}
                          {o.in_network ? ` · ${s("in-network")}` : ""}
                          {o.payment
                            ? ` · ${s(o.payment.mode.replace("_", "-"))} (${s("pay AED {amount}", { amount: L.num(o.payment.patient_upfront_aed ?? 0) })})`
                            : ""}
                          {o.distance_km != null ? ` · ${s("{n} km", { n: L.num(o.distance_km) })}` : ""}
                          {o.earliest_slot_hours != null ? ` · ${s("{n} h", { n: L.num(o.earliest_slot_hours) })}` : ""}
                          {o.language_match ? ` · ${s("language match")}` : ""}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </details>
              <details style={{ marginTop: "0.75rem" }}>
                <summary style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}>
                  {s("Channel preview (simulated)")}
                </summary>
                <p className="muted">{s("Simulated SMS / WhatsApp — nothing is sent. No result values over SMS.")}</p>
                {(selected.messages || [])
                  .filter((m) => m.channel === "sms" || m.text || m.text_ar)
                  .map((m, i) => (
                    <div
                      key={i}
                      style={{
                        maxWidth: 280,
                        margin: "0.5rem 0",
                        padding: "0.75rem",
                        borderRadius: "1rem",
                        border: "1px solid var(--line)",
                        background: "#f7faf8",
                      }}
                    >
                      <div className="muted" style={{ fontSize: "0.75rem" }}>
                        {s(m.channel || "message")} · {s("simulated")}
                      </div>
                      <p style={{ whiteSpace: "pre-wrap", margin: "0.35rem 0" }} data-src="record" dir="ltr" lang="en">
                        {m.text}
                      </p>
                      {m.text_ar ? (
                        <p style={{ whiteSpace: "pre-wrap", margin: 0 }} dir="rtl" lang="ar">
                          {m.text_ar}
                        </p>
                      ) : null}
                    </div>
                  ))}
              </details>
              <h3 style={{ fontFamily: "var(--font-display)", marginTop: "1.4rem" }}>{s("Timeline")}</h3>
              <p className="muted" style={{ marginTop: 0 }}>
                {s("Blue = recorded fact · Gold = calculated (templates/rules) · Violet = AI-generated (LLM ran)")}
              </p>
              <ul className="timeline">
                {selected.timeline.map((t, i) => (
                  <li key={`${t.label}-${i}`}>
                    <span className={`tag ${t.kind}`}>{s(t.kind)}</span> <strong data-src="record">{t.label}</strong>
                    <div className="muted">
                      {t.at ? `${L.date(t.at * 1000)} · ` : ""}
                      <span data-src="record">
                        {t.detail} · {t.actor}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
              <LiveTranslate />
            </>
          ) : null}
        </section>
      </div>
    </main>
  );
}
