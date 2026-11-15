# Responsible AI

- **No-diagnosis boundary** — lexicon + Content Safety (when configured); patient banner on every card.
- **Deterministic safety path** — triage, escalation, SLA, closure never decided by an LLM.
- **Human gates** — critical escalation queue, teach-back failure callback, consent withdrawal, 4-eyes exceptional closure.
- **Consent** — withdrawing messaging consent pauses automation.
- **Audit** — provenance trail on every transition; timeline separates fact / calculated / AI.
- **Fairness** — KPI slices planned with small-cell suppression (benchmark path).
- **Failure modes** — LLM/Content Safety down → static templates; never auto-close on timeout.
