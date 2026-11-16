"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, setApiPersona } from "@/lib/api";

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
  evidence?: {
    patient_display_name?: string;
    patient_display_name_ar?: string;
    payment_mode?: string;
    booked_option?: string;
    claim?: Claim;
  };
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
    payment?: Payment;
    reimbursement_guide?: { summary_en: string; summary_ar: string; steps_en: string[]; steps_ar: string[] };
    rationale_en?: string;
    rationale_ar?: string;
  }>;
  reassurance?: {
    answer: string;
    citations?: Array<{ id: string; title?: string }>;
    hand_off?: boolean;
    hand_off_offered?: boolean;
    ai_generated?: boolean;
    gap?: boolean;
  };
  concern?: { intent: string; crisis?: boolean; snippet?: string };
};

type Payment = {
  mode: "cashless" | "reimbursement" | "self_pay";
  patient_upfront_aed: number;
  expected_reimbursement_aed: number;
  claim_window_days?: number | null;
};

type Claim = {
  status: string;
  amount_claimed_aed?: number;
  expected_reimbursement_aed?: number;
  claim_window_days?: number;
  documents?: Array<{ id: string; label: string; provided: boolean }>;
  guide?: { summary_en: string; summary_ar: string; steps_en: string[]; steps_ar: string[] };
  insurer_ack?: { claim_reference?: string; decision_days?: number };
};

const STEPS: Array<[string, string]> = [
  ["Result", "النتيجة"],
  ["Understood", "الفهم"],
  ["Choose care", "اختيار الرعاية"],
  ["Booked", "الحجز"],
  ["Closed", "الإغلاق"],
];

function stepIndex(state: string): number {
  if (state === "Closed" || state === "ClosedByHuman") return 4;
  if (["Booked", "NoShow", "Attended", "ClosurePending"].includes(state)) return 3;
  if (state === "Referred" || state === "ReferralRejected") return 2;
  if (state === "Understood") return 1;
  return 0;
}

const BOOKED_STATES = ["Booked", "Attended", "ClosurePending", "Closed", "ClosedByHuman"];

/** Turn an API error ("{"detail": "..."}" or plain text) into a sentence a patient can read. */
function friendlyError(raw: string, rtl: boolean): string {
  let detail = raw.replace(/^Error:\s*/, "");
  try {
    const parsed = JSON.parse(detail);
    if (parsed && typeof parsed.detail === "string") detail = parsed.detail;
  } catch {
    /* plain text */
  }
  if (/failed to fetch|network/i.test(detail)) {
    return rtl ? "تعذر الاتصال بالخدمة. حاول مرة أخرى بعد لحظات." : "We could not reach the service. Please try again in a moment.";
  }
  return rtl ? `تعذر إكمال الطلب: ${detail}` : `That did not work: ${detail}`;
}

const PAY_LABEL: Record<string, [string, string]> = {
  cashless: ["Cashless (network)", "بدون دفع مسبق (ضمن الشبكة)"],
  reimbursement: ["Pay & claim back", "ادفع ثم استرد"],
  self_pay: ["Self-pay", "دفع ذاتي"],
};

export default function PatientCasePage() {
  const params = useParams<{ caseId: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const lang = search.get("lang") === "en" ? "en" : "ar";
  const [c, setC] = useState<Case | null>(null);
  const [answers, setAnswers] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [ttsNote, setTtsNote] = useState("");
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
    // Patient writes must not use the board coordinator persona (#85).
    setApiPersona("patient:fatima");
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
    setQuestion("");
    setAnswers([]);
    setTtsNote("");
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
    (lang === "ar"
      ? c?.evidence?.patient_display_name_ar || c?.evidence?.patient_display_name
      : c?.evidence?.patient_display_name) || (lang === "ar" ? "المريض" : "Patient");

  const stateLabels: Record<string, { en: string; ar: string }> = {
    New: { en: "New", ar: "جديد" },
    DataQuery: { en: "Data query", ar: "استعلام بيانات" },
    Triaged: { en: "Triaged", ar: "فُرزت" },
    Escalated: { en: "Escalated", ar: "مُصعَّدة" },
    AwaitingOwner: { en: "Awaiting owner", ar: "بانتظار المالك" },
    Owned: { en: "Owned", ar: "مملوكة" },
    PatientNotified: { en: "Patient notified", ar: "تم إشعار المريض" },
    Unreachable: { en: "Unreachable", ar: "تعذر الوصول" },
    HumanCallback: { en: "Human callback", ar: "اتصال بشري" },
    Understood: { en: "Understood", ar: "تم الفهم" },
    Referred: { en: "Referred", ar: "أُحيلت" },
    ReferralRejected: { en: "Referral rejected", ar: "رُفضت الإحالة" },
    Booked: { en: "Booked", ar: "محجوزة" },
    NoShow: { en: "No-show", ar: "لم يحضر" },
    Attended: { en: "Attended", ar: "حضر" },
    ClosurePending: { en: "Closure pending", ar: "بانتظار الإغلاق" },
    Closed: { en: "Closed", ar: "مغلقة" },
    ClosedByHuman: { en: "Closed by human", ar: "أُغلقت بشرياً" },
    OnHoldConsent: { en: "On hold (consent)", ar: "موقوفة (موافقة)" },
    Transferred: { en: "Transferred", ar: "مُحوَّلة" },
  };
  const stateLabel =
    (lang === "ar" ? stateLabels[c?.state || ""]?.ar : stateLabels[c?.state || ""]?.en) ||
    c?.state ||
    "—";

  const t = {
    title: rtl ? "بطاقة النتيجة" : "Your result",
    notDx: rtl ? "هذا ليس تشخيصاً" : "This is not a diagnosis",
    owner: rtl ? "المسؤول عن حالتك" : "Case owner",
    teach: rtl ? "تأكيد الفهم" : "Confirm you understood",
    next: rtl ? "اختر خطوتك التالية" : "Choose your next step",
    network: rtl
      ? "نعرض أولاً المستشفيات ضمن الشبكة بدون دفع مسبق، ثم خيارات الدفع والاسترداد إن كانت خطتك تسمح بها"
      : "Cashless network hospitals first; pay-and-claim options only when your plan reimburses them",
    book: rtl ? "احجز الموعد" : "Book this option",
    ask: rtl ? "رفيق الطمأنينة" : "Reassurance companion",
    askHint: rtl ? "نجيب فقط من قاعدة المعرفة المعتمدة" : "Answers only from the approved knowledge base",
    talk: rtl ? "تحدث إلى شخص" : "Talk to a person",
    submit: rtl ? "إرسال" : "Submit",
    askBtn: rtl ? "اسأل" : "Ask",
    askPlaceholder: rtl ? "مثال: ماذا تعني نتيجتي؟" : "For example: what does my result mean?",
    sources: rtl ? "المصادر المعتمدة" : "Approved sources",
    handoff: rtl ? "سيتواصل معك شخص من فريق الرعاية." : "A person from your care team will follow up.",
    appt: rtl ? "موعدك" : "Your appointment",
    apptClose: rtl
      ? "سيؤكد فريق الرعاية حضورك ويغلق الحلقة بدليل موثّق."
      : "Your care team confirms the visit and closes the loop with evidence.",
    progress: rtl ? "تقدّم رعايتك" : "Your progress",
    listen: rtl ? "استمع" : "Listen",
    noVoice: rtl ? "لا يتوفر صوت عربي على هذا الجهاز." : "No voice for this language on this device.",
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
          <section className="panel empty-state" role="alert">
            <h1 className="section-title">{t.missing}</h1>
            <Link className="btn" href="/">
              {t.back}
            </Link>
          </section>
        ) : err ? (
          <section className="panel empty-state" role="alert">
            <p>{friendlyError(err, rtl)}</p>
            <button type="button" className="btn" onClick={() => load()}>
              {rtl ? "حاول مرة أخرى" : "Try again"}
            </button>
          </section>
        ) : (
          <section className="panel skeleton" aria-busy="true" aria-live="polite">
            <span className="sr-only">{t.waking}</span>
            <div className="sk sk-line short" />
            <div className="sk sk-title" />
            <div className="sk sk-line" />
            <div className="sk sk-line" />
            <p className="muted small" aria-hidden>{t.waking}</p>
          </section>
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

  const bookedOption = BOOKED_STATES.includes(c.state)
    ? (c.options || []).find((o) => o.id === c.evidence?.booked_option)
    : undefined;

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
      {err ? (
        <div className="banner" role="alert">
          {friendlyError(err, rtl)}
        </div>
      ) : null}

      <ol className="stepper rise d2" aria-label={t.progress}>
        {STEPS.map(([en, ar], i) => {
          const at = stepIndex(c.state);
          const status = i < at ? "done" : i === at ? "current" : "todo";
          return (
            <li key={en} className={status} aria-current={status === "current" ? "step" : undefined}>
              <span className="dot" aria-hidden>
                {status === "done" ? "✓" : i + 1}
              </span>
              <span className="label">{rtl ? ar : en}</span>
            </li>
          );
        })}
      </ol>

      <section className="panel result-hero rise d2">
        <div className="chip-row">
          <span className="tag fact">{rtl ? "حقيقة مسجّلة" : "Recorded fact"}</span>
          <span className={`tag ${c.urgency === "CRITICAL" ? "urgent" : "calculated"}`}>{urgencyLabel}</span>
          <span className="tag role">
            {t.state}: {stateLabel}
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
          <div style={{ marginTop: "1rem", position: "relative" }}>
            <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>
              {viewMsg.ai_generated ? (
                <>
                  <span className="tag ai">AI</span>{" "}
                </>
              ) : null}
              {viewMsg.text.trim()}
            </p>
            <div className="row-actions" style={{ justifyContent: "flex-start" }}>
              <button
                type="button"
                className="btn secondary btn-sm"
                onClick={() => {
                  if (typeof window === "undefined" || !window.speechSynthesis) {
                    setTtsNote(t.noVoice);
                    return;
                  }
                  const want = lang === "ar" ? "ar" : "en";
                  const voices = window.speechSynthesis.getVoices();
                  if (voices.length && !voices.some((v) => v.lang.toLowerCase().startsWith(want))) {
                    setTtsNote(t.noVoice);
                  } else {
                    setTtsNote("");
                  }
                  const u = new SpeechSynthesisUtterance(viewMsg.text || "");
                  u.lang = lang === "ar" ? "ar-AE" : "en-US";
                  window.speechSynthesis.cancel();
                  window.speechSynthesis.speak(u);
                }}
              >
                <span aria-hidden>🔊</span> {t.listen}
              </button>
            </div>
            {ttsNote ? (
              <p className="muted small" role="status">
                {ttsNote}
              </p>
            ) : null}
          </div>
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
            disabled={
              busy ||
              !(viewMsg?.teachback || []).every((_, i) => Boolean(answers[i]))
            }
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

      {bookedOption ? (
        <section className="panel soft rise d3 appointment" style={{ marginTop: "0.9rem" }} aria-labelledby="appt-title">
          <h2 id="appt-title" style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>
            {t.appt}
          </h2>
          <div className="chip-row" style={{ marginBottom: "0.35rem" }}>
            <span className="tag ok">{stateLabel}</span>
            {bookedOption.payment ? (
              <span className={`tag ${bookedOption.payment.mode === "cashless" ? "ok" : "calculated"}`}>
                {PAY_LABEL[bookedOption.payment.mode]?.[rtl ? 1 : 0] ?? bookedOption.payment.mode}
              </span>
            ) : null}
          </div>
          <strong style={{ fontFamily: "var(--font-display)" }}>{bookedOption.name}</strong>
          <p className="muted" style={{ margin: "0.35rem 0 0.6rem" }}>
            {rtl ? bookedOption.rationale_ar : bookedOption.rationale_en}
          </p>
          {bookedOption.payment ? <p style={{ margin: "0 0 0.6rem" }}>{payExplain(bookedOption.payment, rtl)}</p> : null}
          <p className="muted small" style={{ margin: 0 }}>
            {t.apptClose}
          </p>
        </section>
      ) : c.options?.length ? (
        <section className="panel soft rise d3" style={{ marginTop: "0.9rem" }}>
          <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>{t.next}</h2>
          <p className="muted">{t.network}</p>
          <div style={{ display: "grid", gap: "0.75rem" }}>
            {c.options.map((o, idx) => (
              <div key={o.id} className="panel" style={{ boxShadow: "none", background: idx === 0 ? "var(--cyan-soft)" : "white" }}>
                <div className="chip-row" style={{ marginBottom: "0.35rem" }}>
                  {o.in_network ? <span className="tag ok">{rtl ? "ضمن الشبكة" : "In network"}</span> : null}
                  {o.payment ? (
                    <span className={`tag ${o.payment.mode === "cashless" ? "ok" : "calculated"}`}>
                      {PAY_LABEL[o.payment.mode]?.[rtl ? 1 : 0] ?? o.payment.mode}
                    </span>
                  ) : null}
                </div>
                <strong style={{ fontFamily: "var(--font-display)" }}>{o.name}</strong>
                <p className="muted" style={{ margin: "0.35rem 0 0.75rem" }}>
                  {rtl ? o.rationale_ar : o.rationale_en}
                </p>
                {o.reimbursement_guide ? (
                  <details style={{ marginBottom: "0.75rem" }}>
                    <summary>{rtl ? "كيف أسترد المبلغ؟" : "How do I claim the money back?"}</summary>
                    <p className="muted">{rtl ? o.reimbursement_guide.summary_ar : o.reimbursement_guide.summary_en}</p>
                    <ol>
                      {(rtl ? o.reimbursement_guide.steps_ar : o.reimbursement_guide.steps_en).map((step) => (
                        <li key={step}>{step}</li>
                      ))}
                    </ol>
                  </details>
                ) : null}
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

      {c.evidence?.claim ? (
        <section className="panel soft rise d3" style={{ marginTop: "0.9rem" }} aria-label="Reimbursement claim">
          <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>
            {rtl ? "مطالبة الاسترداد" : "Your reimbursement claim"}
          </h2>
          <p className="muted" style={{ marginTop: 0 }}>
            {rtl ? c.evidence.claim.guide?.summary_ar : c.evidence.claim.guide?.summary_en}
          </p>
          <p>
            <span className="tag calculated">{c.evidence.claim.status.replace(/_/g, " ")}</span>
            {c.evidence.claim.insurer_ack?.claim_reference ? (
              <span className="muted"> · {c.evidence.claim.insurer_ack.claim_reference}</span>
            ) : null}
          </p>
          <ul>
            {(c.evidence.claim.documents || []).map((d) => (
              <li key={d.id}>
                {d.provided ? "✓ " : "○ "}
                {d.label}
              </li>
            ))}
          </ul>
          {c.evidence.claim.status === "not_started" || c.evidence.claim.status === "rejected" ? (
            <button
              className="btn"
              type="button"
              disabled={busy}
              onClick={() =>
                run(async () => {
                  const updated = await api<Case>(`/cases/${c.case_id}/claim`, {
                    method: "POST",
                    body: JSON.stringify({ status: "documents_ready" }),
                  });
                  setC(updated);
                })
              }
            >
              {rtl ? "المستندات جاهزة" : "I have all documents"}
            </button>
          ) : null}
          {c.evidence.claim.status === "documents_ready" ? (
            <button
              className="btn"
              type="button"
              disabled={busy}
              onClick={() =>
                run(async () => {
                  const updated = await api<Case>(`/cases/${c.case_id}/claim`, {
                    method: "POST",
                    body: JSON.stringify({ status: "submitted" }),
                  });
                  setC(updated);
                })
              }
            >
              {rtl ? "أرسل المطالبة إلى شركة التأمين" : "Send claim to insurer"}
            </button>
          ) : null}
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
            placeholder={t.askPlaceholder}
            maxLength={500}
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
            disabled={busy || !question.trim()}
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
            {busy ? "…" : t.askBtn}
          </button>
        </div>
        {c.reassurance?.answer ? (
          <div className="answer" aria-live="polite">
            <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>
              {c.reassurance.ai_generated ? (
                <>
                  <span className="tag ai">AI</span>{" "}
                </>
              ) : null}
              {c.reassurance.answer}
            </p>
            {c.reassurance.citations?.length ? (
              <p className="muted small" style={{ margin: "0.5rem 0 0" }}>
                {t.sources}: {Array.from(new Set(c.reassurance.citations.map((x) => x.title || x.id))).join(" · ")}
              </p>
            ) : null}
            {c.reassurance.hand_off || c.reassurance.gap ? (
              <p className="small" style={{ margin: "0.5rem 0 0" }}>
                <span className="tag human">{t.talk}</span> {t.handoff}
              </p>
            ) : null}
          </div>
        ) : null}
        <h3 style={{ fontFamily: "var(--font-display)", marginTop: "1.2rem" }}>
          {rtl ? "لديّ قلق" : "I have a concern"}
        </h3>
        <button
          className="btn secondary"
          type="button"
          disabled={busy || !question.trim()}
          onClick={() =>
            run(async () => {
              if (!question.trim()) return;
              const updated = await api<Case & { concern?: { snippet?: string } }>(`/cases/${c.case_id}/concern`, {
                method: "POST",
                body: JSON.stringify({ text: question, language: lang }),
              });
              setC(updated);
            })
          }
        >
          {rtl ? "أرسل القلق للمنسق" : "Share concern with coordinator"}
        </button>
        {c.concern?.snippet ? (
          <p style={{ whiteSpace: "pre-wrap", marginTop: "0.9rem" }}>{c.concern.snippet}</p>
        ) : null}
      </section>
    </main>
  );
}

function payExplain(p: Payment, rtl: boolean): string {
  if (p.mode === "cashless") {
    return rtl
      ? `بدون دفع مسبق: أظهر بطاقة التأمين في العيادة. تدفع فقط ${p.patient_upfront_aed} درهم.`
      : `Cashless: show your insurance card at the clinic. You pay only AED ${p.patient_upfront_aed}.`;
  }
  if (p.mode === "reimbursement") {
    const days = p.claim_window_days ? (rtl ? ` خلال ${p.claim_window_days} يومًا` : ` within ${p.claim_window_days} days`) : "";
    return rtl
      ? `تدفع ${p.patient_upfront_aed} درهم عند الزيارة ثم تسترد ${p.expected_reimbursement_aed} درهم من التأمين${days}. نتابع المطالبة معك أدناه.`
      : `Pay AED ${p.patient_upfront_aed} at the visit, then claim AED ${p.expected_reimbursement_aed} back from your insurer${days}. We track the claim with you below.`;
  }
  return rtl ? `دفع ذاتي: ${p.patient_upfront_aed} درهم عند الزيارة.` : `Self-pay: AED ${p.patient_upfront_aed} at the visit.`;
}
