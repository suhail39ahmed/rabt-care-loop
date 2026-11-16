# Module 5 — Architecture bits (what we are building)

## Boxes (target)
```
Labs/FHIR → Events → Orchestrator (state machine + coordinator)
                         ├─ Deterministic agents
                         ├─ Optional LLM → OpenAI-compatible / Azure (AI_ENABLED kill switch)
                         ├─ Mock insurer A2A (Demo Health Insurance)
                         ├─ RAG mock / Azure IaC (off by default)
                         ├─ MCP tools (fhir / directory / messaging) — not on demo path
                         └─ HITL → Board
Patient app (Sehatna role) ←→ Orchestrator
Admin → KPIs, equity, leak funnel
```

## As-built today (local / Render)
- FastAPI + SQLite ledger  
- Next.js patient / board / admin (+ Judge mode on home)  
- Templates by default (`AI_ENABLED=false`)  
- LLM only if kill switch on + `LLM_*` / Azure env set  
- Terraform under `infra/terraform/` for AOAI, Search, APIM, Content Safety, Redis  

## Key docs
- `docs/architecture.md` — eventing today vs pilot  
- `docs/rag-azure.md` — RAG / gateway map  
- `docs/threat-model.md` — STRIDE → controls  
- `docs/pilot-plan.md` — 12-week pilot + cost sketch  
- `docs/agent-security.md` — OWASP-style agent hardening  

## Diagram files
- `learn/diagrams/diagram-agentic-workflow.png`  
- `learn/diagrams/diagram-agentic-delegation.png`  
- `learn/diagrams/diagram-hitl.png`  
- `docs/assets/architecture-hitl-concern-loop.png`  
- `docs/assets/architecture-eventing-today.png` / `…-pilot.png`  

## After this module
1. Walk **Judge mode** on `/`  
2. Quiz yourself with `learn/game-data.json` / `learn/assessment.json` (pass ≥ 80%)  
