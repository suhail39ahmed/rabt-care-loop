# Responsible AI

- **No-diagnosis boundary** — lexicon + Content Safety (when configured); patient banner on every card.
- **Deterministic safety path** — triage, escalation, SLA, closure never decided by an LLM.
- **Human gates** — critical escalation queue, teach-back failure callback, consent withdrawal, 4-eyes exceptional closure.
- **Consent** — withdrawing messaging consent pauses automation.
- **Audit** — provenance trail on every transition; timeline separates fact / calculated / AI.
- **Fairness** — KPI slices planned with small-cell suppression (benchmark path).
- **Failure modes** — LLM/Content Safety down → static templates; never auto-close on timeout.
- **Concerns and critical calls (planned, #86 #87)** — crisis / red-flag / refusal wording goes to a human before any AI reply; reassurance uses approved snippets only; a clinician, never AI alone, calls critical patients and logs the outcome; refusals are recorded as informed refusal, never forced closed.

Who can do what, and what each human input triggers: [hitl-playbook.md](hitl-playbook.md).

## Demo authentication (limitation)

The live demo uses **`X-Rabt-Persona`** on write routes and **`X-Rabt-Ingest-Secret`** for ingest/FHIR webhooks. Read-only guest access remains open for judges. Approver identity is taken from the persona header, not the request body.

This is **not** production IAM. The pilot plan is:

1. Microsoft Entra ID for clinician / coordinator roles.
2. UAE PASS (or programme IdP) for patient-facing consent and messaging preferences.
3. Short-lived tokens; no shared demo secrets in browser storage.

Until then, treat the public URL as a synthetic showcase on a single free-tier replica — **not** production IAM. Demo writes use role-checked personas (patient vs clinician); there is no per-IP rate limiter in this demo build.
