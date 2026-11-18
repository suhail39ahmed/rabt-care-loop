"use client";

import { useEffect, useState } from "react";
import { api } from "./api";
import type { Locale } from "./i18n";

/** Languages the server writes content in (result cards, guides, clinic rationale). */
const NATIVE: Locale[] = ["en", "ar"];
const cache = new Map<string, string | null>();
const inflight = new Map<string, Promise<string | null>>();
const STORE = "rabt.tx.v1";

function load() {
  if (cache.size || typeof window === "undefined") return;
  try {
    const raw = window.sessionStorage.getItem(STORE);
    if (raw) Object.entries(JSON.parse(raw) as Record<string, string>).forEach(([k, v]) => cache.set(k, v));
  } catch {
    /* ignore */
  }
}

function save() {
  try {
    const obj: Record<string, string> = {};
    cache.forEach((v, k) => {
      if (v) obj[k] = v;
    });
    window.sessionStorage.setItem(STORE, JSON.stringify(obj));
  } catch {
    /* quota */
  }
}

/** Translate server text into a patient language through Rabt's translation layer (PII is kept local server-side). */
export async function translateText(text: string, target: Locale): Promise<string | null> {
  if (!text.trim() || NATIVE.includes(target)) return text;
  load();
  const key = `${target}\u0000${text}`;
  if (cache.has(key)) return cache.get(key) ?? null;
  if (!inflight.has(key)) {
    inflight.set(
      key,
      api<{ text: string | null; method: string }>("/translate", { method: "POST", body: JSON.stringify({ text, target }) })
        .then((r) => (r.method === "unavailable" ? null : r.text))
        .catch(() => null)
        .then((out) => {
          cache.set(key, out);
          inflight.delete(key);
          save();
          return out;
        })
    );
  }
  return inflight.get(key)!;
}

export type Translated = { text: string; ai: boolean; pending: boolean; failed: boolean };

/**
 * Show server-written English text in the chosen language. EN/AR are served natively; other languages
 * are translated on demand and labelled as AI-translated, falling back to English when translation fails.
 */
export function useTranslated(text: string | null | undefined, lang: Locale): Translated {
  const src = text || "";
  const needs = !!src && !NATIVE.includes(lang);
  const [state, setState] = useState<Translated>({ text: src, ai: false, pending: needs, failed: false });
  useEffect(() => {
    if (!needs) {
      setState({ text: src, ai: false, pending: false, failed: false });
      return;
    }
    let live = true;
    setState({ text: src, ai: false, pending: true, failed: false });
    translateText(src, lang).then((out) => {
      if (!live) return;
      setState(out ? { text: out, ai: true, pending: false, failed: false } : { text: src, ai: false, pending: false, failed: true });
    });
    return () => {
      live = false;
    };
  }, [src, lang, needs]);
  return state;
}
