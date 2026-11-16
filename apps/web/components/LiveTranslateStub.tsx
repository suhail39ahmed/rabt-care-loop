"use client";

import { useState } from "react";

/** Simulated coordinator ↔ patient interpreter (#73). */
export function LiveTranslateStub() {
  const [src, setSrc] = useState("Please book your follow-up this week.");
  const dict: Record<string, string> = {
    "Please book your follow-up this week.": "يرجى حجز المتابعة هذا الأسبوع.",
    "هل يمكنك الحضور غداً؟": "Can you attend tomorrow?",
  };
  const out = dict[src] || `[AI-translated · simulated] ${src}`;
  return (
    <section className="panel soft" style={{ marginTop: "0.9rem" }}>
      <h2 style={{ fontFamily: "var(--font-display)", marginTop: 0 }}>Live translation (demo)</h2>
      <p className="muted">Simulated interpreter — not a real MT model. Output labelled AI-translated.</p>
      <textarea
        value={src}
        onChange={(e) => setSrc(e.target.value)}
        rows={3}
        style={{ width: "100%", padding: "0.75rem", borderRadius: "0.75rem", border: "1px solid var(--line)" }}
      />
      <p>
        <span className="tag ai">AI-translated</span> {out}
      </p>
    </section>
  );
}
