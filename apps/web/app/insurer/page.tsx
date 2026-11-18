"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { LangSwitcher } from "@/components/LangSwitcher";
import { STAFF_LOCALES, useLocale } from "@/lib/i18n";

type Card = { name: string; description: string; url: string; skills: string[]; authentication: string };
type Exchange = {
  at: number;
  case_id: string | null;
  skill: string;
  transport: string;
  outcome: "accepted" | "rejected" | "unavailable";
  signature_verified: boolean;
  reason_code?: string;
  dropped_fields: string[];
  request_fields: string[];
  ms?: number;
  error?: string;
};
type Exchanges = { transport: string; insurer_url: string | null; signed: boolean; exchanges: Exchange[] };

const OUTCOME: Record<Exchange["outcome"], string> = {
  accepted: "Accepted",
  rejected: "Rejected (failed checks)",
  unavailable: "Insurer unavailable",
};

export default function InsurerPage() {
  const L = useLocale({ allowed: STAFF_LOCALES });
  const { s } = L;
  const [card, setCard] = useState<Card | null>(null);
  const [ex, setEx] = useState<Exchanges | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const [c, e] = await Promise.all([api<Card>("/insurer/agent-card"), api<Exchanges>("/insurer/exchanges")]);
      setCard(c);
      setEx(e);
      setError(null);
    } catch {
      setError("Could not reach the Rabt API. It may be waking up; try again in a few seconds.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <main className="shell">
      <div className="topbar">
        <div className="brand-mark">
          <div className="mark">ر</div>
          <div>
            <h1 style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "1.05rem", margin: 0 }}>
              {s("Insurer agent (A2A)")}
            </h1>
            <div className="muted" style={{ fontSize: "0.82rem" }}>{s("Demo Health Insurance · synthetic payer")}</div>
          </div>
        </div>
        <div className="row-actions" style={{ marginTop: 0 }}>
          <button type="button" className="btn secondary" onClick={() => void load()}>
            {s("Refresh")}
          </button>
          <Link className="btn secondary" href="/board">
            {s("Board")}
          </Link>
          <LangSwitcher L={L} compact />
        </div>
      </div>

      <div className="banner" role="status">
        {loading
          ? s("Loading the insurer agent…")
          : (error && s(error)) ||
            (ex?.signed
              ? s("Rabt talks to the insurer as a separate agent over HTTPS. Every request and reply is signed and checked.")
              : s("Local mode: the insurer runs in-process. Replies still pass the same strict checks."))}
      </div>

      <section className="panel soft" style={{ marginTop: "1rem" }} aria-labelledby="how">
        <h2 id="how" className="section-title">{s("How Rabt treats the insurer's replies")}</h2>
        <ol className="small" style={{ margin: 0, paddingInlineStart: "1.2rem", lineHeight: 1.7 }}>
          <li>{s("Only the navigator (eligibility, payment paths) and claims steps may call the insurer; other agents are refused.")}</li>
          <li>{s("Requests carry Rabt's identity and an HMAC signature; the insurer signs its reply the same way.")}</li>
          <li>{s("Replies are data, never instructions: unknown fields are dropped, values are range-checked, free text is scrubbed and checked for injected instructions.")}</li>
          <li>{s("A reply that fails any check is not used. The case goes to a coordinator to confirm cover by phone.")}</li>
        </ol>
      </section>

      <section className="panel soft" style={{ marginTop: "1rem" }} aria-labelledby="card">
        <h2 id="card" className="section-title">{s("Agent card")}</h2>
        {card ? (
          <dl className="small" style={{ display: "grid", gridTemplateColumns: "max-content 1fr", gap: "0.35rem 1rem", margin: 0 }}>
            <dt className="muted">{s("Name")}</dt>
            <dd style={{ margin: 0 }} data-src="record">
              {card.name}
            </dd>
            <dt className="muted">{s("Endpoint")}</dt>
            <dd style={{ margin: 0, overflowWrap: "anywhere" }} dir="ltr" data-src="record">
              {card.url.startsWith("http") ? (
                <a href={card.url} target="_blank" rel="noreferrer">
                  {card.url}
                </a>
              ) : (
                card.url
              )}
            </dd>
            <dt className="muted">{s("Skills")}</dt>
            <dd style={{ margin: 0 }} dir="ltr" data-src="record">
              {card.skills.join(", ")}
            </dd>
            <dt className="muted">{s("Authentication")}</dt>
            <dd style={{ margin: 0 }} data-src="record">
              {card.authentication}
            </dd>
          </dl>
        ) : (
          <p className="muted">{loading ? s("Loading…") : s("Not available.")}</p>
        )}
      </section>

      <section className="panel soft" style={{ marginTop: "1rem" }} aria-labelledby="log">
        <h2 id="log" className="section-title">{s("Recent exchanges")}</h2>
        {ex && ex.exchanges.length === 0 && (
          <p className="muted">{s("No exchanges yet. Open a case on the board and find care options to see the insurer check.")}</p>
        )}
        {ex && ex.exchanges.length > 0 && (
          <div className="table-scroll">
            <table className="data-table stack">
              <thead>
                <tr>
                  <th scope="col">{s("Time")}</th>
                  <th scope="col">{s("Skill")}</th>
                  <th scope="col">{s("Case")}</th>
                  <th scope="col">{s("Result")}</th>
                  <th scope="col">{s("Checks")}</th>
                </tr>
              </thead>
              <tbody>
                {ex.exchanges.map((e, i) => (
                  <tr key={`${e.at}-${i}`}>
                    <td data-label={s("Time")}>{L.date(e.at * 1000, { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</td>
                    <td data-label={s("Skill")} dir="ltr" data-src="record">
                      {e.skill}
                    </td>
                    <td data-label={s("Case")} dir="ltr" data-src="record">
                      {e.case_id || "—"}
                    </td>
                    <td data-label={s("Result")}>
                      <span>
                        <span className={`tag ${e.outcome === "accepted" ? "role" : "warn"}`}>{s(OUTCOME[e.outcome])}</span>{" "}
                        <span data-src="record">{e.reason_code}</span>
                      </span>
                    </td>
                    <td className="muted" data-label={s("Checks")}>
                      {e.signature_verified ? `${s("signature verified")} · ` : `${s(e.transport)} · `}
                      {s("schema checked")}
                      {e.dropped_fields.length > 0 && ` · ${s("dropped {fields}", { fields: e.dropped_fields.join(", ") })}`}
                      {e.error && <span data-src="record"> · {e.error}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
