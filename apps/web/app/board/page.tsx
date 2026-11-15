"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

type Case = {
  case_id: string;
  state: string;
  urgency?: string;
  patient_id: string;
  result_display?: string;
  owner_name?: string;
  timeline: Array<{ kind: string; label: string; detail: string; actor: string }>;
};

type QueueItem = {
  id: string;
  case_id: string;
  kind: string;
  urgency?: string;
  title: string;
  detail?: string;
};

export default function BoardPage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [selected, setSelected] = useState<Case | null>(null);
  const [err, setErr] = useState("");

  const refresh = async () => {
    const [cs, q] = await Promise.all([api<Case[]>("/cases"), api<QueueItem[]>("/queue")]);
    setCases(cs);
    setQueue(q);
  };

  useEffect(() => {
    refresh().catch((e) => setErr(String(e)));
  }, []);

  const openCase = async (id: string) => {
    const c = await api<Case>(`/cases/${id}`);
    setSelected(c);
  };

  const accept = async (id: string) => {
    await api(`/cases/${id}/accept?actor=human:gp-aisha`, { method: "POST" });
    await refresh();
    await openCase(id);
  };

  const handleEscalation = async (id: string) => {
    await api(`/cases/${id}/escalation/handle?actor=human:coordinator`, { method: "POST" });
    await refresh();
    await openCase(id);
  };

  const attend = async (id: string) => {
    await api(`/cases/${id}/attend`, { method: "POST" });
    await refresh();
    await openCase(id);
  };

  const tryClose = async (id: string) => {
    await api(`/cases/${id}/close`, { method: "POST", body: JSON.stringify({}) });
    await refresh();
    await openCase(id);
  };

  return (
    <main className="shell">
      <div className="topbar rise">
        <div className="brand-mark">
          <div className="mark">ر</div>
          <div>
            <div style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>Rabt board</div>
            <div className="muted" style={{ fontSize: "0.82rem" }}>
              HITL queue · ownership · closure gate
            </div>
          </div>
        </div>
        <div className="actions" style={{ marginTop: 0 }}>
          <Link className="btn ghost" href="/learn">
            Learn
          </Link>
          <Link className="btn secondary" href="/">
            Demo home
          </Link>
        </div>
      </div>

      <div className="banner rise d2">
        Synthetic data only. Coral items on the left are human-in-the-loop queues.
      </div>
      {err ? <div className="banner">{err}</div> : null}

      <div className="board-layout rise d3">
        <section className="panel soft">
          <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>
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
              </div>
              <h2 style={{ fontFamily: "var(--font-display)", letterSpacing: "-0.02em" }}>
                {selected.result_display}
              </h2>
              <p className="muted">
                {selected.case_id} · owner {selected.owner_name || "—"}
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
                    Mark attended + close
                  </button>
                ) : null}
                <button className="btn danger" type="button" onClick={() => tryClose(selected.case_id)}>
                  Try close (evidence gate)
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
