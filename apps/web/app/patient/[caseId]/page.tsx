"use client";

import { type ReactElement, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, setApiPersona } from "@/lib/api";
import { PATIENT_LOCALES, type Locale, type LocaleApi, useLocale } from "@/lib/i18n";
import { useTranslated } from "@/lib/translate";
import { speak, stopSpeaking } from "@/lib/speech";
import { LangSwitcher } from "@/components/LangSwitcher";
import { ChatLauncher, type ChatContext } from "@/components/ChatLauncher";
import { PwaRegister } from "@/components/PwaRegister";

type TeachQ = { prompt: string; choices: string[]; correct: string };
type LangBundle = { text?: string; banner?: string; teachback?: TeachQ[]; ai_generated?: boolean; language?: string };
type Payment = {
  mode: "cashless" | "reimbursement" | "self_pay";
  patient_upfront_aed: number;
  expected_reimbursement_aed: number;
  claim_window_days?: number | null;
};
type Guide = { summary_en: string; summary_ar: string; steps_en: string[]; steps_ar: string[] };
type Claim = {
  status: string;
  amount_claimed_aed?: number;
  expected_reimbursement_aed?: number;
  claim_window_days?: number;
  documents?: Array<{ id: string; label: string; provided: boolean; checked?: boolean }>;
  guide?: Guide;
  insurer_ack?: { claim_reference?: string; decision_days?: number };
};
type DocRecord = { name: string; doc_id?: string | null; status: "accepted" | "quarantined"; stripped?: string[]; flags?: string[] };
type Option = {
  id: string;
  name: string;
  score: number;
  in_network: boolean;
  payment?: Payment;
  reimbursement_guide?: Guide;
  rationale_en?: string;
  rationale_ar?: string;
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
    age?: number;
    assisted?: boolean;
    callback_requested?: boolean;
    caregiver?: { name: string; relation: string };
    documents?: DocRecord[];
    preferences?: { language?: string; easy_mode?: boolean };
  };
  messages: Array<LangBundle & { by_lang?: Record<string, LangBundle> }>;
  options: Option[];
};

const POLL_MS = 4000;
const BOOKED_STATES = ["Booked", "Attended", "ClosurePending", "Closed", "ClosedByHuman"];
const STEP_KEYS = ["p.step.result", "p.step.understood", "p.step.choose", "p.step.booked", "p.step.closed"] as const;

function stepIndex(state: string): number {
  if (state === "Closed" || state === "ClosedByHuman") return 4;
  if (["Booked", "NoShow", "Attended", "ClosurePending"].includes(state)) return 3;
  if (state === "Referred" || state === "ReferralRejected") return 2;
  if (state === "Understood") return 1;
  return 0;
}

function chatContext(state: string): ChatContext {
  const i = stepIndex(state);
  if (i === 4) return "default";
  if (i === 3) return "booking";
  if (i === 2) return "referral";
  return "result";
}

/** Server-written text (result card, clinic rationale, guides): native in EN/AR, translated on demand otherwise. */
function Tx({ text, L, as = "span", className }: { text?: string | null; L: LocaleApi; as?: "span" | "p" | "strong" | "li"; className?: string }) {
  const tr = useTranslated(text, L.lang);
  const Tag = as;
  if (!text) return null;
  return (
    <Tag className={className} lang={tr.ai || L.lang === "en" || L.lang === "ar" ? L.lang : "en"} dir="auto" aria-busy={tr.pending || undefined}>
      {tr.ai ? (
        <span className="tag role tx-tag" title={L.t("common.aiTranslated")}>
          {L.t("common.aiTranslated")}
        </span>
      ) : null}
      {tr.ai ? " " : null}
      {L.digits(tr.text)}
      {tr.failed ? <span className="sr-only"> ({L.t("common.translationUnavailable")})</span> : null}
    </Tag>
  );
}

function pick<T>(lang: Locale, en: T | undefined, ar: T | undefined): T | undefined {
  return lang === "ar" ? ar ?? en : en ?? ar;
}

function errorText(raw: string, L: LocaleApi): string {
  return /failed to fetch|network|load failed/i.test(raw) ? L.t("err.network") : L.t("err.generic");
}

async function toBase64(file: File): Promise<string> {
  const buf = new Uint8Array(await file.arrayBuffer());
  let bin = "";
  for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode(...buf.subarray(i, i + 0x8000));
  return btoa(bin);
}

export default function PatientCasePage() {
  const params = useParams<{ caseId: string }>();
  const search = useSearchParams();
  const L = useLocale({ allowed: PATIENT_LOCALES, initial: search.get("lang"), fallback: "ar" });
  const { t, lang, rtl } = L;
  const [c, setC] = useState<Case | null>(null);
  const [answers, setAnswers] = useState<string[]>([]);
  const [err, setErr] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [easy, setEasy] = useState(false);
  const [easySuggested, setEasySuggested] = useState(false);
  const [step, setStep] = useState(0);
  const [showAll, setShowAll] = useState(false);
  const [reading, setReading] = useState(false);
  const [lastDoc, setLastDoc] = useState<DocRecord | null>(null);
  const [helper, setHelper] = useState({ name: "", relation: "son", last4: "", consent: false });
  const easyInit = useRef(false);
  const main = useRef<HTMLElement>(null);

  const load = useCallback(async () => {
    try {
      const data = await api<Case>(`/cases/${params.caseId}`);
      setC(data);
      setNotFound(false);
      setErr("");
    } catch (e) {
      const msg = String(e);
      if (/not found|404/i.test(msg)) setNotFound(true);
      setErr(msg);
    }
  }, [params.caseId]);

  useEffect(() => {
    setApiPersona("patient:fatima");
    void load();
  }, [load]);

  // Near-live: coordinator actions on the board show up on the phone without a reload.
  useEffect(() => {
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible" && !busy) void load();
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [load, busy]);

  // Easy mode: ?easy=1, the saved choice, or suggested automatically for patients aged 60+.
  useEffect(() => {
    if (!c || easyInit.current) return;
    easyInit.current = true;
    const key = `rabt.easy.${c.case_id}`;
    const q = search.get("easy");
    let saved: string | null = null;
    try {
      saved = window.localStorage.getItem(key);
    } catch {
      /* ignore */
    }
    if (q === "1" || q === "0") setEasy(q === "1");
    else if (saved === "1" || saved === "0") setEasy(saved === "1");
    else if (c.evidence?.preferences?.easy_mode != null) setEasy(!!c.evidence.preferences.easy_mode);
    else if ((c.evidence?.age || 0) >= 60 || c.evidence?.assisted) {
      setEasy(true);
      setEasySuggested(true);
    }
  }, [c, search]);

  useEffect(() => {
    document.documentElement.classList.toggle("easy-mode", easy);
    return () => document.documentElement.classList.remove("easy-mode");
  }, [easy]);

  useEffect(() => {
    document.title = t("app.title");
  }, [t]);

  const savePrefs = useCallback(
    (body: { language?: Locale; easy_mode?: boolean }) => {
      api(`/cases/${params.caseId}/preferences`, { method: "POST", body: JSON.stringify(body) }).catch(() => undefined);
    },
    [params.caseId]
  );

  const toggleEasy = () => {
    const next = !easy;
    setEasy(next);
    setEasySuggested(false);
    setStep(0);
    try {
      window.localStorage.setItem(`rabt.easy.${params.caseId}`, next ? "1" : "0");
    } catch {
      /* ignore */
    }
    savePrefs({ easy_mode: next });
  };

  const latestMsg = useMemo(() => {
    if (!c?.messages?.length) return null;
    return [...c.messages].reverse().find((m) => m.text || m.by_lang) || c.messages[c.messages.length - 1];
  }, [c]);

  const viewMsg: LangBundle | null = useMemo(() => {
    if (!latestMsg) return null;
    const native = latestMsg.by_lang?.[lang];
    if (native?.text) return native;
    if (lang !== "ar") return latestMsg.by_lang?.en?.text ? latestMsg.by_lang.en : latestMsg;
    return latestMsg;
  }, [latestMsg, lang]);

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

  if (!c) {
    return (
      <main className="shell phone-shell" dir={L.dir}>
        {notFound ? (
          <section className="panel empty-state" role="alert">
            <h1 className="section-title">{t("common.missing")}</h1>
            <Link className="btn" href="/">
              {t("common.back")}
            </Link>
          </section>
        ) : err ? (
          <section className="panel empty-state" role="alert">
            <p>{errorText(err, L)}</p>
            <button type="button" className="btn" onClick={() => load()}>
              {t("common.tryAgain")}
            </button>
          </section>
        ) : (
          <section className="panel skeleton" aria-busy="true" aria-live="polite">
            <span className="sr-only">{t("common.waking")}</span>
            <div className="sk sk-line short" />
            <div className="sk sk-title" />
            <div className="sk sk-line" />
            <div className="sk sk-line" />
            <p className="muted small" aria-hidden>
              {t("common.waking")}
            </p>
          </section>
        )}
      </main>
    );
  }

  const name =
    (lang === "ar" ? c.evidence?.patient_display_name_ar || c.evidence?.patient_display_name : c.evidence?.patient_display_name) ||
    t("p.patient");
  const at = stepIndex(c.state);
  const bookedOption = BOOKED_STATES.includes(c.state) ? (c.options || []).find((o) => o.id === c.evidence?.booked_option) : undefined;
  const showTeach = !!viewMsg?.teachback?.length && c.state === "PatientNotified";
  const options = c.options || [];
  const claim = c.evidence?.claim;
  const closed = at === 4;

  const payText = (p: Payment) =>
    p.mode === "cashless"
      ? t("p.payCashless", { amount: L.num(p.patient_upfront_aed) })
      : p.mode === "reimbursement"
        ? t("p.payReimb", { upfront: L.num(p.patient_upfront_aed), back: L.num(p.expected_reimbursement_aed), days: L.num(p.claim_window_days || 30) })
        : t("p.paySelf", { amount: L.num(p.patient_upfront_aed) });

  const callMe = () =>
    run(async () => {
      const updated = await api<Case>(`/cases/${c.case_id}/callback-request`, {
        method: "POST",
        body: JSON.stringify({ reason: easy ? "easy_mode_call_me" : "patient_call_me" }),
      });
      setC(updated);
      setNote(t("e.callRequested"));
    });

  const book = (o: Option) =>
    run(async () => {
      const updated = await api<Case>(`/cases/${c.case_id}/book`, { method: "POST", body: JSON.stringify({ option_id: o.id }) });
      setC(updated);
    });

  const submitTeach = () =>
    run(async () => {
      const updated = await api<Case>(`/cases/${c.case_id}/teachback`, { method: "POST", body: JSON.stringify({ answers }) });
      setC(updated);
      setAnswers([]);
    });

  const setClaim = (status: string) =>
    run(async () => {
      const updated = await api<Case>(`/cases/${c.case_id}/claim`, { method: "POST", body: JSON.stringify({ status }) });
      setC(updated);
    });

  const upload = (file: File, docId?: string) =>
    run(async () => {
      setLastDoc(null);
      const updated = await api<Case>(`/cases/${c.case_id}/documents`, {
        method: "POST",
        body: JSON.stringify({ filename: file.name.slice(-120), content_b64: await toBase64(file), purpose: "claim", doc_id: docId || null }),
      });
      setC(updated);
      const docs = updated.evidence?.documents || [];
      setLastDoc(docs[docs.length - 1] || null);
    });

  const addHelper = () =>
    run(async () => {
      const updated = await api<Case>(`/cases/${c.case_id}/caregiver`, {
        method: "POST",
        body: JSON.stringify({ name: helper.name.trim(), relation: helper.relation, phone_last4: helper.last4, consent: helper.consent }),
      });
      setC(updated);
      setNote(t("e.helperAdded", { name: helper.name.trim() }));
    });

  /* ---------- sections ---------- */

  const resultSection = (
    <section className="panel result-hero rise d2" aria-labelledby="result-title">
      <div className="chip-row">
        <span className="tag fact">{t("p.recordedFact")}</span>
        {c.urgency ? (
          <span className={`tag ${c.urgency === "CRITICAL" ? "urgent" : "calculated"}`}>
            {t(`p.urgency.${c.urgency}` as "p.urgency.ROUTINE")}
          </span>
        ) : null}
      </div>
      <p className="muted hello">{t("p.hello", { name })}</p>
      <h1 id="result-title">
        <Tx text={c.result_display} L={L} />
        {c.result_value ? (
          <>
            {" · "}
            <bdi>
              {/^(positive|negative)$/i.test(String(c.result_value))
                ? t(`p.val.${String(c.result_value).toLowerCase()}` as "p.val.positive")
                : L.digits(String(c.result_value))}
              {c.result_unit ? ` ${c.result_unit}` : ""}
            </bdi>
          </>
        ) : null}
      </h1>
      <p className="muted owner">
        {t("p.owner")}: <strong data-src="record">{c.owner_name || "—"}</strong>
      </p>
      {viewMsg?.text ? (
        <div className="result-message">
          <p className="message-text">
            {viewMsg.ai_generated ? <span className="tag ai">{t("common.aiTag")}</span> : null} <Tx text={viewMsg.text.trim()} L={L} />
          </p>
          <ReadAloud text={viewMsg.text} L={L} />
        </div>
      ) : null}
    </section>
  );

  const teachSection = showTeach ? (
    <section className="panel soft rise d3" aria-labelledby="teach-title">
      <h2 id="teach-title" className="section-title">
        {t("p.teach")}
      </h2>
      {(viewMsg?.teachback || []).map((q, i) => (
        <fieldset key={q.prompt} className="teach-q">
          <legend>
            <Tx text={q.prompt} L={L} />
          </legend>
          <div className="choices">
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
                <Tx text={ch} L={L} />
              </button>
            ))}
          </div>
        </fieldset>
      ))}
      <button className="btn" type="button" disabled={busy || !(viewMsg?.teachback || []).every((_, i) => Boolean(answers[i]))} onClick={submitTeach}>
        {t("p.submit")}
      </button>
    </section>
  ) : null;

  const optionCard = (o: Option, idx: number, recommended = false) => (
    <div key={o.id} className={`option-card ${idx === 0 ? "top" : ""}`}>
      <div className="chip-row">
        {recommended ? <span className="tag ok">{t("e.recommended")}</span> : null}
        {o.in_network ? <span className="tag ok">{t("p.inNetwork")}</span> : null}
        {o.payment ? (
          <span className={`tag ${o.payment.mode === "cashless" ? "ok" : "calculated"}`}>{t(`p.pay.${o.payment.mode}` as "p.pay.cashless")}</span>
        ) : null}
      </div>
      <strong className="option-name" data-src="record">
        {o.name}
      </strong>
      <Tx as="p" className="muted" text={pick(lang, o.rationale_en, o.rationale_ar)} L={L} />
      {o.payment ? <p className="pay-line">{payText(o.payment)}</p> : null}
      {o.reimbursement_guide && !easy ? (
        <details>
          <summary>{t("p.howClaim")}</summary>
          <Tx as="p" className="muted" text={pick(lang, o.reimbursement_guide.summary_en, o.reimbursement_guide.summary_ar)} L={L} />
          <ol>
            {(pick(lang, o.reimbursement_guide.steps_en, o.reimbursement_guide.steps_ar) || []).map((s) => (
              <Tx as="li" key={s} text={s} L={L} />
            ))}
          </ol>
        </details>
      ) : null}
      {c.state === "Referred" ? (
        <button className="btn" type="button" disabled={busy} onClick={() => book(o)}>
          {busy ? t("p.booking") : t("p.book")}
        </button>
      ) : null}
    </div>
  );

  const chooseSection =
    !bookedOption && options.length ? (
      <section className="panel soft rise d3" aria-labelledby="next-title">
        <h2 id="next-title" className="section-title">
          {t("p.next")}
        </h2>
        <p className="muted">{t("p.networkNote")}</p>
        <div className="option-list">
          {easy && !showAll ? optionCard(options[0], 0, true) : options.map((o, i) => optionCard(o, i, i === 0 && easy))}
        </div>
        {easy ? (
          <div className="row-actions">
            <button type="button" className="btn secondary big" onClick={callMe} disabled={busy || !!c.evidence?.callback_requested}>
              <span aria-hidden="true">📞</span> {t("e.callMe")}
            </button>
            {options.length > 1 && !showAll ? (
              <button type="button" className="btn ghost" onClick={() => setShowAll(true)}>
                {t("e.moreOptions")}
              </button>
            ) : null}
          </div>
        ) : null}
      </section>
    ) : null;

  const apptSection = bookedOption ? (
    <section className="panel soft rise d3 appointment" aria-labelledby="appt-title">
      <h2 id="appt-title" className="section-title">
        {t("p.appt")}
      </h2>
      <div className="chip-row">
        <span className="tag ok">{t(at >= 4 ? "p.step.closed" : "p.step.booked")}</span>
        {bookedOption.payment ? (
          <span className={`tag ${bookedOption.payment.mode === "cashless" ? "ok" : "calculated"}`}>
            {t(`p.pay.${bookedOption.payment.mode}` as "p.pay.cashless")}
          </span>
        ) : null}
      </div>
      <strong className="option-name" data-src="record">
        {bookedOption.name}
      </strong>
      <Tx as="p" className="muted" text={pick(lang, bookedOption.rationale_en, bookedOption.rationale_ar)} L={L} />
      {bookedOption.payment ? <p className="pay-line">{payText(bookedOption.payment)}</p> : null}
      {easy ? (
        <ul className="easy-hints">
          <li>{t("e.reminders")}</li>
          <li>{t("e.transport")}</li>
        </ul>
      ) : null}
      {c.evidence?.payment_mode === "unverified" && !closed ? (
        <div className="banner info" role="status">
          {t("p.coverageChecking")}
        </div>
      ) : null}
      <p className="muted small">{closed ? t("p.closedNote") : t("p.apptClose")}</p>
    </section>
  ) : null;

  const claimSection = claim ? (
    <section className="panel soft rise d3" aria-labelledby="claim-title">
      <h2 id="claim-title" className="section-title">
        {t("p.claim")}
      </h2>
      <Tx as="p" className="muted" text={pick(lang, claim.guide?.summary_en, claim.guide?.summary_ar)} L={L} />
      <p>
        <span className={`tag ${claim.status === "paid" || claim.status === "approved" ? "ok" : claim.status === "rejected" ? "urgent" : "calculated"}`}>
          {(PATIENT_CLAIM as readonly string[]).includes(claim.status) ? t(`p.claim.${claim.status}` as "p.claim.paid") : t("p.claim.documents_needed")}
        </span>
        {claim.insurer_ack?.claim_reference ? (
          <span className="muted" data-src="record">
            {" "}
            · {claim.insurer_ack.claim_reference}
          </span>
        ) : null}
      </p>
      <h3 className="small-title">{t("p.claimDocs")}</h3>
      <ul className="doc-list">
        {(claim.documents || []).map((d) => (
          <li key={d.id} className={d.provided ? "done" : ""}>
            <span aria-hidden="true">{d.provided ? "✓" : "○"}</span> <Tx text={d.label} L={L} />
            {d.checked ? <span className="tag ok">{t("p.docChecked")}</span> : null}
          </li>
        ))}
      </ul>
      <div className="upload">
        <label className="btn secondary upload-btn">
          <input
            type="file"
            accept="application/pdf,image/png,image/jpeg"
            className="sr-only"
            disabled={busy}
            onChange={(e) => {
              const f = e.target.files?.[0];
              const firstMissing = (claim.documents || []).find((d) => !d.provided);
              if (f) void upload(f, firstMissing?.id);
              e.target.value = "";
            }}
          />
          <span aria-hidden="true">⬆</span> {t("p.upload")}
        </label>
        <p className="muted small">{t("p.uploadHint")}</p>
        <div aria-live="polite">
          {busy && !lastDoc ? <p className="small">{t("p.uploading")}</p> : null}
          {lastDoc ? (
            lastDoc.status === "accepted" ? (
              <p className="doc-status ok">
                <span aria-hidden="true">🛡️</span> {t("p.docChecked")}
                {lastDoc.stripped?.length ? <span className="muted"> · {t("p.docStripped", { items: lastDoc.stripped.join(", ") })}</span> : null}
              </p>
            ) : (
              <p className="doc-status held" role="alert">
                <span aria-hidden="true">⚠</span> {t("p.docHeld")}
              </p>
            )
          ) : null}
        </div>
      </div>
      {claim.status === "not_started" || claim.status === "rejected" || claim.status === "documents_needed" ? (
        <button className="btn" type="button" disabled={busy} onClick={() => setClaim("documents_ready")}>
          {t("p.claimDocsReady")}
        </button>
      ) : null}
      {claim.status === "documents_ready" ? (
        <button className="btn" type="button" disabled={busy} onClick={() => setClaim("submitted")}>
          {t("p.claimSend")}
        </button>
      ) : null}
    </section>
  ) : null;

  const helperSection = (
    <section className="panel soft rise d4" aria-labelledby="helper-title">
      <h2 id="helper-title" className="section-title">
        {t("e.family")}
      </h2>
      {c.evidence?.caregiver ? (
        <p className="doc-status ok">{t("e.helperAdded", { name: c.evidence.caregiver.name })}</p>
      ) : (
        <form
          className="helper-form"
          onSubmit={(e) => {
            e.preventDefault();
            void addHelper();
          }}
        >
          <p className="muted">{t("e.familyHint")}</p>
          <label>
            {t("e.familyName")}
            <input className="field" value={helper.name} maxLength={40} required onChange={(e) => setHelper({ ...helper, name: e.target.value })} />
          </label>
          <label>
            {t("e.relation")}
            <select className="field" value={helper.relation} onChange={(e) => setHelper({ ...helper, relation: e.target.value })}>
              {(["son", "daughter", "spouse", "other"] as const).map((r) => (
                <option key={r} value={r}>
                  {t(`e.rel.${r}`)}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t("e.phoneLast4")}
            <input
              className="field"
              inputMode="numeric"
              pattern="[0-9]{4}"
              maxLength={4}
              dir="ltr"
              required
              value={helper.last4}
              onChange={(e) => setHelper({ ...helper, last4: e.target.value.replace(/\D/g, "") })}
            />
          </label>
          <label className="check">
            <input type="checkbox" checked={helper.consent} onChange={(e) => setHelper({ ...helper, consent: e.target.checked })} />
            <span>{t("e.consent")}</span>
          </label>
          <button className="btn" type="submit" disabled={busy || !helper.consent || helper.last4.length !== 4 || !helper.name.trim()}>
            {t("e.addHelper")}
          </button>
        </form>
      )}
    </section>
  );

  const easySteps = [resultSection, teachSection, chooseSection || apptSection, claimSection, helperSection].filter(Boolean) as ReactElement[];
  const stepNow = Math.min(step, easySteps.length - 1);

  const readScreen = () => {
    if (reading) {
      stopSpeaking();
      setReading(false);
      return;
    }
    const text = main.current?.querySelector<HTMLElement>("[data-read]")?.innerText || main.current?.innerText || "";
    if (speak(text, L.meta.voice, () => setReading(false))) setReading(true);
    else setNote(t("p.noVoice"));
  };

  return (
    <main ref={main} className={`shell phone-shell ${easy ? "easy" : ""}`} dir={L.dir}>
      <a href="#content" className="skip-link">
        {t("p.title")}
      </a>
      <div className="topbar rise">
        <div className="brand-mark">
          <div className="mark" aria-hidden="true">
            ر
          </div>
          <div>
            <div className="brand-name">{t("app.name")}</div>
            <div className="muted brand-sub">
              <span className="live-dot on" aria-hidden="true" /> {t("p.title")}
            </div>
          </div>
        </div>
        <div className="actions top-actions">
          <LangSwitcher L={L} compact onChange={(code) => savePrefs({ language: code })} />
          <button type="button" className={`btn ${easy ? "" : "ghost"} easy-toggle`} aria-pressed={easy} onClick={toggleEasy}>
            <span aria-hidden="true">Aa</span> {t("e.mode")}
          </button>
        </div>
      </div>

      <div className="banner rise d2">{t("common.notDx")}</div>
      {easySuggested && easy ? (
        <div className="banner info" role="status">
          {t("e.suggested")}
        </div>
      ) : null}
      {err ? (
        <div className="banner error" role="alert">
          {errorText(err, L)}
        </div>
      ) : null}
      {note ? (
        <div className="banner success" role="status">
          {note}
        </div>
      ) : null}

      <ol className="stepper rise d2" aria-label={t("p.progress")}>
        {STEP_KEYS.map((k, i) => {
          const status = i < at ? "done" : i === at ? "current" : "todo";
          return (
            <li key={k} className={status} aria-current={status === "current" ? "step" : undefined}>
              <span className="dot" aria-hidden>
                {status === "done" ? "✓" : L.num(i + 1)}
              </span>
              <span className="label">{t(k)}</span>
            </li>
          );
        })}
      </ol>

      {easy ? (
        <div className="easy-bar">
          <button type="button" className="btn secondary big" onClick={readScreen} aria-pressed={reading}>
            <span aria-hidden="true">{reading ? "■" : "🔊"}</span> {reading ? t("p.stopListening") : t("e.readAloud")}
          </button>
          <button type="button" className="btn big call" onClick={callMe} disabled={busy || !!c.evidence?.callback_requested}>
            <span aria-hidden="true">📞</span> {c.evidence?.callback_requested ? t("e.callRequested") : t("e.callMe")}
          </button>
        </div>
      ) : null}

      <div id="content" tabIndex={-1}>
        {easy ? (
          <div className="easy-step" data-read>
            <p className="step-count" aria-live="polite">
              {t("e.stepOf", { n: L.num(stepNow + 1), total: L.num(easySteps.length) })}
            </p>
            {easySteps[stepNow]}
            <div className="easy-nav">
              <button type="button" className="btn secondary big" disabled={stepNow === 0} onClick={() => setStep(stepNow - 1)}>
                <span aria-hidden="true" className="flip-rtl">
                  ←
                </span>{" "}
                {t("common.previous")}
              </button>
              <button type="button" className="btn big" disabled={stepNow >= easySteps.length - 1} onClick={() => setStep(stepNow + 1)}>
                {t("common.next")}{" "}
                <span aria-hidden="true" className="flip-rtl">
                  →
                </span>
              </button>
            </div>
          </div>
        ) : (
          <div className="stack" data-read>
            {resultSection}
            {teachSection}
            {apptSection || chooseSection}
            {claimSection}
            {closed ? <div className="banner success">{t("p.closedNote")}</div> : null}
            <details className="panel soft helper-details">
              <summary>{t("e.family")}</summary>
              {helperSection}
            </details>
          </div>
        )}
      </div>

      <footer className="patient-foot muted small">
        <span>{t("common.synthetic")}</span>
        <Link href="/">{t("common.back")}</Link>
      </footer>

      <PwaRegister label={t("common.install")} hint={t("common.installHint")} closeLabel={t("common.close")} />
      <ChatLauncher caseId={c.case_id} L={L} context={chatContext(c.state)} name={name} easy={easy} />
    </main>
  );
}

const PATIENT_CLAIM = ["documents_needed", "documents_ready", "submitted", "approved", "rejected", "paid"] as const;

function ReadAloud({ text, L }: { text: string; L: LocaleApi }) {
  const [on, setOn] = useState(false);
  const [noVoice, setNoVoice] = useState(false);
  const tr = useTranslated(text, L.lang);
  return (
    <div className="row-actions start">
      <button
        type="button"
        className="btn secondary btn-sm"
        aria-pressed={on}
        onClick={() => {
          if (on) {
            stopSpeaking();
            setOn(false);
            return;
          }
          const ok = speak(tr.text, tr.ai || L.lang === "en" || L.lang === "ar" ? L.meta.voice : "en-US", () => setOn(false));
          setNoVoice(!ok);
          setOn(ok);
        }}
      >
        <span aria-hidden>{on ? "■" : "🔊"}</span> {on ? L.t("p.stopListening") : L.t("p.listen")}
      </button>
      {noVoice ? (
        <p className="muted small" role="status">
          {L.t("p.noVoice")}
        </p>
      ) : null}
    </div>
  );
}
