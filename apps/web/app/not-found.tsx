"use client";

import Link from "next/link";
import { STAFF_LOCALES, useLocale } from "@/lib/i18n";

export default function NotFound() {
  const { s } = useLocale({ allowed: STAFF_LOCALES });
  return (
    <main className="shell empty-page" style={{ textAlign: "center", paddingTop: "4rem" }}>
      <div className="brand-mark" style={{ justifyContent: "center" }}>
        <div className="mark" aria-hidden="true">
          ر
        </div>
        <div style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}>{s("Rabt")}</div>
      </div>
      <h1 style={{ fontFamily: "var(--font-display)" }}>{s("Page not found")}</h1>
      <p className="muted">{s("That route is not part of the demo — or the shared demo was reset.")}</p>
      <Link className="btn" href="/">
        {s("Back to demo home")}
      </Link>
    </main>
  );
}
