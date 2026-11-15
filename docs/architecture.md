# Rabt architecture

## Image exports (for deck / README)

| Diagram | PNG |
|---|---|
| A — Target (Azure / Foundry) | [`docs/assets/architecture-target.png`](assets/architecture-target.png) · also `architecture.png` |
| B — As-built local demo | [`docs/assets/architecture-asbuilt.png`](assets/architecture-asbuilt.png) |
| C — Agent split | [`docs/assets/architecture-agent-split.png`](assets/architecture-agent-split.png) |
| D — SC-01 sequence | [`docs/assets/architecture-sequence-sc01.png`](assets/architecture-sequence-sc01.png) |

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

  subgraph BUS["Events"]
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
  WEB["Next.js apps<br/>patient · board · learn · KPIs"]
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
  end

  DET --> HUMAN
  LLM --> HUMAN
```

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

## E. File map

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

## F. What to say if asked “Are you on Foundry or LangChain?”

> We do **not** use LangChain. The product orchestration is our own FHIR-aligned state machine. For generative steps we use the **Microsoft Agent Framework** pointing at **Azure OpenAI hosted in Azure AI Foundry**, with Content Safety. Safety-critical steps (triage, escalation, closure) stay deterministic Python so an LLM cannot falsely close a case or miss a critical result. The local prototype runs fully on templates so judges can demo without cloud keys; Foundry lights up when Azure credentials are provided.
