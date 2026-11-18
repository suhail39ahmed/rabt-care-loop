"use client";

import { useEffect, useState } from "react";

type InstallEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: "accepted" | "dismissed" }> };

/** Registers the service worker and offers "Install app" when the browser allows it. */
export function PwaRegister({ label, hint, closeLabel }: { label: string; hint: string; closeLabel: string }) {
  const [evt, setEvt] = useState<InstallEvent | null>(null);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    if ("serviceWorker" in navigator && window.isSecureContext) {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => undefined);
    }
    try {
      setHidden(window.localStorage.getItem("rabt.install.dismissed") === "1");
    } catch {
      /* ignore */
    }
    const onPrompt = (e: Event) => {
      e.preventDefault();
      setEvt(e as InstallEvent);
    };
    const onInstalled = () => setEvt(null);
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  if (!evt || hidden) return null;
  return (
    <div className="install-bar" role="region" aria-label={label}>
      <img src="/icons/icon-192.png" alt="" width={36} height={36} />
      <span>{hint}</span>
      <button
        type="button"
        className="btn btn-sm"
        onClick={async () => {
          await evt.prompt();
          await evt.userChoice.catch(() => undefined);
          setEvt(null);
        }}
      >
        {label}
      </button>
      <button
        type="button"
        className="icon-btn"
        aria-label={closeLabel}
        onClick={() => {
          setHidden(true);
          try {
            window.localStorage.setItem("rabt.install.dismissed", "1");
          } catch {
            /* ignore */
          }
        }}
      >
        <span aria-hidden="true">×</span>
      </button>
    </div>
  );
}
