# Hack2Skill form text (match shipped build)

Deadline: 20 Nov 2026, 11:59 PM IST. Canonical safety wording: [submission-claims.md](submission-claims.md).

## Prototype / deployment link

https://rabt-web.onrender.com

API: https://rabt-api-9oig.onrender.com · Repo: https://github.com/suhail39ahmed/rabt-care-loop

## What was built

Rabt is a FHIR-native care-loop orchestrator for Abu Dhabi-style screening follow-up. Every abnormal result gets an owner, an in-network next step, teach-back, and documented closure with two-person approval when evidence is incomplete. Humans stay on the safety path (escalation ladder, HITL queue). Live demo on Render (free tier, Oregon; cold start ~15–20 s). Synthetic data only.

Automated tests: full pytest suite in CI (orchestrator, golden **10/10**, safety). Web build + Playwright smoke/story e2e. Next.js 16 on the web app.

## Not in progress (already shipped)

Two-person closure, multi-step escalation timer + demo clock, golden 10/10, simulated benchmark, cloud deploy on Render, demo auth headers, CI jobs.

## Honest next / optional

- Azure AI Content Safety and LLM rewrite are **optional and off** in the live demo; lexicon guardrails always on (`GET /healthz`).
- MCP tool servers are a **prototype**, not on the demo path.
- Deck PDF export and any video re-record for post-P0 behaviour (attend → outcome → close).

## Contact / video

- Video: https://youtu.be/Qe9OF5uIzyg
- Deck: attach exported `Rabt_Deck.pdf` (< 5 MB) once slides are updated (no TBD / “in progress” / confirm placeholders).
