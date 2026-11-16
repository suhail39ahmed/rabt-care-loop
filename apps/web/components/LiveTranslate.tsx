"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Result = {
  text: string | null;
  method: "glossary" | "ai" | "unavailable" | "same_language" | "none";
  label: string | null;
  source_lang: "en" | "ar";
  target_lang: "en" | "ar";
  note?: string;
};

type Phrase = { en: string; ar: string };

/** Coordinator ↔ patient interpreter: approved phrases first, then the small model with PII kept local. */
export function LiveTranslate() {
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
      setOut(await api<Result>("/translate", { method: "POST", body: JSON.stringify({ text }) }));
    } catch {
      setErr("Translation service unavailable. Use an interpreter.");
      setOut(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel soft live-translate" aria-labelledby="lt-title">
      <h2 id="lt-title" className="section-title">Live translation</h2>
      <p className="muted small">
        English ↔ Arabic. Approved phrases are instant; anything else goes to the AI model with names, phones and IDs
        replaced before it leaves Rabt. Always check meaning with the patient.
      </p>
      {phrases.length > 0 && (
        <div className="chip-row" aria-label="Approved phrases">
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
              {p.en}
            </button>
          ))}
        </div>
      )}
      <label htmlFor="lt-src" className="sr-only">
        Message to translate
      </label>
      <textarea
        id="lt-src"
        className="field"
        value={src}
        dir="auto"
        onChange={(e) => setSrc(e.target.value)}
        rows={3}
        maxLength={2000}
      />
      <div className="row-actions">
        <button type="button" className="btn" onClick={() => run()} disabled={busy || !src.trim()}>
          {busy ? "Translating…" : "Translate"}
        </button>
      </div>
      <div aria-live="polite">
        {err && <p className="error-text">{err}</p>}
        {out && out.text && (
          <p className="translation" dir={out.target_lang === "ar" ? "rtl" : "ltr"} lang={out.target_lang}>
            <span className={`tag ${out.method === "ai" ? "ai" : "role"}`}>
              {out.label || (out.method === "same_language" ? "Same language" : "Translation")}
            </span>{" "}
            {out.text}
          </p>
        )}
        {out && !out.text && out.method === "unavailable" && <p className="muted">{out.note}</p>}
      </div>
    </section>
  );
}
