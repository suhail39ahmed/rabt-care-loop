# Module 4 — Human-in-the-loop (deep)

## Idea
**HITL** = automation *pauses* and a human must act before the case continues. Humans are not “if the LLM fails” — they are **gates on the safety path**.

## Gates in Rabt

| Gate | When | What human does |
|---|---|---|
| Critical ladder | CRITICAL triage | Expert call (approved script) + log outcome; then Handle escalation |
| Ownership handshake | AwaitingOwner | GP accept / decline with reason |
| Teach-back fail | 2 failures | Phone callback → **Callback done** |
| Consent | Withdraw messaging | Resume consent (cannot Accept while on hold) |
| Data query | Bad intake | **Resolve data query** |
| Unreachable | No engagement | **Mark unreachable** → ladder |
| Concern | Patient shares barrier | Queue item Call / Book / Assign |
| Closure | No evidence | Blocked; exceptional close needs **4-eyes** |
| Unknown code | No triage rule | Human triage |
| Queue clutter | Open items | **Resolve queue item** (`POST /queue/{id}/resolve`) |

## Safe timeouts
`hitl.py` → `SAFE_DEFAULTS`:
- exceptional_closure → **keep_open**  
- critical → **next_ladder_step**  
- Never silent auto-close  

## Where you see it in the UI
Board → coral **Escalation queue** → Resolve / open case  
CRITICAL: call script + outcome buttons → **Handle escalation (HITL)**  
Patient: **Share concern** + teach-back (persona `patient:fatima`)

## Playbook
`docs/hitl-playbook.md` + concern-loop diagram under `docs/assets/architecture-hitl-concern-loop.*`

## Code to open
- `services/orchestrator/app/hitl.py`  
- `coordinator.resume_consent` / `callback_done` / `log_call_outcome` / `share_concern`  
- Board actions in `apps/web/app/board/page.tsx`  
