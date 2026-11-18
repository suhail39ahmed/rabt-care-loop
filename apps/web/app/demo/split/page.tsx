"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { LangSwitcher } from "@/components/LangSwitcher";
import { STAFF_LOCALES, useLocale } from "@/lib/i18n";

/** Recording layout: patient phone (left), coordinator board (right), insurer agent as a brief inset. */
function SplitDemo() {
  const search = useSearchParams();
  const L = useLocale({ allowed: STAFF_LOCALES });
  const { s } = L;
  const caseId = search.get("case") || "case-gc05-fit";
  const patientLang = search.get("plang") || "en";
  const [insurer, setInsurer] = useState(search.get("insurer") === "1");
  const [tracker, setTracker] = useState(search.get("tracker") === "1");
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (el && /input|textarea|select/i.test(el.tagName)) return;
      if (e.key.toLowerCase() === "i") setInsurer((v) => !v);
      if (e.key.toLowerCase() === "t") setTracker((v) => !v);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <main className="split">
      <div className="split-head">
        <div className="brand-mark">
          <div className="mark" aria-hidden="true">
            ر
          </div>
          <div>
            <h1 style={{ fontFamily: "var(--font-display)", fontSize: "1.05rem", margin: 0 }}>{s("Split-screen demo")}</h1>
            <div className="muted small">{s("patient phone and coordinator board side by side, live")}</div>
          </div>
        </div>
        <div className="actions" style={{ marginTop: 0 }}>
          <button type="button" className={`btn ${insurer ? "" : "secondary"}`} aria-pressed={insurer} onClick={() => setInsurer((v) => !v)}>
            {insurer ? s("Hide insurer") : s("Show insurer")}
          </button>
          <button type="button" className={`btn ${tracker ? "" : "secondary"}`} aria-pressed={tracker} onClick={() => setTracker((v) => !v)}>
            {tracker ? s("Hide tracker") : s("Show tracker")}
          </button>
          <button type="button" className="btn secondary" onClick={() => setNonce((n) => n + 1)}>
            {s("Refresh")}
          </button>
          <Link className="btn ghost" href="/">
            {s("Demo home")}
          </Link>
          <LangSwitcher L={L} compact />
        </div>
      </div>
      <div className="phone-frame">
        <iframe key={`p${nonce}`} title={s("Patient view")} src={`/patient/${caseId}?lang=${patientLang}`} />
      </div>
      <div className="desk-frame">
        <div className="bar" aria-hidden="true">
          <i />
          <i />
          <i />
        </div>
        <iframe
          key={`b${nonce}-${tracker ? "t" : "c"}`}
          title={s("Rabt board")}
          src={`/board?focus=${caseId}${tracker ? "&view=tracker" : ""}`}
        />
        <div className={`inset ${insurer ? "" : "hidden"}`} aria-hidden={!insurer}>
          <span className="tag role label">{s("Insurer agent (A2A)")}</span>
          <iframe title={s("Insurer agent (A2A)")} src="/insurer" tabIndex={insurer ? 0 : -1} />
        </div>
      </div>
    </main>
  );
}

export default function SplitDemoPage() {
  return (
    <Suspense fallback={null}>
      <SplitDemo />
    </Suspense>
  );
}
