"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { LOCALES, STAFF_LOCALES, type Locale, useLocale } from "@/lib/i18n";

type Result = {
  text: string | null;
  method: "glossary" | "ai" | "unavailable" | "same_language" | "none";
  label: string | null;
  source_lang: string;
  target_lang: string;
  note?: string;
};

type Phrase = { en: string; ar: string };

/** Coordinator ↔ patient interpreter: approved phrases first, then the small model with PII kept local. */
export function LiveTranslate() {
  const L = useLocale({ allowed: STAFF_LOCALES });
  const { s } = L;
  const [target, setTarget] = useState<Locale | "auto">("auto");
  const [src, setSrc] = useState("Please book your follow-up this week.");
  const [out, setOut] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [phrases, setPhrases] = useState<Phrase[]>([]);

  useEffect(() => {
    api<{ phrases: Phrase[] }>("/translate/glossary")
      .then((r) => setPhrases(r.phrases))
      .catch(() => setPhrases([]));
  }, []);

  async function run(text = src) {
    if (!text.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      setOut(await api<Result>("/translate", { method: "POST", body: JSON.stringify(target === "auto" ? { text } : { text, target }) }));
    } catch {
      setErr(s("Translation service unavailable. Use an interpreter."));
      setOut(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel soft live-translate" aria-labelledby="lt-title">
      <h2 id="lt-title" className="section-title">{s("Live translation")}</h2>
      <p className="muted small">
        {s(
          "English ↔ Arabic, Hindi, Urdu, Malayalam, Filipino and Bengali. Approved phrases are instant; anything else goes to the AI model with names, phones and IDs replaced before it leaves Rabt. Always check meaning with the patient."
        )}
      </p>
      {phrases.length > 0 && (
        <div className="chip-row" aria-label={s("Approved phrases")}>
          {phrases.slice(0, 4).map((p) => (
            <button
              key={p.en}
              type="button"
              className="chip"
              onClick={() => {
                setSrc(p.en);
                void run(p.en);
              }}
            >
              <span data-src="record" lang="en">
                {p.en}
              </span>
            </button>
          ))}
        </div>
      )}
      <label htmlFor="lt-src" className="sr-only">
        {s("Message to translate")}
      </label>
      <textarea
        id="lt-src"
        className="field"
        data-src="record"
        value={src}
        dir="auto"
        onChange={(e) => setSrc(e.target.value)}
        rows={3}
        maxLength={2000}
      />
      <div className="row-actions">
        <label className="small muted">
          {s("Target language")}{" "}
          <select className="field inline" value={target} onChange={(e) => setTarget(e.target.value as Locale | "auto")}>
            <option value="auto">{s("Auto (English ↔ Arabic)")}</option>
            {LOCALES.map((l) => (
              <option key={l.code} value={l.code} lang={l.code}>
                {l.name}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="btn" onClick={() => run()} disabled={busy || !src.trim()}>
          {busy ? s("Translating…") : s("Translate")}
        </button>
      </div>
      <div aria-live="polite">
        {err && <p className="error-text">{err}</p>}
        {out && out.text && (
          <p className="translation" dir={out.target_lang === "ar" || out.target_lang === "ur" ? "rtl" : "ltr"} lang={out.target_lang} data-src="record">
            <span className={`tag ${out.method === "ai" ? "ai" : "role"}`}>
              {out.method === "ai" ? s("AI-translated") : out.method === "same_language" ? s("Same language") : s("Approved phrase")}
            </span>{" "}
            {out.text}
          </p>
        )}
        {out && !out.text && out.method === "unavailable" && <p className="muted">{s("Translation service unavailable. Use an interpreter.")}</p>}
      </div>
    </section>
  );
}
