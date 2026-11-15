"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, setApiPersona } from "@/lib/api";

type Evidence = {
  attended_encounter?: boolean;
  outcome_document?: boolean;
  outcome_ref?: string;
  outcome_note?: string;
  attendance_note?: string;
  pending_approval_token?: string;
  approvers?: string[];
};

type Case = {
  case_id: string;
  state: string;
  urgency?: string;
  patient_id: string;
  result_display?: string;
  owner_name?: string;
  ladder_step?: number;
  evidence?: Evidence;
  timeline: Array<{ kind: string; label: string; detail: string; actor: string }>;
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
      api<Approval[]>("/approvals"),
    ]);
    setCases(cs);
    setQueue(q);
    setApprovals(ap);
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

  const handleEscalation = async (id: string) => {
    await api(`/cases/${id}/escalation/handle?actor=${encodeURIComponent(persona)}`, { method: "POST" });
    await afterAction(id);
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
            <div style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>Rabt board</div>
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
          <Link className="btn ghost" href="/learn">
            Learn
          </Link>
          <Link className="btn secondary" href="/">
            Demo home
          </Link>
        </div>
      </div>

      <div className="banner rise d2">
        Synthetic data only. Switch persona to cast the second approval vote without reloading.
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
            <button
              key={q.id}
              type="button"
              className="choice"
              style={{ width: "100%", marginBottom: "0.5rem", background: "#fff7f4", borderColor: "#f2d2c8" }}
              onClick={() => openCase(q.case_id)}
            >
              <strong>{q.title}</strong>
              <div className="muted">
                {q.urgency} · {q.kind}
                {q.ladder_step ? ` · ladder ${q.ladder_step}` : ""}
              </div>
            </button>
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
                {c.state} · {c.patient_id}
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
                <span className="tag role">{selected.state}</span>
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
              <div className="actions">
                {selected.state === "AwaitingOwner" ? (
                  <button className="btn" type="button" onClick={() => accept(selected.case_id)}>
                    Accept ownership
                  </button>
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
                <button className="btn danger" type="button" onClick={() => tryClose(selected.case_id)}>
                  Request close (2-person if no evidence)
                </button>
                <Link className="btn secondary" href={`/patient/${selected.case_id}?lang=en`}>
                  Patient view
                </Link>
              </div>
              <h3 style={{ fontFamily: "var(--font-display)", marginTop: "1.4rem" }}>Timeline</h3>
              <p className="muted" style={{ marginTop: 0 }}>
                Blue = recorded fact · Gold = calculated · Violet = AI text
              </p>
              <ul className="timeline">
                {selected.timeline.map((t, i) => (
                  <li key={`${t.label}-${i}`}>
                    <span className={`tag ${t.kind}`}>{t.kind}</span> <strong>{t.label}</strong>
                    <div className="muted">
                      {t.detail} · {t.actor}
                    </div>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </section>
      </div>
    </main>
  );
}
