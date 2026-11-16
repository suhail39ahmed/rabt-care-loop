# Module 1 — What are we building?

## In one sentence
**Rabt** (ربط = binding/connection) is an AI care-loop layer: every actionable screening result gets an **owner**, a **next step**, and **documented closure**.

## The problem (Abu Dhabi / ADPHC)
Screening finds a result, but the loop leaks:
- Who owns the next step across facilities?
- Does insurance / network affect where the patient can go?
- Did the patient understand?
- Was care completed — with evidence?

Reminders alone are not enough. Rabt adds ownership handshake, insurance-aware routing (including a **Demo Health Insurance** A2A mock), teach-back, concern listening, expert call on CRITICAL, and evidence-gated closure.

## What Rabt is *not*
- Not an EMR replacement  
- Not Malaffi or Sehatna (it plugs in beside them)  
- Not a diagnostic chatbot  
- Not LangChain  

## Pieces you will touch in code

| Piece | Role |
|---|---|
| `state_machine.py` | Legal case states |
| `coordinator.py` | Supervisor that delegates |
| `services/agents/*` | Specialist agents (triage, comms, intent, …) |
| `hitl.py` | Human gates + queue resolve |
| `insurer.py` | Mock A2A coverage / preauth / cost |
| `apps/web` | Patient + board + admin |
| Optional LLM | `AI_ENABLED` + `LLM_*` via `llm_client.py` (off by default) |

## Mental picture
```
Lab result → Rabt case → Owner accepts → Patient understands → Book in-network → Attend → Close with evidence
                 ↑                              ↑
            deterministic                   HITL if stuck
                 │
                 └─ CRITICAL → expert call outcome required before handle
```

## Honest AI story
Templates run without cloud keys. Violet timeline = **AI-generated only when an LLM ran**. Keyword reassurance is **calculated**, not AI.
