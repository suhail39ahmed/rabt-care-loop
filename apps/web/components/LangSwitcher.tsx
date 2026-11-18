"use client";

import { useId } from "react";
import { LOCALES, type LocaleApi, type Locale } from "@/lib/i18n";

const GLOBE = (
  <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="1.8" />
    <path d="M3 12h18M12 3c2.6 2.8 2.6 15.2 0 18M12 3c-2.6 2.8-2.6 15.2 0 18" fill="none" stroke="currentColor" strokeWidth="1.6" />
  </svg>
);

/** Language picker usable on every screen. Names are shown in their own script; the choice is saved for next time. */
export function LangSwitcher({ L, compact = false, onChange }: { L: LocaleApi; compact?: boolean; onChange?: (l: Locale) => void }) {
  const id = useId();
  const label = L.allowed.length > 2 ? L.t("common.language") : L.s("Language");
  const digitsLabel = L.allowed.length > 2 ? L.t("common.arabicDigits") : L.s("Arabic digits");
  return (
    <div className={`lang-switch ${compact ? "compact" : ""}`}>
      <label htmlFor={id} className="lang-label">
        {GLOBE}
        <span className={compact ? "sr-only" : ""}>{label}</span>
      </label>
      <select
        id={id}
        className="lang-select"
        value={L.lang}
        onChange={(e) => {
          const code = e.target.value as Locale;
          L.setLang(code);
          onChange?.(code);
        }}
      >
        {LOCALES.filter((l) => L.allowed.includes(l.code)).map((l) => (
          <option key={l.code} value={l.code} lang={l.code}>
            {l.name}
          </option>
        ))}
      </select>
      {L.lang === "ar" ? (
        <label className="digits-toggle">
          <input type="checkbox" checked={L.arabicDigits} onChange={(e) => L.setArabicDigits(e.target.checked)} />
          <span>{digitsLabel}</span>
        </label>
      ) : null}
    </div>
  );
}
