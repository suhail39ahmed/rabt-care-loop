# Module 2 — Agentic workflow (deep)

## Idea
An **agentic workflow** here means: the *path* is decided by **code** (a state machine), not by a free LLM. Agents run *inside* steps.

## Why healthcare needs this
If an LLM could jump `New → Closed`, you get **false closures** — deadly for trust and scoring. So every transition is in `ALLOWED`.

## Happy path (Fatima / SC-01)
1. `New` — Observation ingested  
2. `Triaged` — rules say URGENT  
3. `AwaitingOwner` — GP assigned  
4. `Owned` — GP accepts (handshake)  
5. `PatientNotified` — AR/EN card  
6. `Understood` — teach-back pass  
7. `Referred` → coverage check → `Booked` → `Attended`  
8. `ClosurePending` → `Closed` (evidence)

## Side paths (bit by bit)
| Trigger | State move |
|---|---|
| Bad / missing data | `New → DataQuery` (resolve via board) |
| CRITICAL | `Triaged → Escalated` + expert-call queue |
| Teach-back fail ×2 | `PatientNotified → HumanCallback` |
| Consent withdrawn | `Owned` or `PatientNotified` → `OnHoldConsent` |
| Consent resumed | `OnHoldConsent → Owned` |
| Callback done | `HumanCallback → Owned` |
| Close without evidence | 4-eyes or bounce; reject restores prior open state |
| Preauth pending | Book blocked until insurer clears |

## Code to open
- `services/orchestrator/app/state_machine.py` — `S`, `ALLOWED`, `transition()`  
- `coordinator.py` — drives the path for a case  

## Check yourself
Can `Booked` go straight to `Closed`? **No.** Attendance + outcome (or human 4-eyes) required.  
Can you Handle CRITICAL escalation without a call outcome? **No.** Log `reached_going_now` / `reached_refusing` / `not_reached` first.
