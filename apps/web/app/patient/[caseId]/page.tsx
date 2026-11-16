"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

type TeachQ = { prompt: string; choices: string[]; correct: string };

type LangBundle = {
  text?: string;
  banner?: string;
  teachback?: TeachQ[];
  ai_generated?: boolean;
  language?: string;
};

type Case = {
  case_id: string;
  state: string;
  urgency?: string;
  result_display?: string;
  result_value?: string;
  result_unit?: string;
  language?: string;
  owner_name?: string;
  evidence?: { patient_display_name?: string };
  messages: Array<
    LangBundle & {
      by_lang?: Record<string, LangBundle>;
    }
  >;
  options: Array<{
    id: string;
    name: string;
    score: number;
    in_network: boolean;
    rationale_en?: string;
    rationale_ar?: string;
  }>;
  reassurance?: { answer: string; citations?: Array<{ id: string }>; hand_off_offered?: boolean };
};

export default function PatientCasePage() {
  const params = useParams<{ caseId: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const lang = search.get("lang") === "en" ? "en" : "ar";
  const [c, setC] = useState<Case | null>(null);
  const [answers, setAnswers] = useState<string[]>([]);
  const [question, setQuestion] = useState(lang === "ar" ? "هل لدي سرطان؟" : "Do I have cancer?");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const rtl = lang === "ar";

  const load = async () => {
    try {
      const data = await api<Case>(`/cases/${params.caseId}`);
      setC(data);
      setNotFound(false);
    } catch (e) {
      const msg = String(e);
      if (msg.toLowerCase().includes("not found") || msg.includes("404")) {
        setNotFound(true);
      }
      setErr(msg);
      setC(null);
    }
  };

  useEffect(() => {
    load().catch((e) => setErr(String(e)));
  }, [params.caseId]);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = rtl ? "rtl" : "ltr";
    return () => {
      document.documentElement.lang = "en";
      document.documentElement.dir = "ltr";
    };
  }, [lang, rtl]);

  useEffect(() => {
    setQuestion(lang === "ar" ? "هل لدي سرطان؟" : "Do I have cancer?");
    setAnswers([]);
  }, [lang]);

  const latestMsg = useMemo(() => {
    if (!c?.messages?.length) return null;
    return [...c.messages].reverse().find((m) => m.text || m.by_lang) || c.messages[c.messages.length - 1];
  }, [c]);

  const viewMsg: LangBundle | null = useMemo(() => {
    if (!latestMsg) return null;
    const localized = latestMsg.by_lang?.[lang];
    if (localized?.text) return localized;
    return latestMsg;
  }, [latestMsg, lang]);

  const firstName =
    c?.evidence?.patient_display_name ||
    (lang === "ar" ? "المريض" : "Patient");

  const t = {
    title: rtl ? "بطاقة النتيجة" : "Your result",
    notDx: rtl ? "هذا ليس تشخيصاً" : "This is not a diagnosis",
    owner: rtl ? "المسؤول عن حالتك" : "Case owner",
    teach: rtl ? "تأكيد الفهم" : "Confirm you understood",
    next: rtl ? "اختر خطوتك التالية" : "Choose your next step",
    network: rtl ? "ضمن شبكة تأمينك فقط" : "In-network options only",
    book: rtl ? "احجز الموعد" : "Book this option",
    ask: rtl ? "رفيق الطمأنينة" : "Reassurance companion",
    askHint: rtl ? "نجيب فقط من قاعدة المعرفة المعتمدة" : "Answers only from the approved knowledge base",
    talk: rtl ? "تحدث إلى شخص" : "Talk to a person",
    submit: rtl ? "إرسال" : "Submit",
    back: rtl ? "العودة" : "Back",
    state: rtl ? "حالة الحلقة" : "Loop state",
    waking: rtl ? "إيقاظ العرض التجريبي (حتى ~20 ثانية)…" : "Waking up the demo (up to ~20 s)…",
    missing: rtl ? "الحالة غير موجودة أو أُعيد ضبط العرض" : "Case not found or demo was reset",
    hello: rtl ? `مرحباً ${firstName}` : `Hello, ${firstName}`,
  };

  const setLang = (next: "ar" | "en") => {
    const q = new URLSearchParams(search.toString());
    q.set("lang", next);
    router.replace(`/patient/${params.caseId}?${q.toString()}`);
  };

  if (!c) {
    const missing = /not found|404/i.test(err);
    return (
      <main className="shell phone-shell" dir={rtl ? "rtl" : "ltr"}>
        {notFound || missing ? (
          <>
            <p>{t.missing}</p>
            <Link className="btn" href="/">
              {t.back}
            </Link>
          </>
        ) : (
          <p className="muted">{err || t.waking}</p>
        )}
      </main>
    );
  }

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setErr("");
    try {
      await fn();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const urgencyLabel =
    lang === "ar"
      ? { CRITICAL: "حرج", URGENT: "عاجل", ROUTINE: "روتيني" }[c.urgency || ""] || c.urgency
      : c.urgency;

  return (
    <main className="shell phone-shell" dir={rtl ? "rtl" : "ltr"}>
      <div className="topbar rise">
        <div className="brand-mark">
          <div className="mark">ر</div>
          <div>
            <div style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>ربط · Rabt</div>
            <div className="muted" style={{ fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "0.35rem" }}>
              <span className="live-dot" /> {t.title}
            </div>
          </div>
        </div>
        <div className="actions" style={{ marginTop: 0 }}>
          <button
            type="button"
            className={`btn ${lang === "ar" ? "" : "ghost"}`}
            aria-pressed={lang === "ar"}
            onClick={() => setLang("ar")}
          >
            ع
          </button>
          <button
            type="button"
            className={`btn ${lang === "en" ? "" : "ghost"}`}
            aria-pressed={lang === "en"}
            onClick={() => setLang("en")}
          >
            EN
          </button>
          <Link className="btn secondary" href="/">
            {t.back}
          </Link>
        </div>
      </div>

      <div className="banner rise d2">{t.notDx}</div>
      {err ? <div className="banner">{err}</div> : null}

      <section className="panel result-hero rise d2">
        <div className="chip-row">
          <span className="tag fact">{rtl ? "حقيقة مسجّلة" : "Recorded fact"}</span>
          <span className={`tag ${c.urgency === "CRITICAL" ? "urgent" : "calculated"}`}>{urgencyLabel}</span>
          <span className="tag role">
            {t.state}: {c.state}
          </span>
        </div>
        <p className="muted" style={{ margin: "0 0 0.35rem" }}>
          {t.hello}
        </p>
        <h1>
          {c.result_display}
          {c.result_value ? (
            <>
              {" · "}
              <bdi>
                {c.result_value}
                {c.result_unit ? ` ${c.result_unit}` : ""}
              </bdi>
            </>
          ) : null}
        </h1>
        <p className="muted" style={{ margin: 0, position: "relative" }}>
          {t.owner}: <strong>{c.owner_name || "—"}</strong>
        </p>
        {viewMsg?.text ? (
          <p style={{ whiteSpace: "pre-wrap", marginTop: "1rem", position: "relative" }}>
            {viewMsg.ai_generated ? <span className="tag ai">AI</span> : null} {viewMsg.text}
          </p>
        ) : null}
      </section>

      {viewMsg?.teachback?.length && c.state === "PatientNotified" ? (
        <section className="panel soft rise d3" style={{ marginTop: "0.9rem" }}>
          <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0, letterSpacing: "-0.02em" }}>
            {t.teach}
          </h2>
          {viewMsg.teachback.map((q, i) => (
            <div key={q.prompt} style={{ marginBottom: "1rem" }}>
              <p style={{ fontWeight: 600 }}>{q.prompt}</p>
              <div className="choices" role="group" aria-label={q.prompt}>
                {q.choices.map((ch) => (
                  <button
                    key={ch}
                    type="button"
                    className={`choice ${answers[i] === ch ? "selected" : ""}`}
                    aria-pressed={answers[i] === ch}
                    onClick={() => {
                      const next = [...answers];
                      next[i] = ch;
                      setAnswers(next);
                    }}
                  >
                    {ch}
                  </button>
                ))}
              </div>
            </div>
          ))}
          <button
            className="btn"
            type="button"
            disabled={busy}
            onClick={() =>
              run(async () => {
                const updated = await api<Case>(`/cases/${c.case_id}/teachback`, {
                  method: "POST",
                  body: JSON.stringify({ answers }),
                });
                setC(updated);
              })
            }
          >
            {t.submit}
          </button>
        </section>
      ) : null}

      {c.options?.length ? (
        <section className="panel soft rise d3" style={{ marginTop: "0.9rem" }}>
          <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>{t.next}</h2>
          <p className="muted">{t.network}</p>
          <div style={{ display: "grid", gap: "0.75rem" }}>
            {c.options.map((o, idx) => (
              <div key={o.id} className="panel" style={{ boxShadow: "none", background: idx === 0 ? "var(--cyan-soft)" : "white" }}>
                <div className="chip-row" style={{ marginBottom: "0.35rem" }}>
                  {o.in_network ? <span className="tag ok">{rtl ? "ضمن الشبكة" : "In network"}</span> : null}
                  <span className="tag calculated">score {o.score}</span>
                </div>
                <strong style={{ fontFamily: "var(--font-display)" }}>{o.name}</strong>
                <p className="muted" style={{ margin: "0.35rem 0 0.75rem" }}>
                  {rtl ? o.rationale_ar : o.rationale_en}
                </p>
                {c.state === "Referred" ? (
                  <button
                    className="btn"
                    type="button"
                    disabled={busy}
                    onClick={() =>
                      run(async () => {
                        const updated = await api<Case>(`/cases/${c.case_id}/book`, {
                          method: "POST",
                          body: JSON.stringify({ option_id: o.id }),
                        });
                        setC(updated);
                      })
                    }
                  >
                    {t.book}
                  </button>
                ) : null}
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="panel rise d4" style={{ marginTop: "0.9rem" }}>
        <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>{t.ask}</h2>
        <p className="muted" style={{ marginTop: 0 }}>{t.askHint}</p>
        <label className="muted" style={{ display: "block", fontSize: "0.85rem", marginBottom: "0.75rem" }}>
          {rtl ? "سؤالك" : "Your question"}
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            aria-label={rtl ? "سؤالك" : "Your question"}
            style={{
              display: "block",
              width: "100%",
              marginTop: "0.35rem",
              padding: "0.8rem 0.95rem",
              borderRadius: "0.9rem",
              border: "1px solid var(--line)",
              background: "white",
              color: "var(--ink)",
            }}
          />
        </label>
        <div className="actions" style={{ marginTop: 0 }}>
          <button
            className="btn"
            type="button"
            disabled={busy}
            onClick={() =>
              run(async () => {
                const updated = await api<Case>(`/cases/${c.case_id}/reassure`, {
                  method: "POST",
                  body: JSON.stringify({ question }),
                });
                setC(updated);
              })
            }
          >
            {t.submit}
          </button>
        </div>
        {c.reassurance?.answer ? (
          <p style={{ whiteSpace: "pre-wrap", marginTop: "0.9rem" }}>{c.reassurance.answer}</p>
        ) : null}
      </section>
    </main>
  );
}
