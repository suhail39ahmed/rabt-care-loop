# Assumptions and limitations

## Assumptions
- Prototype uses **synthetic data only** (no real patients, no Malaffi/Sehatna access).
- Triage thresholds and SLA clocks are **illustrative placeholders** pending clinician / DoH sign-off.
- Insurance plan and network names are **fictional**.
- Judges accept synthetic evaluation for scoring (per challenge Q&A).

## Limitations
- Local demo defaults to an in-memory/SQLite ledger; HAPI FHIR is optional via Docker.
- Azure OpenAI and Content Safety are optional locally; without them (or with `AI_ENABLED=false`), approved templates are used unchanged. On the Azure pilot they are wired through APIM → Foundry with `AI_ENABLED=true`.
- Arabic readability is not auto-scored.
- SNOMED usage (if Synthea later) is prototype-only; licence must be checked for production.
- Not a medical device; does not diagnose or prescribe.
