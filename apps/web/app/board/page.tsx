"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, setApiPersona } from "@/lib/api";
import { LiveTranslate } from "@/components/LiveTranslate";

type Evidence = {
  attended_encounter?: boolean;
  outcome_document?: boolean;
  outcome_ref?: string;
  outcome_note?: string;
  attendance_note?: string;
  pending_approval_token?: string;
  approvers?: string[];
  call_outcome?: string;
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
  return c.state;
}

export default function BoardPage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [selected, setSelected] = useState<Case | null>(null);
  const [persona, setPersona] = useState<string>(PERSONAS[0].id);
  const [err, setErr] = useState("");
  const [flash, setFlash] = useState("");

  const refresh = useCallback(async () => {
    const [cs, q, ap] = await Promise.all([
      api<Case[]>("/cases"),
      api<QueueItem[]>("/queue"),
      api<Approval[]>("/approvals?action=exceptional_closure"),
    ]);
    setCases(cs);
    setQueue(q);
    // 4-eyes panel is closure-only; critical ladder items stay in the escalation queue
    setApprovals(ap.filter((a) => a.action === "exceptional_closure"));
    return cs;
  }, []);

  useEffect(() => {
    setApiPersona(persona);
    refresh().catch((e) => setErr(String(e)));
  }, [refresh, persona]);

  const openCase = async (id: string) => {
    const c = await api<Case>(`/cases/${id}`);
    setSelected(c);
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
    await afterAction(id, "Patient notified");
  };

  const markUnreachable = async (id: string) => {
    await api(`/cases/${id}/unreachable`, { method: "POST" });
    await afterAction(id, "Marked unreachable");
  };

  const resumeConsent = async (id: string) => {
    await api(`/cases/${id}/consent/resume`, { method: "POST" });
    await afterAction(id, "Consent resumed");
  };

  const resolveDataQuery = async (id: string) => {
    await api(`/cases/${id}/data-query/resolve`, { method: "POST" });
    await afterAction(id, "Data query resolved");
  };

  const callbackDone = async (id: string) => {
    await api(`/cases/${id}/callback/done`, { method: "POST" });
    await afterAction(id, "Callback completed");
  };

  const resolveQueue = async (qid: string, caseId: string) => {
    await api(`/queue/${qid}/resolve`, { method: "POST" });
    await afterAction(caseId, "Queue item resolved");
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
    await afterAction(id, `Call outcome: ${outcome}`);
  };

  const updateClaim = async (id: string, status: string) => {
    await api(`/cases/${id}/claim`, { method: "POST", body: JSON.stringify({ status }) });
    await afterAction(id, `Claim: ${status}`);
  };

  const attend = async (id: string) => {
    await api(`/cases/${id}/attend`, { method: "POST" });
    await afterAction(id, "Attendance recorded — outcome still required to close.");
  };

  const recordOutcome = async (id: string) => {
    await api(`/cases/${id}/outcome`, {
      method: "POST",
      body: JSON.stringify({
        outcome_ref: `Encounter/demo-${id.slice(-6)}`,
        outcome_note: "Follow-up plan documented",
      }),
    });
    await afterAction(id, "Outcome linked — evidence gate re-checked.");
  };

  const tryClose = async (id: string) => {
    await api(`/cases/${id}/close`, {
      method: "POST",
      body: JSON.stringify({
        human_reason_code: "exceptional_closure",
        human_signer: persona,
      }),
    });
    await afterAction(id, "Close requested — check pending approvals if evidence is incomplete.");
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
          ? `Approved — case is now ${result.case?.state || "updated"}.`
          : `Vote recorded (${result.status}).`
      );
    } catch (e) {
      setErr(String(e));
    }
  };

  const evidenceBits = (ev?: Evidence) => {
    const attended = ev?.attended_encounter ? "Attendance ✓" : "Attendance missing";
    const outcome = ev?.outcome_document
      ? `Outcome ✓${ev.outcome_ref ? ` (${ev.outcome_ref})` : ""}`
      : "Outcome missing";
    return `${attended} · ${outcome}`;
  };

  return (
    <main className="shell">
      <div className="topbar rise">
        <div className="brand-mark">
          <div className="mark">ر</div>
          <div>
            <h1 style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "1.05rem", margin: 0 }}>
              Rabt board
            </h1>
            <div className="muted" style={{ fontSize: "0.82rem" }}>
              HITL queue · ownership · two-person closure
            </div>
          </div>
        </div>
        <div className="actions" style={{ marginTop: 0, alignItems: "center" }}>
          <label className="muted" style={{ fontSize: "0.82rem" }}>
            Acting as{" "}
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
                  {p.label}
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
              setFlash("Demo clock +15 minutes — ladder tick ran.");
            }}
          >
            Advance +15m
          </button>
          <button
            className="btn ghost"
            type="button"
            onClick={async () => {
              setSelected(null);
              await api("/demo/reset", { method: "POST" });
              await refresh();
              setFlash("Demo reset — 7 seeded cases restored.");
            }}
          >
            Reset demo
          </button>
          <Link className="btn secondary" href="/">
            Demo home
          </Link>
        </div>
      </div>

      <div className="banner rise d2">
        Shared demo — data resets on restart or Reset demo. Switch persona to cast the second approval vote.
      </div>
      {err ? <div className="banner">{err}</div> : null}
      {flash ? (
        <div className="banner" style={{ background: "#eef7f1", borderColor: "#b7d8c3" }}>
          {flash}
        </div>
      ) : null}

      <div className="board-layout rise d3">
        <section className="panel soft">
          <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>
            Pending approvals{" "}
            <span className="tag human" style={{ marginInlineStart: "0.4rem" }}>
              4-eyes
            </span>
          </h2>
          {approvals.length === 0 ? <p className="muted">No open approval requests</p> : null}
          {approvals.map((a) => {
            const isRequester = a.requested_by === persona;
            return (
              <div
                key={a.token}
                className="choice"
                style={{ width: "100%", marginBottom: "0.5rem", background: "#fff7f4", borderColor: "#f2d2c8" }}
              >
                <button type="button" style={{ all: "unset", cursor: "pointer", display: "block", width: "100%" }} onClick={() => openCase(a.case_id)}>
                  <strong>{a.action.replace(/_/g, " ")}</strong>
                  <div className="muted">
                    Case {a.case_id} · {a.approve_count}/{a.required} votes · requested by {a.requested_by || "—"}
                  </div>
                  <div className="muted" style={{ fontSize: "0.78rem" }}>
                    {a.votes.map((v) => `${v.user_id}: ${v.decision}`).join(" · ") || "No votes yet"}
                  </div>
                </button>
                <div className="actions" style={{ marginTop: "0.55rem" }}>
                  <button
                    className="btn"
                    type="button"
                    disabled={isRequester}
                    title={isRequester ? "Requester cannot approve their own request" : "Approve"}
                    onClick={() => vote(a.token, "approved", a.case_id)}
                  >
                    Approve
                  </button>
                  <button
                    className="btn danger"
                    type="button"
                    disabled={isRequester}
                    onClick={() => vote(a.token, "rejected", a.case_id)}
                  >
                    Reject
                  </button>
                </div>
                {isRequester ? (
                  <p className="muted" style={{ fontSize: "0.78rem", marginBottom: 0 }}>
                    Switch persona — you requested this closure.
                  </p>
                ) : null}
              </div>
            );
          })}

          <h2 style={{ fontFamily: "var(--font-display)" }}>
            Escalation queue <span className="tag human" style={{ marginInlineStart: "0.4rem" }}>HITL</span>
          </h2>
          {queue.length === 0 ? <p className="muted">No open queue items</p> : null}
          {queue.map((q) => (
            <div
              key={q.id}
              className="choice"
              style={{ width: "100%", marginBottom: "0.5rem", background: "#fff7f4", borderColor: "#f2d2c8" }}
            >
              <button type="button" style={{ all: "unset", cursor: "pointer", display: "block", width: "100%" }} onClick={() => openCase(q.case_id)}>
                <strong>{q.title}</strong>
                <div className="muted">
                  {q.urgency} · {q.kind}
                  {q.ladder_step ? ` · ladder ${q.ladder_step}` : ""}
                </div>
              </button>
              <button
                className="btn secondary"
                type="button"
                style={{ marginTop: "0.4rem" }}
                onClick={() => resolveQueue(q.id, q.case_id).catch((e) => setErr(String(e)))}
              >
                Resolve queue item
              </button>
            </div>
          ))}

          <h2 style={{ fontFamily: "var(--font-display)" }}>All cases</h2>
          {cases.map((c) => (
            <button
              key={c.case_id}
              type="button"
              className="choice"
              style={{ width: "100%", marginBottom: "0.5rem" }}
              onClick={() => openCase(c.case_id)}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem" }}>
                <strong>{c.result_display || c.case_id}</strong>
                <span className={`tag ${c.urgency === "CRITICAL" ? "urgent" : "calculated"}`}>
                  {c.urgency || "—"}
                </span>
              </div>
              <div className="muted">
                {boardStateLabel(c)} ·{" "}
                {(c.evidence as { patient_display_name?: string } | undefined)?.patient_display_name ||
                  c.patient_id}
                {c.ladder_step ? ` · L${c.ladder_step}` : ""}
              </div>
            </button>
          ))}
        </section>

        <section className="panel">
          {!selected ? (
            <p className="muted">Select a case to see the fact / calculated / AI timeline and human actions.</p>
          ) : null}
          {selected ? (
            <>
              <div className="chip-row">
                <span className="tag role">{boardStateLabel(selected)}</span>
                <span className={`tag ${selected.urgency === "CRITICAL" ? "urgent" : "calculated"}`}>
                  {selected.urgency}
                </span>
                {selected.ladder_step ? <span className="tag calculated">Ladder {selected.ladder_step}</span> : null}
              </div>
              <h2 style={{ fontFamily: "var(--font-display)", letterSpacing: "-0.02em" }}>
                {selected.result_display}
              </h2>
              <p className="muted">
                {selected.case_id} · owner {selected.owner_name || "—"}
              </p>
              <p style={{ marginTop: 0 }}>
                <strong>Evidence:</strong>{" "}
                <span className="muted">{evidenceBits(selected.evidence)}</span>
              </p>
              {(selected.coverage || selected.evidence?.coverage) && (
                <div className="panel soft" style={{ marginBottom: "0.75rem", boxShadow: "none" }}>
                  <strong>Coverage (Demo Health Insurance)</strong>
                  <p className="muted" style={{ margin: "0.25rem 0 0" }}>
                    {JSON.stringify(selected.coverage || selected.evidence?.coverage)}
                  </p>
                  {(selected.coverage || selected.evidence?.coverage)?.preauth_status === "pending" ? (
                    <p className="muted">Booking blocked until pre-auth clears.</p>
                  ) : null}
                </div>
              )}
              {selected.evidence?.claim ? (
                <div className="panel soft" style={{ marginBottom: "0.75rem", boxShadow: "none" }}>
                  <strong>Reimbursement claim</strong>
                  <p className="muted" style={{ margin: "0.25rem 0" }}>
                    {selected.evidence.claim.provider_name} · status {selected.evidence.claim.status.replace(/_/g, " ")} · claimed AED{" "}
                    {selected.evidence.claim.amount_claimed_aed ?? "?"} · expected back AED{" "}
                    {selected.evidence.claim.expected_reimbursement_aed ?? "?"}
                    {selected.evidence.claim.insurer_ack?.claim_reference
                      ? ` · ref ${selected.evidence.claim.insurer_ack.claim_reference}`
                      : ""}
                  </p>
                  {selected.evidence.claim.status === "submitted" ? (
                    <div className="actions">
                      <button className="btn" type="button" onClick={() => updateClaim(selected.case_id, "approved")}>
                        Insurer approved
                      </button>
                      <button className="btn secondary" type="button" onClick={() => updateClaim(selected.case_id, "rejected")}>
                        Insurer rejected
                      </button>
                    </div>
                  ) : null}
                  {selected.evidence.claim.status === "approved" ? (
                    <button className="btn" type="button" onClick={() => updateClaim(selected.case_id, "paid")}>
                      Mark paid back
                    </button>
                  ) : null}
                </div>
              ) : null}
              <div className="actions">
                {selected.state === "AwaitingOwner" ? (
                  <button className="btn" type="button" onClick={() => accept(selected.case_id)}>
                    Accept ownership
                  </button>
                ) : null}
                {selected.state === "Owned" ? (
                  <button className="btn" type="button" onClick={() => notify(selected.case_id)}>
                    Notify patient
                  </button>
                ) : null}
                {selected.state === "PatientNotified" ? (
                  <button className="btn secondary" type="button" onClick={() => markUnreachable(selected.case_id)}>
                    Mark unreachable
                  </button>
                ) : null}
                {selected.state === "OnHoldConsent" ? (
                  <button className="btn" type="button" onClick={() => resumeConsent(selected.case_id)}>
                    Resume consent
                  </button>
                ) : null}
                {selected.state === "DataQuery" ? (
                  <button className="btn" type="button" onClick={() => resolveDataQuery(selected.case_id)}>
                    Resolve data query
                  </button>
                ) : null}
                {selected.state === "HumanCallback" ? (
                  <button className="btn" type="button" onClick={() => callbackDone(selected.case_id)}>
                    Callback done
                  </button>
                ) : null}
                {selected.state === "Escalated" && selected.urgency === "CRITICAL" ? (
                  <>
                    {selected.evidence?.expert_call_script ? (
                      <details style={{ width: "100%", marginBottom: "0.5rem" }}>
                        <summary>Approved call script</summary>
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
                      Call: going now
                    </button>
                    <button
                      className="btn secondary"
                      type="button"
                      onClick={() => logCallOutcome(selected.case_id, "reached_refusing")}
                    >
                      Call: refusing
                    </button>
                    <button
                      className="btn secondary"
                      type="button"
                      onClick={() => logCallOutcome(selected.case_id, "not_reached")}
                    >
                      Call: not reached
                    </button>
                  </>
                ) : null}
                {selected.state === "Escalated" ? (
                  <button className="btn" type="button" onClick={() => handleEscalation(selected.case_id)}>
                    Handle escalation (HITL)
                  </button>
                ) : null}
                {selected.state === "Booked" ? (
                  <button className="btn" type="button" onClick={() => attend(selected.case_id)}>
                    Mark attended
                  </button>
                ) : null}
                {(selected.state === "Owned" || selected.state === "ClosurePending" || selected.state === "Attended") &&
                selected.evidence?.attended_encounter &&
                !selected.evidence?.outcome_document ? (
                  <button className="btn" type="button" onClick={() => recordOutcome(selected.case_id)}>
                    Record outcome
                  </button>
                ) : null}
                {selected.state !== "Closed" && selected.state !== "ClosedByHuman" ? (
                  selected.urgency === "CRITICAL" && selected.state === "Escalated" ? (
                    <button
                      className="btn danger"
                      type="button"
                      disabled
                      title="Handle escalation first"
                    >
                      Request close (handle escalation first)
                    </button>
                  ) : (
                    <button className="btn danger" type="button" onClick={() => tryClose(selected.case_id)}>
                      Request close (2-person if no evidence)
                    </button>
                  )
                ) : null}
                <Link className="btn secondary" href={`/patient/${selected.case_id}?lang=en`}>
                  Patient view
                </Link>
                <a
                  className="btn secondary"
                  href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/cases/${selected.case_id}/evidence-pack`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Download evidence pack
                </a>
              </div>
              <details style={{ marginTop: "1rem" }}>
                <summary style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}>Why?</summary>
                <p className="muted">
                  Illustrative thresholds pending clinician / DoH sign-off. Values are fact / calculated / AI-generated from
                  timeline kinds — no LLM text for deterministic steps.
                </p>
                <ul>
                  {(selected.provenance || []).map((p, i) => (
                    <li key={`${p.to}-${i}`}>
                      <strong>
                        {p.from} → {p.to}
                      </strong>{" "}
                      · {p.reason}
                      {p.evidence?.rule_id ? (
                        <div className="muted">
                          rule {String(p.evidence.rule_id)} v{String(p.evidence.rule_version || "—")}
                          {selected.result_value != null ? ` · input ${selected.result_value}` : ""}
                        </div>
                      ) : null}
                    </li>
                  ))}
                </ul>
                {selected.options?.length ? (
                  <div>
                    <strong>Navigator score breakdown</strong>
                    <ul>
                      {selected.options.map((o) => (
                        <li key={o.id}>
                          {o.name}: score {o.score}
                          {o.in_network ? " · in-network" : ""}
                          {o.payment ? ` · ${o.payment.mode.replace("_", "-")} (pay AED ${o.payment.patient_upfront_aed ?? "?"})` : ""}
                          {o.distance_km != null ? ` · ${o.distance_km} km` : ""}
                          {o.earliest_slot_hours != null ? ` · ${o.earliest_slot_hours}h` : ""}
                          {o.language_match ? " · language match" : ""}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </details>
              <details style={{ marginTop: "0.75rem" }}>
                <summary style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}>
                  Channel preview (simulated)
                </summary>
                <p className="muted">Simulated SMS / WhatsApp — nothing is sent. No result values over SMS.</p>
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
                        {m.channel || "message"} · simulated
                      </div>
                      <p style={{ whiteSpace: "pre-wrap", margin: "0.35rem 0" }}>{m.text}</p>
                      {m.text_ar ? (
                        <p style={{ whiteSpace: "pre-wrap", margin: 0 }} dir="rtl">
                          {m.text_ar}
                        </p>
                      ) : null}
                    </div>
                  ))}
              </details>
              <h3 style={{ fontFamily: "var(--font-display)", marginTop: "1.4rem" }}>Timeline</h3>
              <p className="muted" style={{ marginTop: 0 }}>
                Blue = recorded fact · Gold = calculated (templates/rules) · Violet = AI-generated (LLM ran)
              </p>
              <ul className="timeline">
                {selected.timeline.map((t, i) => (
                  <li key={`${t.label}-${i}`}>
                    <span className={`tag ${t.kind}`}>{t.kind}</span> <strong>{t.label}</strong>
                    <div className="muted">
                      {t.at
                        ? `${new Date(t.at * 1000).toLocaleString(undefined, {
                            day: "2-digit",
                            month: "short",
                            hour: "2-digit",
                            minute: "2-digit",
                          })} · `
                        : ""}
                      {t.detail} · {t.actor}
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
