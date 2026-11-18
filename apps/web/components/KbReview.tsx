"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { STAFF_LOCALES, useLocale } from "@/lib/i18n";

type Pending = { id: string; title: string; language: string; reason?: string; suggested_by?: string; content: string };
type Kb = { index_version: string; docs: Array<{ id: string; title: string; language: string; topic?: string; clinical_review_status?: string; approved_by?: string | null }> };

const REVIEWERS = [
  { id: "human:gp-aisha", label: "Dr Aisha (physician)" },
  { id: "human:supervisor", label: "Supervisor" },
];

/** Clinician-approved learning loop: drafts from coordinators wait here until a physician or supervisor decides. */
export function KbReview() {
  const L = useLocale({ allowed: STAFF_LOCALES });
  const { s } = L;
  const [pending, setPending] = useState<Pending[] | null>(null);
  const [kb, setKb] = useState<Kb | null>(null);
  const [reviewer, setReviewer] = useState(REVIEWERS[0].id);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [draft, setDraft] = useState({ title: "", content: "", language: "en", reason: "" });

  async function suggest() {
    setBusy("draft");
    setMsg("");
    try {
      await api("/kb/suggestions", {
        method: "POST",
        headers: { "X-Rabt-Persona": "human:coordinator-sara" },
        body: JSON.stringify(draft),
      });
      setDraft({ title: "", content: "", language: "en", reason: "" });
      setMsg(s("Draft saved for clinician review. Names, phones and IDs were removed."));
      await load();
    } catch (e) {
      setMsg(s("Could not save the draft: {reason}", { reason: String(e).replace(/^Error:\s*/, "") }));
    } finally {
      setBusy(null);
    }
  }

  const load = useCallback(async () => {
    try {
      const [p, k] = await Promise.all([api<Pending[]>("/kb/pending"), api<Kb>("/kb")]);
      setPending(p);
      setKb(k);
    } catch {
      setMsg(s("Knowledge base unavailable."));
      setPending([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function decide(id: string, action: "approve" | "reject") {
    setBusy(id);
    setMsg("");
    try {
      await api(`/kb/pending/${encodeURIComponent(id)}/${action}`, {
        method: "POST",
        headers: { "X-Rabt-Persona": reviewer },
        body: action === "reject" ? JSON.stringify({ reason: "Not accurate enough for patients" }) : undefined,
      });
      setMsg(action === "approve" ? s("Approved and published. Cached answers were cleared.") : s("Rejected."));
      await load();
    } catch (e) {
      setMsg(s("Could not {action}: {reason}", { action: s(action), reason: String(e).replace(/^Error:\s*/, "") }));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <div className="row-actions" style={{ justifyContent: "space-between", alignItems: "center", marginTop: 0 }}>
        <p className="muted small" style={{ margin: 0 }}>
          {kb ? (
            <>
              {s("{n} approved articles · index", {
                n: L.num(kb.docs.filter((d) => (d.clinical_review_status ?? "approved") === "approved").length),
              })}{" "}
              <span data-src="record" dir="ltr">
                {kb.index_version}
              </span>
            </>
          ) : (
            s("Loading…")
          )}
        </p>
        <label className="muted small">
          {s("Reviewing as")}{" "}
          <select className="field" style={{ width: "auto", padding: "0.3rem 0.5rem" }} value={reviewer} onChange={(e) => setReviewer(e.target.value)}>
            {REVIEWERS.map((r) => (
              <option key={r.id} value={r.id}>
                {s(r.label)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div aria-live="polite">{msg ? <p className="small">{msg}</p> : null}</div>
      {pending && pending.length === 0 ? (
        <p className="muted">
          {s(
            "No drafts waiting. When a patient asks something the approved knowledge base cannot answer, the coordinator gets a \"kb gap\" item and can draft an article here for a clinician to approve."
          )}
        </p>
      ) : null}
      {(pending || []).map((p) => (
        <article key={p.id} className="choice" style={{ width: "100%", marginBottom: "0.5rem" }}>
          <div className="chip-row">
            <span className="tag role">{p.language.toUpperCase()}</span>
            {p.suggested_by ? <span className="tag calculated">
                {s("by")} {s(p.suggested_by.replace(/^human:/, "").replace(/-/g, " "))}
              </span> : null}
          </div>
          <strong data-src="record" dir="auto">
            {p.title}
          </strong>
          {p.reason ? (
            <p className="muted small" style={{ margin: "0.25rem 0" }} data-src="record" dir="auto">
              {p.reason}
            </p>
          ) : null}
          <details>
            <summary className="small">{s("Read draft")}</summary>
            <p className="small" style={{ whiteSpace: "pre-wrap" }} dir="auto" data-src="record">
              {p.content}
            </p>
          </details>
          <div className="row-actions" style={{ justifyContent: "flex-start" }}>
            <button type="button" className="btn btn-sm" disabled={busy === p.id} onClick={() => decide(p.id, "approve")}>
              {s("Approve and publish")}
            </button>
            <button type="button" className="btn secondary btn-sm" disabled={busy === p.id} onClick={() => decide(p.id, "reject")}>
              {s("Reject")}
            </button>
          </div>
        </article>
      ))}
      <details className="draft">
        <summary className="small">{s("Draft an article (coordinator)")}</summary>
        <div style={{ display: "grid", gap: "0.5rem", marginTop: "0.5rem" }}>
          <label className="small">
            {s("Title")}
            <input className="field" value={draft.title} maxLength={120} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
          </label>
          <label className="small">
            {s("Language")}
            <select className="field" value={draft.language} onChange={(e) => setDraft({ ...draft, language: e.target.value })}>
              <option value="en">{s("English")}</option>
              <option value="ar">{s("Arabic")}</option>
            </select>
          </label>
          <label className="small">
            {s("Article (plain language, no diagnosis)")}
            <textarea className="field" rows={4} dir="auto" value={draft.content} maxLength={6000} onChange={(e) => setDraft({ ...draft, content: e.target.value })} />
          </label>
          <label className="small">
            {s("Why is it needed?")}
            <input className="field" value={draft.reason} maxLength={300} onChange={(e) => setDraft({ ...draft, reason: e.target.value })} />
          </label>
          <div className="row-actions" style={{ justifyContent: "flex-start" }}>
            <button
              type="button"
              className="btn btn-sm"
              disabled={busy === "draft" || draft.title.trim().length < 3 || draft.content.trim().length < 20}
              onClick={() => suggest()}
            >
              {s("Send for review")}
            </button>
          </div>
        </div>
      </details>
    </div>
  );
}
