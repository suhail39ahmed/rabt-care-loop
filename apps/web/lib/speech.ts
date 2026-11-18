"use client";

/** Read text aloud with the device voice for the chosen language. Returns false when no voice is available. */
export function speak(text: string, bcp47: string, onEnd?: () => void): boolean {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return false;
  const synth = window.speechSynthesis;
  const base = bcp47.toLowerCase().split("-")[0];
  const voices = synth.getVoices();
  const voice = voices.find((v) => v.lang.toLowerCase() === bcp47.toLowerCase()) || voices.find((v) => v.lang.toLowerCase().startsWith(base));
  if (voices.length && !voice) return false;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = bcp47;
  if (voice) u.voice = voice;
  u.rate = 0.92;
  if (onEnd) u.onend = onEnd;
  synth.cancel();
  synth.speak(u);
  return true;
}

export function stopSpeaking() {
  if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
}

type Recognizer = {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
};

export function canListen(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as unknown as { SpeechRecognition?: unknown; webkitSpeechRecognition?: unknown };
  return !!(w.SpeechRecognition || w.webkitSpeechRecognition);
}

/** One-shot voice input; resolves with the transcript (empty when nothing was heard). */
export function listenOnce(bcp47: string): { promise: Promise<string>; stop: () => void } {
  const w = window as unknown as { SpeechRecognition?: new () => Recognizer; webkitSpeechRecognition?: new () => Recognizer };
  const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
  if (!Ctor) return { promise: Promise.resolve(""), stop: () => undefined };
  const r = new Ctor();
  r.lang = bcp47;
  r.interimResults = false;
  r.maxAlternatives = 1;
  const promise = new Promise<string>((resolve) => {
    let said = "";
    r.onresult = (e) => {
      said = e.results[0]?.[0]?.transcript || "";
    };
    r.onend = () => resolve(said);
    r.onerror = () => resolve("");
  });
  r.start();
  return { promise, stop: () => r.stop() };
}
