# Module 3 — Agentic delegation (deep)

## Idea
**Delegation** = a supervisor asks a specialist to do one step, then checks the result before writing state.

In Rabt the supervisor is the **Coordinator**.

## Contract (typed)
```
DelegationRequest  →  step, depth≤2, allowed_tools, inputs
DelegationResult   →  status ok|needs_human|error, proposed_transition, outputs
```
File: `services/orchestrator/app/contracts.py`

## Who does what (bits)

| Step | Agent | Decide or explain? |
|---|---|---|
| data_quality | DQ checks | Decide (hold bad data) |
| triage | YAML rules | Decide urgency |
| ownership | assign GP / SLA | Decide owner |
| escalation | ladder | Decide (no LLM) |
| navigate | scoring + insurer check | Decide ranking / coverage |
| intent | concern classify | Decide crisis; explain snippet |
| comms | templates ± LLM client | Explain only (if `AI_ENABLED`) |
| reassurance | KB keyword / mock RAG | Explain only; `ai_generated` false unless LLM |
| econsult | packet summary | Explain only |
| closure | evidence gate | Decide closable? |

## Flow
```
Event → Coordinator → pick agent → DelegationResult → verify → state_machine.transition
                                              ↘ needs_human → HITL queue
```

## LLM path (honest)
- **Not LangChain**  
- Default: approved YAML templates (`AI_ENABLED=false`)  
- Optional: `llm_client.chat_completion` (OpenAI-compatible or Azure) behind kill switch  
- Timeline violet **only** when `ai_generated` / `ai_translated` is true  

## Code to open
- `coordinator.py` — `open_from_observation`, `notify_patient`, `_apply`  
- `services/agents/triage/engine.py`  
- `services/agents/comms/agent.py`  
- `services/agents/common/llm_client.py`  
- `services/agents/intent/classify.py`  
