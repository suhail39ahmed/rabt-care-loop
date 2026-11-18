"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { api } from "@/lib/api";
import { PATIENT_LOCALES, type LocaleApi, type Locale } from "@/lib/i18n";
import { canListen, listenOnce, speak, stopSpeaking } from "@/lib/speech";
import { LangSwitcher } from "./LangSwitcher";

export type ChatContext = "result" | "referral" | "booking" | "default";

type Citation = { id: string; title?: string };
type Reassurance = {
  answer: string;
  citations?: Citation[];
  hand_off?: boolean;
  hand_off_offered?: boolean;
  ai_generated?: boolean;
  gap?: boolean;
  method?: string;
  blocked_injection?: boolean;
  translation?: string;
  language?: string;
};
type Msg = {
  id: number;
  role: "user" | "assistant" | "system";
  text: string;
  lang: Locale;
  citations?: Citation[];
  blocked?: boolean;
  handoff?: boolean;
  ai?: boolean;
  translated?: boolean;
  englishOnly?: boolean;
};

const GREET_DELAY_MS = 2200;
const QUICK: Record<ChatContext, Array<"c.q.result1" | "c.q.result2" | "c.q.ref1" | "c.q.ref2" | "c.q.book1" | "c.q.book2">> = {
  result: ["c.q.result1", "c.q.result2"],
  referral: ["c.q.ref1", "c.q.ref2"],
  booking: ["c.q.book1", "c.q.book2"],
  default: ["c.q.result1", "c.q.ref2"],
};

function seenKey(caseId: string) {
  return `rabt.greet.${caseId}`;
}

function readSeen(caseId: string): { dismissed?: boolean; shown?: string[] } {
  try {
    return JSON.parse(window.localStorage.getItem(seenKey(caseId)) || "{}");
  } catch {
    return {};
  }
}

function writeSeen(caseId: string, v: { dismissed?: boolean; shown?: string[] }) {
  try {
    window.localStorage.setItem(seenKey(caseId), JSON.stringify(v));
  } catch {
    /* private mode */
  }
}

const Avatar = () => (
  <span className="chat-avatar" aria-hidden="true">
    <svg viewBox="0 0 32 32" width="22" height="22">
      <path d="M16 4c6.6 0 12 4.6 12 10.3 0 5.7-5.4 10.3-12 10.3-1.3 0-2.6-.2-3.8-.5L6 27l1.6-5.4C5.4 19.8 4 17.2 4 14.3 4 8.6 9.4 4 16 4z" fill="currentColor" />
      <circle cx="11.5" cy="14.5" r="1.6" fill="var(--paper, #fff)" />
      <circle cx="16" cy="14.5" r="1.6" fill="var(--paper, #fff)" />
      <circle cx="20.5" cy="14.5" r="1.6" fill="var(--paper, #fff)" />
    </svg>
  </span>
);

/**
 * Floating "ask Rabt" assistant: launcher button, proactive greeting, and a chat sheet (bottom sheet on phones,
 * floating card on desktop). Answers come only from the approved knowledge base; a coordinator reviews.
 */
export function ChatLauncher({
  caseId,
  L,
  context,
  name,
  easy = false,
}: {
  caseId: string;
  L: LocaleApi;
  context: ChatContext;
  name: string;
  easy?: boolean;
}) {
  const { t } = L;
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [typing, setTyping] = useState(false);
  const [unread, setUnread] = useState(0);
  const [greet, setGreet] = useState<ChatContext | null>(null);
  const [listening, setListening] = useState(false);
  const [handoffSent, setHandoffSent] = useState(false);
  const [speakingId, setSpeakingId] = useState<number | null>(null);
  const nextId = useRef(1);
  const fab = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const log = useRef<HTMLDivElement>(null);
  const titleId = useId();

  // Proactive greeting: once per case state, never again after the patient dismisses it.
  useEffect(() => {
    setGreet(null);
    const seen = readSeen(caseId);
    if (seen.dismissed || (seen.shown || []).includes(context)) return;
    const timer = window.setTimeout(() => {
      if (open) return;
      setGreet(context);
      setUnread((n) => Math.max(n, 1));
      writeSeen(caseId, { ...seen, shown: [...(seen.shown || []), context] });
    }, GREET_DELAY_MS);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, context]);

  const greetText = greet ? t(`c.greet.${greet}` as "c.greet.default", { name }) : "";

  const dismissGreeting = () => {
    setGreet(null);
    setUnread(0);
    writeSeen(caseId, { ...readSeen(caseId), dismissed: true });
  };

  const openChat = useCallback(() => {
    const g = greet || context;
    setMsgs((m) =>
      m.length ? m : [{ id: nextId.current++, role: "assistant", text: t(`c.greet.${g}` as "c.greet.default", { name }), lang: L.lang }]
    );
    setGreet(null);
    setOpen(true);
    setUnread(0);
  }, [greet, context, L.lang, name, t]);

  const close = useCallback(() => {
    setOpen(false);
    stopSpeaking();
    setSpeakingId(null);
    requestAnimationFrame(() => fab.current?.focus());
  }, []);

  useEffect(() => {
    if (!open) return;
    requestAnimationFrame(() => input.current?.focus());
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        close();
      }
      if (e.key === "Tab" && panel.current) {
        const f = panel.current.querySelectorAll<HTMLElement>("button:not([disabled]), textarea, select, a[href], input");
        if (!f.length) return;
        const first = f[0];
        const last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, close]);

  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" });
  }, [msgs, typing]);

  const ask = async (q: string) => {
    const question = q.trim();
    if (!question || typing) return;
    setText("");
    setMsgs((m) => [...m, { id: nextId.current++, role: "user", text: question, lang: L.lang }]);
    setTyping(true);
    try {
      const out = await api<{ reassurance?: Reassurance }>(`/cases/${caseId}/reassure`, {
        method: "POST",
        body: JSON.stringify({ question, language: L.lang }),
      });
      const r = out.reassurance;
      const blocked = !!r && (r.blocked_injection || r.method === "injection_rule");
      setMsgs((m) => [
        ...m,
        r
          ? {
              id: nextId.current++,
              role: "assistant",
              text: r.answer,
              lang: r.translation === "unavailable" ? "en" : (r.language as Locale) || L.lang,
              citations: r.citations,
              blocked,
              handoff: !!(r.hand_off || r.gap || r.hand_off_offered),
              ai: !!r.ai_generated,
              translated: !!r.translation && r.translation !== "unavailable",
              englishOnly: r.translation === "unavailable",
            }
          : { id: nextId.current++, role: "assistant", text: t("err.generic"), lang: L.lang, handoff: true },
      ]);
      if (!open) setUnread((n) => n + 1);
    } catch {
      setMsgs((m) => [...m, { id: nextId.current++, role: "system", text: t("err.network"), lang: L.lang }]);
    } finally {
      setTyping(false);
    }
  };

  const handoff = async () => {
    try {
      await api(`/cases/${caseId}/callback-request`, { method: "POST", body: JSON.stringify({ reason: "chat_handoff" }) });
      setHandoffSent(true);
      setMsgs((m) => [...m, { id: nextId.current++, role: "system", text: t("c.handoffSent"), lang: L.lang }]);
    } catch {
      setMsgs((m) => [...m, { id: nextId.current++, role: "system", text: t("err.generic"), lang: L.lang }]);
    }
  };

  const voice = async () => {
    if (listening) return;
    setListening(true);
    const { promise } = listenOnce(L.meta.voice);
    const said = await promise;
    setListening(false);
    if (said) await ask(said);
  };

  const readAloud = (m: Msg) => {
    if (speakingId === m.id) {
      stopSpeaking();
      setSpeakingId(null);
      return;
    }
    const meta = L.meta.code === m.lang ? L.meta : { voice: m.lang === "ar" ? "ar-AE" : m.lang === "en" ? "en-US" : L.meta.voice };
    if (speak(m.text, meta.voice, () => setSpeakingId(null))) setSpeakingId(m.id);
    else setMsgs((x) => [...x, { id: nextId.current++, role: "system", text: t("p.noVoice"), lang: L.lang }]);
  };

  return (
    <div className={`chat-root ${easy ? "easy" : ""}`}>
      {greet && !open ? (
        <div className="chat-greeting" role="status" aria-live="polite">
          <button type="button" className="greet-body" onClick={openChat}>
            {greetText}
          </button>
          <button type="button" className="greet-close" onClick={dismissGreeting} aria-label={t("c.dismiss")}>
            <span aria-hidden="true">×</span>
          </button>
        </div>
      ) : null}

      {!open ? (
        <button
          ref={fab}
          type="button"
          className="chat-fab"
          onClick={openChat}
          aria-label={unread ? `${t("c.open")} · ${t("c.unread", { n: L.num(unread) })}` : t("c.open")}
          aria-haspopup="dialog"
        >
          <Avatar />
          {unread ? (
            <span className="chat-badge" aria-hidden="true">
              {L.num(unread)}
            </span>
          ) : null}
        </button>
      ) : null}

      {open ? (
        <>
          <div className="chat-scrim" onClick={close} aria-hidden="true" />
          <div ref={panel} className="chat-panel" role="dialog" aria-modal="true" aria-labelledby={titleId}>
            <header className="chat-head">
              <Avatar />
              <div className="chat-title">
                <h2 id={titleId}>{t("c.title")}</h2>
                <p>{t("c.sub")}</p>
              </div>
              <LangSwitcher L={L} compact />
              <button type="button" className="icon-btn" onClick={close} aria-label={t("c.close")}>
                <span aria-hidden="true">×</span>
              </button>
            </header>

            <div ref={log} className="chat-log" role="log" aria-live="polite" aria-relevant="additions">
              <p className="chat-note">{t("c.welcome")}</p>
              {msgs.map((m) => (
                <div key={m.id} className={`bubble-row ${m.role}`}>
                  <div className={`bubble ${m.role} ${m.blocked ? "refusal" : ""}`} lang={m.lang} dir="auto">
                    <span className="sr-only">{m.role === "user" ? t("c.you") : t("c.assistant")}: </span>
                    {m.blocked ? <strong className="refusal-title">{t("c.blockedTitle")}</strong> : null}
                    <p>{m.text}</p>
                    {m.citations?.length ? (
                      <div className="cite-row" aria-label={t("c.sources")}>
                        {Array.from(new Map(m.citations.map((c) => [c.title || c.id, c])).values()).map((c) => (
                          <span key={c.id} className="cite-chip" data-src="record">
                            {c.title || c.id}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    {m.role === "assistant" ? (
                      <div className="bubble-tools">
                        {m.ai ? <span className="tag ai">{t("common.aiTag")}</span> : null}
                        {m.translated ? <span className="tag role">{t("common.aiTranslated")}</span> : null}
                        {m.englishOnly ? <span className="tag role">{t("c.englishOnly")}</span> : null}
                        <button type="button" className="mini-btn" onClick={() => readAloud(m)} aria-pressed={speakingId === m.id}>
                          <span aria-hidden="true">{speakingId === m.id ? "■" : "🔊"}</span> {speakingId === m.id ? t("p.stopListening") : t("p.listen")}
                        </button>
                        {m.handoff && !handoffSent ? (
                          <button type="button" className="mini-btn human" onClick={handoff}>
                            {t("c.talkPerson")}
                          </button>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                </div>
              ))}
              {typing ? (
                <div className="bubble-row assistant">
                  <div className="bubble assistant typing" role="status" aria-label={t("c.typing")}>
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              ) : null}
            </div>

            <div className="quick-row" role="group" aria-label={t("c.suggestions")}>
              {QUICK[context].map((k) => (
                <button key={k} type="button" className="quick-chip" disabled={typing} onClick={() => ask(t(k))}>
                  {t(k)}
                </button>
              ))}
              {!handoffSent ? (
                <button type="button" className="quick-chip human" onClick={handoff}>
                  {t("c.talkPerson")}
                </button>
              ) : null}
            </div>

            <form
              className="chat-input"
              onSubmit={(e) => {
                e.preventDefault();
                void ask(text);
              }}
            >
              <label htmlFor={`${titleId}-q`} className="sr-only">
                {t("c.placeholder")}
              </label>
              <textarea
                id={`${titleId}-q`}
                ref={input}
                rows={1}
                value={text}
                maxLength={500}
                dir="auto"
                placeholder={t("c.placeholder")}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void ask(text);
                  }
                }}
              />
              {canListen() ? (
                <button type="button" className={`icon-btn ${listening ? "on" : ""}`} onClick={voice} aria-label={listening ? t("c.listening") : t("c.voice")}>
                  <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
                    <path d="M12 15a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.9V21h2v-2.1A7 7 0 0 0 19 12z" fill="currentColor" />
                  </svg>
                </button>
              ) : null}
              <button type="submit" className="send-btn" disabled={typing || !text.trim()} aria-label={t("c.send")}>
                <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" className="flip-rtl">
                  <path d="M3 20.5 21 12 3 3.5 3 10l12 2-12 2z" fill="currentColor" />
                </svg>
              </button>
            </form>
          </div>
        </>
      ) : null}
    </div>
  );
}

export const CHAT_LOCALES = PATIENT_LOCALES;
