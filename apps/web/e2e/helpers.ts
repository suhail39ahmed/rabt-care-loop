import type { Page } from "@playwright/test";
import { PATIENT } from "../lib/dict/patient";

export const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
export const PATIENT_LOCALES = ["en", "ar", "hi", "ur", "ml", "tl", "bn"] as const;
export const RTL = ["ar", "ur"];
export const LATIN = ["tl"];

/** Words allowed in any locale: product name, lab codes, units, people and place names from the synthetic seed. */
const ALLOWED =
  /^(Rabt|HbA|HbA1c|FIT|AED|HMAC|HTTPS|FHIR|APIM|SMS|PDF|LDL|eGFR|mmHg|Sehatna|WhatsApp|Azure|HITL|DoH|KPIs?|LLM|A2A|Fatima|Ravi|Omar|Saeed|Aisha|Sara|Mariam|Joel|Khan|Filipino|English)$/i;

/**
 * Visible UI text that still contains English words in a non-English locale. Server records
 * (names, clinic names, case ids, timeline entries) are marked data-src="record" or lang="en" and skipped.
 */
export async function untranslated(page: Page, lang?: string): Promise<{ total: number; hits: string[] }> {
  // Latin-script locales (tl) share the alphabet with English, so there a hit is UI text that is still an English
  // dictionary string (with its {placeholders} as wildcards) instead of "contains any English-looking word".
  const english =
    lang && LATIN.includes(lang)
      ? Object.entries(PATIENT.en)
          .filter(([k, v]) => v.length > 3 && PATIENT[lang as keyof typeof PATIENT][k as keyof typeof PATIENT.en] !== v)
          .map(([, v]) => v)
      : null;
  return page.evaluate(([allowed, english]) => {
    const ok = new RegExp(allowed as string, "i");
    const skip = (el: Element) =>
      el.closest('[data-src="record"],script,style,noscript,[translate="no"],[lang="en"],option,code,pre,bdi,[aria-hidden="true"]');
    const hits: string[] = [];
    let total = 0;
    const esc = (v: string) => v.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\\\{\w+\\\}/g, ".+");
    const en = english ? english.map((v) => new RegExp(`^${esc(v.replace(/\s+/g, " ").trim())}$`, "i")) : null;
    const words = (t: string) =>
      en ? (en.some((r) => r.test(t)) ? [t] : []) : (t.match(/[A-Za-z][A-Za-z'’-]{2,}/g) || []).filter((w) => !ok.test(w));
    const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n: Node | null;
    while ((n = tw.nextNode())) {
      const t = (n.textContent || "").replace(/\s+/g, " ").trim();
      const el = n.parentElement;
      if (!t || !/\p{L}/u.test(t) || !el || skip(el)) continue;
      const st = getComputedStyle(el);
      if (st.display === "none" || st.visibility === "hidden") continue;
      total++;
      if (words(t).length) hits.push(t.slice(0, 90));
    }
    document.querySelectorAll("[aria-label],[title],[placeholder],[alt]").forEach((el) => {
      if (skip(el)) return;
      for (const a of ["aria-label", "title", "placeholder", "alt"]) {
        const v = el.getAttribute(a);
        if (!v) continue;
        total++;
        if (words(v).length) hits.push(`@${a}: ${v.slice(0, 80)}`);
      }
    });
    return { total, hits: [...new Set(hits)] };
  }, [ALLOWED.source, english] as const);
}

export async function resetDemo(request: import("@playwright/test").APIRequestContext) {
  const r = await request.post(`${API}/demo/reset`, { headers: { "X-Rabt-Persona": "human:coordinator-sara" } });
  if (!r.ok()) throw new Error(`demo reset failed: ${r.status()}`);
}
