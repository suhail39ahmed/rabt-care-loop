"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

type Pending = { id: string; title: string; language: string; reason?: string; suggested_by?: string; content: string };
type Kb = { index_version: string; docs: Array<{ id: string; title: string; language: string; approved_by?: string }> };

const REVIEWERS = [
  { id: "human:gp-aisha", label: "Dr Aisha (physician)" },
  { id: "human:supervisor", label: "Supervisor" },
];

/** Clinician-approved learning loop: drafts from coordinators wait here until a physician or supervisor decides. */
export function KbReview() {
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
      setMsg("Draft saved for clinician review. Names, phones and IDs were removed.");
      await load();
    } catch (e) {
      setMsg(`Could not save the draft: ${String(e).replace(/^Error:\s*/, "")}`);
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
      setMsg("Knowledge base unavailable.");
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
      setMsg(action === "approve" ? "Approved and published. Cached answers were cleared." : "Rejected.");
      await load();
    } catch (e) {
      setMsg(`Could not ${action}: ${String(e).replace(/^Error:\s*/, "")}`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <div className="row-actions" style={{ justifyContent: "space-between", alignItems: "center", marginTop: 0 }}>
        <p className="muted small" style={{ margin: 0 }}>
          {kb ? `${kb.docs.length} approved articles · index ${kb.index_version}` : "Loading…"}
        </p>
        <label className="muted small">
          Reviewing as{" "}
          <select className="field" style={{ width: "auto", padding: "0.3rem 0.5rem" }} value={reviewer} onChange={(e) => setReviewer(e.target.value)}>
            {REVIEWERS.map((r) => (
              <option key={r.id} value={r.id}>
                {r.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div aria-live="polite">{msg ? <p className="small">{msg}</p> : null}</div>
      {pending && pending.length === 0 ? (
        <p className="muted">
          No drafts waiting. When a patient asks something the approved knowledge base cannot answer, the coordinator gets a
          &quot;kb gap&quot; item and can draft an article here for a clinician to approve.
        </p>
      ) : null}
      {(pending || []).map((p) => (
        <article key={p.id} className="choice" style={{ width: "100%", marginBottom: "0.5rem" }}>
          <div className="chip-row">
            <span className="tag role">{p.language.toUpperCase()}</span>
            {p.suggested_by ? <span className="tag calculated">by {p.suggested_by.replace(/^human:/, "").replace(/-/g, " ")}</span> : null}
          </div>
          <strong>{p.title}</strong>
          {p.reason ? <p className="muted small" style={{ margin: "0.25rem 0" }}>{p.reason}</p> : null}
          <details>
            <summary className="small">Read draft</summary>
            <p className="small" style={{ whiteSpace: "pre-wrap" }} dir="auto">
              {p.content}
            </p>
          </details>
          <div className="row-actions" style={{ justifyContent: "flex-start" }}>
            <button type="button" className="btn btn-sm" disabled={busy === p.id} onClick={() => decide(p.id, "approve")}>
              Approve and publish
            </button>
            <button type="button" className="btn secondary btn-sm" disabled={busy === p.id} onClick={() => decide(p.id, "reject")}>
              Reject
            </button>
          </div>
        </article>
      ))}
      <details className="draft">
        <summary className="small">Draft an article (coordinator)</summary>
        <div style={{ display: "grid", gap: "0.5rem", marginTop: "0.5rem" }}>
          <label className="small">
            Title
            <input className="field" value={draft.title} maxLength={120} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
          </label>
          <label className="small">
            Language
            <select className="field" value={draft.language} onChange={(e) => setDraft({ ...draft, language: e.target.value })}>
              <option value="en">English</option>
              <option value="ar">Arabic</option>
            </select>
          </label>
          <label className="small">
            Article (plain language, no diagnosis)
            <textarea className="field" rows={4} dir="auto" value={draft.content} maxLength={6000} onChange={(e) => setDraft({ ...draft, content: e.target.value })} />
          </label>
          <label className="small">
            Why is it needed?
            <input className="field" value={draft.reason} maxLength={300} onChange={(e) => setDraft({ ...draft, reason: e.target.value })} />
          </label>
          <div className="row-actions" style={{ justifyContent: "flex-start" }}>
            <button
              type="button"
              className="btn btn-sm"
              disabled={busy === "draft" || draft.title.trim().length < 3 || draft.content.trim().length < 20}
              onClick={() => suggest()}
            >
              Send for review
            </button>
          </div>
        </div>
      </details>
    </div>
  );
}
