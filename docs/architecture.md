# Rabt architecture

## Image exports (for deck / README)

| Diagram | PNG |
|---|---|
| A — Target (Azure / Foundry) | [`docs/assets/architecture-target.png`](assets/architecture-target.png) · also `architecture.png` |
| B — As-built local demo | [`docs/assets/architecture-asbuilt.png`](assets/architecture-asbuilt.png) |
| C — Agent split | [`docs/assets/architecture-agent-split.png`](assets/architecture-agent-split.png) |
| D — SC-01 sequence | [`docs/assets/architecture-sequence-sc01.png`](assets/architecture-sequence-sc01.png) |
| E — Concern & expert-call loop (planned) | [`docs/assets/architecture-hitl-concern-loop.png`](assets/architecture-hitl-concern-loop.png) |
| F — Eventing today | [`docs/assets/architecture-eventing-today.png`](assets/architecture-eventing-today.png) |
| F — Eventing pilot (design only) | [`docs/assets/architecture-eventing-pilot.png`](assets/architecture-eventing-pilot.png) |

Source `.mmd` files sit next to the PNGs if you need to re-render: `npx @mermaid-js/mermaid-cli -i file.mmd -o file.png -b white -s 2`

---

**Stack honesty for the deck / judges**

| Layer | What Rabt uses | What we do **not** use |
|---|---|---|
| Orchestration | Our **state machine** + **Coordinator** (FastAPI) | LangChain, LangGraph, AutoGen |
| LLM agents (target) | **Microsoft Agent Framework** → **Azure OpenAI in Azure AI Foundry** | OpenAI.com keys as primary; LangChain chains |
| LLM agents (today, local demo) | **Approved templates** (no cloud required). AF+Foundry path is coded but **off** until Azure env vars are set | — |
| Tools | **MCP** servers (`fhir-mcp`, `directory-mcp`, `messaging-mcp`) | Ad-hoc unrestricted tool calling |
| Safety path | Deterministic Python (triage, escalation, closure) — **no LLM** | LLM deciding urgency or closure |
| HITL | `hitl.py` queue + board UI | Fully autonomous close |

> **One line for slides:** *Rabt is a deterministic care-loop workflow; Azure AI Foundry (via Microsoft Agent Framework) is used only to draft patient-facing text inside guardrails — not to decide triage, escalation, or closure.*

---

## A. Target architecture (submission / Azure)

Use this diagram in the deck. It matches the solution plan (§5).

```mermaid
flowchart LR
  subgraph SRC["Result sources — synthetic in prototype"]
    LAB["labs-mock / screening feed"]
    HIE["HAPI FHIR or Azure Health Data Services<br/>Malaffi stand-in"]
  end

  subgraph BUS["Events — pilot design, see §F"]
    WH["Webhook / Event Grid"]
    SB["Service Bus / local queue"]
  end

  subgraph ORCH["Rabt orchestrator — FastAPI"]
    SM["Case state machine"]
    CO["Coordinator supervisor"]
    HITL["HITL gates"]
  end

  subgraph AG["Agents"]
    DET["Deterministic<br/>DQ · Triage · Ownership<br/>Escalation · Navigator score · Closure"]
    LLM["LLM-assisted via Agent Framework<br/>Comms · Reassurance · E-consult · Navigator rationale"]
  end

  subgraph FOUNDRY["Azure AI Foundry"]
    AOAI["Azure OpenAI chat deployment"]
    CS["Content Safety"]
    AIS["AI Search KB — optional RAG"]
  end

  subgraph MCP["MCP tool servers"]
    MF["fhir-mcp"]
    MD["directory-mcp"]
    MM["messaging-mcp"]
  end

  subgraph UI["Apps"]
    PAT["Patient app — Sehatna role"]
    BRD["Clinician / coordinator board"]
  end

  LAB --> HIE
  HIE --> WH --> SB --> CO
  CO --> SM
  CO --> DET
  CO --> LLM
  LLM --> AOAI
  LLM --> CS
  LLM --> AIS
  CO --> MCP
  CO --> HITL
  HITL --> BRD
  CO --> PAT
  CO --> BRD
```

---

## B. As-built today (local demo — what you can run now)

```mermaid
flowchart TB
  WEB["Next.js apps<br/>patient · board · KPIs"]
  API["FastAPI orchestrator :8000"]
  LED["SQLite ledger<br/>cases · queue · approvals"]
  SM["state_machine.py"]
  CO["coordinator.py"]
  DET["agents/* deterministic"]
  COM["comms agent<br/>templates first"]
  REA["reassurance agent<br/>local KB markdown"]
  MCP["MCP server stubs"]

  WEB <--> API
  API --> CO
  CO --> SM
  CO --> LED
  CO --> DET
  CO --> COM
  CO --> REA
  COM -.->|"only if AZURE_OPENAI_ENDPOINT set"| AF["Microsoft Agent Framework<br/>+ Azure OpenAI in Foundry"]
  COM -->|"default today"| TPL["YAML templates AR/EN"]
  MCP -.-> API
```

**Default path today:** no LangChain, no Foundry call — templates + deterministic agents.  
**Foundry path:** set `AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_MODEL` (+ Content Safety); `comms/agent.py` uses `agent_framework.Agent` + `OpenAIChatClient`.

---

## C. Agent split (important for judges)

```mermaid
flowchart LR
  subgraph DET["Deterministic — decide"]
    DQ[Data quality]
    TR[Triage rules YAML]
    OW[Ownership / SLA]
    ESC[Escalation ladder]
    NAV[Navigator scoring]
    CL[Closure verifier]
  end

  subgraph LLM["LLM-assisted — explain only"]
    CM[Patient Comms]
    RE[Reassurance RAG]
    EC[E-consult summary]
    NR[Navigator rationale text]
  end

  subgraph HUMAN["Human-in-the-loop"]
    Q[Escalation queue]
    TB[Teach-back failure callback]
    FY[4-eyes exceptional closure]
    CN[Consent withdrawal]
    CQ["Patient concerns queue<br/>(planned #86)"]
    XC["Critical expert call<br/>(planned #87)"]
  end

  subgraph PLAN["LLM-assisted — planned"]
    CA["Concern classify + summary #86"]
    CS2["Call script / conversation guide #86 #87"]
  end

  DET --> HUMAN
  LLM --> HUMAN
  PLAN -.-> HUMAN
```

Dashed / "planned" boxes are not built yet. Full list of human inputs and who can use them: [hitl-playbook.md](hitl-playbook.md).

---

## D. One case through the system (SC-01)

```mermaid
sequenceDiagram
  participant Lab as labs-mock / FHIR
  participant API as Orchestrator
  participant DQ as DQ agent
  participant Tri as Triage agent
  participant Own as Ownership
  participant HITL as HITL / GP
  participant Comms as Comms agent
  participant Foundry as Azure OpenAI Foundry
  participant Pat as Patient app
  participant Nav as Navigator
  participant Close as Closure verifier

  Lab->>API: Observation (HbA1c)
  API->>DQ: check
  DQ-->>API: ok
  API->>Tri: rules
  Tri-->>API: URGENT
  API->>Own: assign GP
  Own-->>API: AwaitingOwner
  HITL->>API: accept ownership
  API->>Comms: draft message
  alt Foundry configured
    Comms->>Foundry: rewrite template
    Foundry-->>Comms: text + Content Safety
  else Local demo
    Comms-->>API: static approved template
  end
  API->>Pat: result card + teach-back
  Pat->>API: teach-back pass
  API->>Nav: in-network options
  Pat->>API: book
  HITL->>API: attended + outcome
  API->>Close: evidence gate
  Close-->>API: Closed
```

---

## E. Human-in-the-loop: concern, reassurance and expert-call loop

**Status: design, not built yet.** Tracked in #86 (concern loop), #87 (critical expert call), #85 (HITL gaps) and #52 (roles). Today only the teach-back failure callback and the critical escalation ladder exist.

```mermaid
flowchart TB
  subgraph A["A. Concern listening & reassurance (#86)"]
    direction TB
    P1["Patient: teach-back fail<br/>or 'I have a concern'<br/>text / voice, any language"]
    LEX{"Crisis / red-flag /<br/>refusal lexicon<br/>(deterministic, runs first)"}
    CAG["Concern agent — LLM<br/>type · risk · summary<br/>patient words kept verbatim"]
    REP["Approved reassurance +<br/>'why follow-up matters'<br/>snippets only · guardrails"]
    CQ["Coordinator: Patient concerns queue<br/>call · send approved msg · book · assign expert"]
    EXP["Expert / counsellor call<br/>AI-drafted conversation guide"]
    OUT{"Call outcome"}
    SUP["Supervisor view<br/>refusers · high risk · trends<br/>another call · GP letter · informed refusal"]
    BK["Booking → normal loop"]
    P1 --> LEX
    LEX -->|"crisis / red flag / refusal"| CQ
    LEX -->|"ok"| CAG --> REP --> CQ
    CQ --> EXP --> OUT
    OUT -->|"convinced_booked"| BK
    OUT -->|"needs_another_call"| CQ
    OUT -->|"refused"| SUP
  end

  subgraph B["B. Critical / emergency expert call (#87)"]
    direction TB
    CR["Triage = CRITICAL"]
    LAD["Escalation ladder keeps running<br/>coordinator 0 → on-call 15m → lead 45m"]
    TASK["Expert call task — now<br/>AI-drafted urgent script, no numbers<br/>approved red-flag advice (998)"]
    CL["Clinician calls patient<br/>(never AI-only)"]
    CO{"Outcome"}
    GO["reached_going_now<br/>ladder stops · case Owned"]
    REF["reached_refusing<br/>supervisor + physician now<br/>informed refusal"]
    NR["not_reached<br/>retry 5m → alternate contact → supervisor"]
    CR --> LAD
    CR --> TASK --> CL --> CO
    CO --> GO
    CO --> REF
    CO --> NR --> CL
    NR -.->|"ladder not stopped"| LAD
  end

  AUD[("Ledger timeline<br/>actor · ai_generated · model<br/>time-to-reach-critical KPI")]
  A --> AUD
  B --> AUD
```

Rules that do not change: the LLM only classifies, summarises and drafts from approved content; it never sets urgency, never lowers deterministic urgency, never stops the ladder and never closes a case. Closure still needs evidence or two-person approval.

---

## F. Eventing: demo today vs pilot

### Today (as built)

- **No message bus.** FastAPI routes call `Coordinator` methods directly and synchronously, in the same process (`services/orchestrator/app/main.py` → `coordinator.py`).
- **SQLite ledger is the event log.** Every transition appends to the case `timeline_json` / `provenance_json`; webhook ingest is de-duplicated through `processed_events` (`ledger.py`, `coordinator.py:103`).
- **Time-based events** come from a background loop that calls `coordinator.tick()` every 5 s (`main.py:35-45`) to sweep HITL timeouts and advance the escalation ladder, plus `POST /demo/advance` to move the demo clock.
- **One process on the Render free tier**, one replica (`render.yaml`); the SQLite file is in `/tmp` and is reseeded on every start.
- **Limits:** single instance only; no guaranteed delivery if the process crashes or the free instance sleeps (in-flight work and timers are lost); no fan-out to other consumers; tick errors are swallowed.

```mermaid
flowchart LR
  WEB["Next.js / FHIR webhook"] -->|"HTTP"| API["FastAPI route"]
  API -->|"sync call, in-process"| CO["Coordinator"]
  CO --> SM["state_machine.py"]
  CO --> LED[("SQLite ledger<br/>timeline = event log<br/>processed_events = idempotency")]
  TICK["asyncio loop every 5s<br/>+ POST /demo/advance"] -->|"tick(): sweep timeouts,<br/>advance ladder"| CO
  CO -->|"HITL queue / approvals"| LED
```

### Pilot (planned — design only, not built)

- The coordinator publishes **domain events** — `CaseCreated`, `CaseTriaged`, `CaseEscalated`, `ConcernRaised`, `ExpertCallRequired`, `CallOutcomeLogged`, `CaseClosed`, … — instead of doing all side effects inline.
- **Azure Service Bus** (topics + sessions per case) is preferred for the clinical workflow: ordered per case, retries, dead-letter queue. **Azure Event Grid** for lightweight fan-out (e.g. analytics, FHIR change notifications).
- **Subscribers:** patient notifications (SMS / WhatsApp / app), expert-call queue (#86, #87), Insurance Navigator (#74), analytics / KPIs, Malaffi / FHIR sync.
- **Durable timers** replace the 5 s sweep: Service Bus scheduled messages for ladder steps and approval due times, or Azure Durable Functions timers.
- **Transactional outbox in Postgres:** state change and outgoing event are written in one transaction; a relay publishes the outbox, so nothing is lost if the process dies between commit and publish. Consumers stay idempotent (same idempotency-key idea as `processed_events`).

```mermaid
flowchart LR
  CO["Coordinator<br/>(N instances)"] -->|"one transaction"| PG[("Postgres<br/>cases + outbox")]
  PG --> RELAY["Outbox relay"]
  RELAY --> SB["Azure Service Bus topic<br/>sessions per case · retries · DLQ"]
  RELAY -.-> EG["Azure Event Grid<br/>fan-out"]
  SB --> N["Notifications"]
  SB --> X["Expert-call queue"]
  SB --> INS["Insurance Navigator"]
  SB --> FHIR["Malaffi / FHIR sync"]
  EG --> AN["Analytics / KPIs"]
  TMR["Scheduled messages /<br/>Durable Functions timers"] -->|"ladder step due,<br/>approval timeout"| CO
  SB -.->|"schedule"| TMR
```

> Pilot eventing is a design. None of Service Bus, Event Grid, Durable Functions or the outbox exists in the code today.

---

## F2. Navigator payment paths (cashless first, then pay-and-claim)

Each navigator option carries a payment path, computed by rules in `services/agents/navigator/payment.py`:

| Mode | When | Patient pays at visit |
|------|------|-----------------------|
| `cashless` | Provider is in the plan network and bills the insurer directly | Co-pay only |
| `reimbursement` | In-network provider that is not cashless, or an out-of-network provider that accepts self-pay **and** the plan reimburses out-of-network care | Full fee, then claims back `pct` % |
| `self_pay` | Out-of-network, no reimbursement, and the patient explicitly opted in to self-pay | Full fee |

Out-of-network options that are neither reimbursable nor an explicit self-pay opt-in are still excluded.
Score weights are 40 / 20 / 10 for cashless / reimbursement / self-pay, plus distance, earliest slot and language.
Ties break on payment mode, then provider ID, so the ranking is deterministic. The LLM can only write rationale text.

After ranking, the coordinator asks the Demo Health Insurance agent (`payment_options` A2A skill) whether the top option is cashless or reimbursable and stores the reply in `evidence.payment_options`.
Booking a pay-and-claim option opens a **claim task** on the case (`evidence.claim`). The task lists the documents, the claim window and the expected amount back.
The claim moves through `not_started → documents_ready → submitted → approved | rejected → paid` (`POST /cases/{id}/claim`).
The patient handles the paperwork steps. On `submitted` the insurer agent's `claim_submit` skill returns a reference, and staff record the insurer decision.

## G. File map

| Box on diagram | Code |
|---|---|
| State machine | `services/orchestrator/app/state_machine.py` |
| Supervisor | `services/orchestrator/app/coordinator.py` |
| Delegation contracts | `services/orchestrator/app/contracts.py` |
| HITL | `services/orchestrator/app/hitl.py` |
| Deterministic agents | `services/agents/{triage,data_quality,ownership,escalation,navigator,closure}/` |
| Foundry hook (optional) | `services/agents/comms/agent.py` → `agent_framework` |
| Reassurance (local KB) | `services/agents/reassurance/agent.py` + `data/kb/` |
| MCP | `mcp-servers/*/` |
| UI | `apps/web/` |

---

## H. What to say if asked “Are you on Foundry or LangChain?”

> We do **not** use LangChain. The product orchestration is our own FHIR-aligned state machine. For generative steps we use the **Microsoft Agent Framework** pointing at **Azure OpenAI hosted in Azure AI Foundry**, with Content Safety. Safety-critical steps (triage, escalation, closure) stay deterministic Python so an LLM cannot falsely close a case or miss a critical result. The local prototype runs fully on templates so judges can demo without cloud keys; Foundry lights up when Azure credentials are provided.
