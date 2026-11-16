# Module 6 — What Rabt adds (full deep dive)

For each capability: **what it is → how we tackle it → technology → scripts → how it resolves.**

| # | Feature | Primary scripts |
|---|---|---|
| F1 | Result intake + deterministic triage | `triage/engine.py`, `rules/v1.yaml`, `coordinator.open_from_observation` |
| F2 | Ownership handshake | `ownership/assign.py`, `accept_ownership` |
| F3 | Insurance-aware navigator + A2A mock | `navigator/scoring.py`, `insurer.py`, `services/insurer_demo/` |
| F4 | AR/EN result card + teach-back (+ i18n snippets) | `comms/agent.py`, `data/templates/*`, `data/templates/i18n/` |
| F5 | Guardrailed reassurance (+ injection deny-list) | `reassurance/agent.py`, `injection.py`, `data/kb/*` |
| F6 | Escalation ladder + expert call | `escalation/ladder.py`, `log_call_outcome`, `data/scripts/expert_call_critical_en.md` |
| F7 | Evidence-gated closure | `closure/verifier.py`, `try_close`, evidence pack FHIR Bundle |
| F8 | Audit trail fact/calculated/AI (honest labels) | `ledger.py`, `_apply` (AI only if `ai_generated`) |
| F9 | Concern + intent classify | `agents/intent/classify.py`, `POST /cases/{id}/concern` |
| F10 | Admin impact + equity | `kpis.py`, `/benchmark/fairness`, `/admin` |
| F11 | Optional LLM + kill switch | `llm_client.py`, `AI_ENABLED`, `/healthz` |
| F12 | RAG / AI platform scaffold | `docs/rag-azure.md`, `rag/mock_retrieve.py`, Terraform |

See also **Module 7** for what shipped in the latest stack.
