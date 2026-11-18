"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { PATIENT, type PatientKey } from "./dict/patient";
import { STAFF } from "./dict/staff";

export const LOCALES = [
  { code: "en", name: "English", dir: "ltr", bcp47: "en-AE", voice: "en-US" },
  { code: "ar", name: "العربية", dir: "rtl", bcp47: "ar-AE", voice: "ar-AE" },
  { code: "hi", name: "हिन्दी", dir: "ltr", bcp47: "hi-IN", voice: "hi-IN" },
  { code: "ur", name: "اردو", dir: "rtl", bcp47: "ur-PK", voice: "ur-PK" },
  { code: "ml", name: "മലയാളം", dir: "ltr", bcp47: "ml-IN", voice: "ml-IN" },
  { code: "tl", name: "Filipino", dir: "ltr", bcp47: "fil-PH", voice: "fil-PH" },
  { code: "bn", name: "বাংলা", dir: "ltr", bcp47: "bn-BD", voice: "bn-BD" },
] as const;

export type Locale = (typeof LOCALES)[number]["code"];
export const PATIENT_LOCALES: Locale[] = LOCALES.map((l) => l.code);
/** Staff screens (board, admin, insurer) are offered in the two working languages of Abu Dhabi clinics. */
export const STAFF_LOCALES: Locale[] = ["en", "ar"];
export const KB_LOCALES: Locale[] = ["en", "ar"];

const STORE = "rabt.lang";
const EVENT = "rabt:lang";
const DIGITS = "rabt.arabicDigits";

export function localeMeta(code: string) {
  return LOCALES.find((l) => l.code === code) || LOCALES[0];
}

export function isLocale(x: string | null | undefined, allowed: Locale[] = PATIENT_LOCALES): x is Locale {
  return !!x && (allowed as string[]).includes(x);
}

/** Patients and staff keep separate choices, so a patient picking Hindi never flips the coordinator board. */
type Scope = "patient" | "staff";
const scopeOf = (allowed: Locale[]): Scope => (allowed.length > STAFF_LOCALES.length ? "patient" : "staff");
const storeKey = (scope: Scope) => (scope === "patient" ? STORE : `${STORE}.staff`);
const cookieKey = (scope: Scope) => (scope === "patient" ? "rabt_lang" : "rabt_staff_lang");

function readStored(scope: Scope): string | null {
  if (typeof window === "undefined") return null;
  try {
    const m = document.cookie.match(new RegExp(`(?:^|; )${cookieKey(scope)}=([a-z]{2})`));
    return window.localStorage.getItem(storeKey(scope)) || m?.[1] || null;
  } catch {
    return null;
  }
}

export function storeLocale(code: Locale, scope: Scope = "patient") {
  try {
    window.localStorage.setItem(storeKey(scope), code);
    document.cookie = `${cookieKey(scope)}=${code}; path=/; max-age=31536000; samesite=lax`;
  } catch {
    /* private mode */
  }
  try {
    window.dispatchEvent(new CustomEvent(EVENT, { detail: { code, scope } }));
  } catch {
    /* old browsers */
  }
}

type Vars = Record<string, string | number>;

function fill(s: string, vars?: Vars) {
  if (!vars) return s;
  return s.replace(/\{(\w+)\}/g, (_, k) => (k in vars ? String(vars[k]) : `{${k}}`));
}

/**
 * Locale for a screen: ?lang= wins, then the saved choice, then `fallback`. Sets <html lang/dir> and the title.
 * `allowed` limits staff screens to EN/AR.
 */
export function useLocale(opts: { allowed?: Locale[]; fallback?: Locale; initial?: string | null } = {}) {
  const allowed = opts.allowed || PATIENT_LOCALES;
  const scope = scopeOf(allowed);
  const pick = (): Locale => {
    if (isLocale(opts.initial, allowed)) return opts.initial;
    const s = readStored(scope);
    if (isLocale(s, allowed)) return s;
    return opts.fallback && allowed.includes(opts.fallback) ? opts.fallback : "en";
  };
  const [lang, setLangState] = useState<Locale>(() => (isLocale(opts.initial, allowed) ? opts.initial : opts.fallback || "en"));
  const [arabicDigits, setArabicDigitsState] = useState(false);

  useEffect(() => {
    setLangState(pick());
    try {
      setArabicDigitsState(window.localStorage.getItem(DIGITS) === "1");
    } catch {
      /* ignore */
    }
    const onChange = (e: Event) => {
      const d = (e as CustomEvent<{ code: string; scope: Scope }>).detail;
      if (d?.scope === scope && isLocale(d.code, allowed)) setLangState(d.code);
    };
    const onDigits = () => {
      try {
        setArabicDigitsState(window.localStorage.getItem(DIGITS) === "1");
      } catch {
        /* ignore */
      }
    };
    window.addEventListener(EVENT, onChange);
    window.addEventListener("rabt:digits", onDigits);
    return () => {
      window.removeEventListener(EVENT, onChange);
      window.removeEventListener("rabt:digits", onDigits);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opts.initial]);

  const meta = localeMeta(lang);
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = meta.dir;
  }, [lang, meta.dir]);

  const setLang = useCallback((code: Locale) => {
    storeLocale(code, scope);
    setLangState(code);
    const url = new URL(window.location.href);
    url.searchParams.set("lang", code);
    window.history.replaceState(null, "", url.toString());
  }, [scope]);

  const setArabicDigits = useCallback((on: boolean) => {
    setArabicDigitsState(on);
    try {
      window.localStorage.setItem(DIGITS, on ? "1" : "0");
      window.dispatchEvent(new Event("rabt:digits"));
    } catch {
      /* ignore */
    }
  }, []);

  const numLocale = lang === "ar" ? (arabicDigits ? "ar-AE-u-nu-arab" : "ar-AE-u-nu-latn") : meta.bcp47;
  const num = useCallback((n: number, o?: Intl.NumberFormatOptions) => new Intl.NumberFormat(numLocale, o).format(n), [numLocale]);
  const date = useCallback(
    (d: Date | number, o: Intl.DateTimeFormatOptions = { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) =>
      new Intl.DateTimeFormat(numLocale, o).format(typeof d === "number" ? new Date(d) : d),
    [numLocale]
  );
  /** Replace ASCII digits inside a server string when Arabic digits are on. */
  const digits = useCallback(
    (s: string) => (lang === "ar" && arabicDigits ? s.replace(/[0-9]/g, (d) => "٠١٢٣٤٥٦٧٨٩"[Number(d)]) : s),
    [lang, arabicDigits]
  );

  const t = useCallback(
    (key: PatientKey, vars?: Vars) => fill((PATIENT[lang] as Record<string, string>)[key] ?? PATIENT.en[key], vars),
    [lang]
  );
  /** Staff text is keyed by its English source, so an unknown key still renders (and the i18n audit flags it). */
  const s = useCallback(
    (key: string, vars?: Vars) => {
      const table = (STAFF as Record<string, Record<string, string>>)[lang] || STAFF.en;
      return fill(table[key] ?? key, vars);
    },
    [lang]
  );

  return useMemo(
    () => ({ lang, setLang, dir: meta.dir, rtl: meta.dir === "rtl", meta, t, s, num, date, digits, arabicDigits, setArabicDigits, allowed }),
    [lang, setLang, meta, t, s, num, date, digits, arabicDigits, setArabicDigits, allowed]
  );
}

export type LocaleApi = ReturnType<typeof useLocale>;
