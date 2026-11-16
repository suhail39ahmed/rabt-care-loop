# Human-in-the-loop playbook

Who can do what in Rabt, what each input does, and what the system does next. **Built** = on `main` today. **Planned** = designed and tracked in an issue, not built yet.

Diagrams: [architecture.md §C, §E](architecture.md). Safety rules: [responsible-ai.md](responsible-ai.md).

## Personas

| Persona | Demo header (`X-Rabt-Persona`) | Role |
|---|---|---|
| Patient | `patient:fatima` | Reads the result card, does teach-back, books, asks questions, shares concerns |
| Coordinator | `human:coordinator-sara`, `human:coordinator` | Runs the queue, contacts patients, requests exceptional close |
| Clinician (GP / on-call) | `human:gp-aisha`, `human:gp-khan`, `human:gp` | Owns the case, records attendance and outcome, makes critical calls |
| Supervisor | `human:supervisor` | Second approver, refusals and high-risk oversight |

**Today the persona list is flat** (`services/orchestrator/app/auth.py`): any listed persona can call any write route, and the patient card sends the coordinator persona (`apps/web/lib/api.ts`). Role rules are planned in #52; the gap is tracked in #85. This is demo auth, not production IAM (Entra ID / UAE PASS in the pilot).

## Inputs and responses — built

| Who | Input (UI → API) | What the system does |
|---|---|---|
| Patient | Teach-back answers → `POST /cases/{id}/teachback` | Pass → `Understood`, navigation options. Fail → retry; second fail → `HumanCallback` + "Teach-back failed — human callback" queue item |
| Patient | Book a slot → `POST /cases/{id}/book` | `Booked`, option and payment path recorded; pay-and-claim options open a claim task |
| Patient | Claim paperwork → `POST /cases/{id}/claim` (`documents_ready`, `submitted`) | Claim sent to the insurer agent, reference stored |
| Coordinator | Insurer decision → `POST /cases/{id}/claim` (`approved`, `rejected`, `paid`) | Claim history on the case; patient sees the status |
| Patient | Ask a question → `POST /cases/{id}/reassure` | Answer from the local approved KB only, no-diagnosis lexicon |
| Clinician | **Accept ownership** → `POST /cases/{id}/accept` | `Owned`, SLA clock starts |
| Clinician | Decline → `POST /cases/{id}/decline` (API only) | Queue item "ownership declined" |
| Any staff | **Handle escalation** → `POST /cases/{id}/escalation/handle` | Ladder stops, case `Owned` |
| Any staff | Notify → `POST /cases/{id}/notify` (API only) | Approved template (AR/EN) sent to the patient card |
| Clinician | **Mark attended** → `POST /cases/{id}/attend` | `Attended` |
| Clinician | **Record outcome** → `POST /cases/{id}/outcome` | Outcome evidence; closure verifier may close if evidence is complete |
| Any staff | **Request close** → `POST /cases/{id}/close` | Without evidence: two-person `exceptional_closure` approval |
| Staff (not requester) | **Approve / Reject** → `POST /approvals/{token}/decision` | Two approvals close; reject keeps the case open; same user can't vote twice |
| Any | Withdraw consent → `POST /cases/{id}/consent/withdraw` (API only) | `OnHoldConsent`, automation stops |
| Any | Reject referral, e-consult draft (API only) | Recorded; e-consult packet drafted, not sent |
| System | Background tick every 5 s, **Advance +15m** → `POST /demo/advance` | Approval timeouts apply safe defaults; critical ladder moves to the next step; **never closes a case** |

## Known gaps (built, but incomplete) — #85

- Queue items are never resolved, even after the case moves on.
- No route or button for: resolve data query, mark unreachable, callback done, resume consent, send e-consult.
- Accept ownership moves a consent-hold case to `Owned` without a consent check.
- No Notify button on the board; decline, reject referral, consent withdraw and e-consult are API-only.
- A rejected exceptional close or a close request during a critical ladder can leave the case stuck (#50).

## Planned — concern listening & reassurance loop (#86)

| Who | Input | System response |
|---|---|---|
| Patient | "I have a concern" (text or voice, any language) | Deterministic crisis / red-flag / refusal check first → urgent human item, no AI reply. Otherwise the concern agent classifies type (fear of result, cost, time off work, past experience, feels fine, family / cultural, access) and risk, keeps the patient's words verbatim, and replies with **approved** reassurance and "why follow-up matters" snippets only |
| Coordinator | Patient concerns queue: Call · Send approved message · Book for patient · Assign expert | Message picker filtered by concern type and language; every action on the timeline |
| Expert / counsellor | Call with an AI-drafted conversation guide; log `convinced_booked` / `needs_another_call` / `refused` | Booked → normal loop; another call → re-queued with due time; refused → supervisor |
| Supervisor | Refusers, high-risk and trend views; another expert call, GP letter, home visit (pilot), informed refusal | Refusal recorded respectfully with reason; closure still needs two-person approval |

## Planned — critical / emergency expert call (#87)

| Who | Input | System response |
|---|---|---|
| System | Triage = CRITICAL | Ladder starts **and** an expert-call task is created now, with an AI-drafted urgent script in the patient's language (no result values, approved red-flag advice such as calling 998) |
| Clinician | Call patient, log `reached_going_now` | Ladder stops, case `Owned`, closure still needs evidence |
| Clinician | Log `reached_refusing` | Supervisor and physician notified now, informed refusal recorded |
| Clinician | Log `not_reached` | Retry in 5 min → alternate contact → supervisor; ladder keeps escalating |
| Admin | — | KPI: time-to-reach-critical |

Only a clinician makes the call; there is no AI-only or automated voice call. **Handle escalation** will require a logged call outcome.

## Role matrix (target, #52)

| Action | Patient | Coordinator | Clinician | Supervisor |
|---|---|---|---|---|
| Teach-back, book, ask, share concern, withdraw consent | ✔ | – | – | – |
| Accept / decline ownership | – | – | ✔ | ✔ |
| Notify, mark unreachable, resolve data query, callback done, resume consent | – | ✔ | ✔ | ✔ |
| Concern queue actions, assign expert | – | ✔ | ✔ | ✔ |
| Expert / critical call + outcome | – | – | ✔ | ✔ |
| Mark attended, record outcome, send e-consult | – | – | ✔ | – |
| Request exceptional close | – | ✔ | ✔ | ✔ |
| Vote on exceptional close (not own request) | – | ✔ | ✔ | ✔ |
| Informed refusal, GP letter, refusal / trend view | – | – | – | ✔ |

## Guardrails for every human-facing AI step

- The LLM classifies, summarises and drafts. It never sets or lowers urgency, never stops the ladder, never closes a case.
- Patient-facing text comes from approved, clinician-signed content; number check + no-diagnosis lexicon + optional Content Safety; template fallback on any failure.
- Crisis, red-flag and refusal wording always goes to a human first.
- Every entry records actor, `ai_generated` and provider / model (#68, #70).
