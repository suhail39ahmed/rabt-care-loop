# Threat model (STRIDE) (#67)

Assets: screening results, patient messages, closure decisions, insurer exchanges.  
Actors: patient (demo), clinician, coordinator, optional LLM/APIM, mock insurer.

| Threat | Example | Control in code | Status |
|---|---|---|---|
| Spoofing | Fake persona | `X-Rabt-Persona` allowlist (`auth.py`) | Demo only |
| Tampering | Alter closure | Ledger provenance + 4-eyes (`hitl.py`) | Shipped |
| Repudiation | Deny approval | Approval votes table | Shipped |
| Info disclosure | PII to LLM | Regex `scrub_pii` / `scrub_pii_uae`, then Azure AI Language PII (bare names, addresses; fails closed); kill switch | Shipped |
| DoS | Agent loops | `MAX_STEPS`, tool scopes | Shipped |
| Elevation | Patient closes cases | Role matrix `write_role_allowed` | Shipped |
| Spoofing (ingest) | Fake FHIR | `RABT_INGEST_SECRET` | Shipped |
| Tampering (insurer) | Free-text instructions | Allowlisted insurer fields | Shipped |
| Injection | Prompt injection | `injection.py` deny-list | Shipped |

**Pilot (not demo):** Entra ID / UAE PASS, encryption at rest, rate limits, private network.

**Residual risks:** shared demo DB resets; demo personas are not authentication.
