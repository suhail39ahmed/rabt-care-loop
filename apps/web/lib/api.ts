const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let activePersona = "human:coordinator-sara";

export function setApiPersona(persona: string) {
  activePersona = persona;
}

export function getApiPersona() {
  return activePersona;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method || "GET").toUpperCase();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (method !== "GET" && method !== "HEAD") {
    headers["X-Rabt-Persona"] = headers["X-Rabt-Persona"] || activePersona;
  }
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export { API };
