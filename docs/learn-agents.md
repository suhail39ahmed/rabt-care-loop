# Learn: HITL, agentic workflow, agent delegation in Rabt

## Mental model

```text
Event/API
   │
   ▼
Coordinator (supervisor)  ──delegates──►  Specialist agents
   │                                            │
   │◄──── DelegationResult (typed) ─────────────┘
   │
   ▼
state_machine.transition()  →  ledger + timeline (fact | calculated | AI*)
   │                              * AI only if LLM ran
   └── if unsafe / unknown / consent / 4-eyes / concern / expert-call
                                                      │
                                                      ▼
                                                   Board UI (human)
```

## Where in the repo

| Concept | Files |
|---|---|
| **Agentic workflow** | `services/orchestrator/app/state_machine.py`, `coordinator.py` |
| **Agent delegation** | `contracts.py` + `services/agents/*/` + `Coordinator._apply` |
| **Human-in-the-loop** | `hitl.py`, board queue / call / consent / callback |
| **Honest AI labels** | `_apply` evidence flags; `AI_ENABLED` + `llm_client.py` |
| **Insurance A2A** | `app/insurer.py`, `services/insurer_demo/` |
| **Curriculum** | `learn/modules/01`–`07`, `learn/assessment.json` |

Study pack: [learn/README.md](../learn/README.md).  
Live walkthrough: home **Judge mode** (not `/learn` — public study pages removed).
