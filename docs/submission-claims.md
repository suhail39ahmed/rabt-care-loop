# Canonical claims (live demo)

Use this wording in the deck, Hack2Skill form, and README so every statement matches https://rabt-web.onrender.com.

## Content Safety

- **Lexicon guardrails** (no-diagnosis phrases, number grounding, PII scrub) always run on templates.
- **Azure AI Content Safety** is optional. It is **off in the live Render demo** unless `CONTENT_SAFETY_ENDPOINT` (and credentials) are configured.
- Check `GET /healthz` → `content_safety: false|true` and `llm: false|true`.

## MCP

- MCP tool servers under `mcp-servers/` are a **prototype** with the same tool-scope checks as the orchestrator.
- They are **not on the live demo path**. The demo uses the FastAPI coordinator directly.

## Tests / golden

- Prefer the CI / local pytest count over stale form text.
- Golden cases: 10/10 (see `benchmark/reports/`).

## Hosting

- Live web: https://rabt-web.onrender.com  
- Live API: https://rabt-api-9oig.onrender.com (`/`, `/healthz`, `/docs`)  
- Render free tier (Oregon): cold start ~15–20 s; shared SQLite reseeds on restart.
