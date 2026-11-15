export type ModuleMeta = {
  slug: string;
  num: string;
  title: string;
  minutes: number;
  summary: string;
};

export const MODULES: ModuleMeta[] = [
  {
    slug: "what-is-rabt",
    num: "01",
    title: "What are we building?",
    minutes: 5,
    summary: "Problem, promise, and the pieces — owner, next step, closure.",
  },
  {
    slug: "workflow",
    num: "02",
    title: "Agentic workflow (deep)",
    minutes: 8,
    summary: "State machine backbone; happy path and side paths.",
  },
  {
    slug: "delegation",
    num: "03",
    title: "Agentic delegation (deep)",
    minutes: 8,
    summary: "Coordinator supervisor, contracts, who decides vs explains.",
  },
  {
    slug: "hitl",
    num: "04",
    title: "Human-in-the-loop (deep)",
    minutes: 7,
    summary: "Safety gates, queue, 4-eyes, safe timeouts.",
  },
  {
    slug: "architecture",
    num: "05",
    title: "Architecture bits",
    minutes: 6,
    summary: "Foundry vs LangChain, MCP, as-built vs target.",
  },
  {
    slug: "features-deep-dive",
    num: "06",
    title: "What Rabt adds (F1–F8)",
    minutes: 25,
    summary: "Each capability: what / tackle / tech / scripts / resolve.",
  },
];

export const MODULE_BODY: Record<string, string> = {
  "what-is-rabt": `# What are we building?

**Rabt** (ربط) means binding / connection. We are building an **AI care-loop orchestrator**: every actionable screening result gets an **owner**, a **next step**, and **documented closure**.

## The problem
In Abu Dhabi screening programmes, a result can exist while the next step stalls: unclear ownership across facilities, insurance networks, patients who did not understand or attend, fragmented records. ADPHC said reminders alone are not enough.

## What Rabt adds
Full deep dive (what / tech / scripts / resolve) → **/learn/features**

1. Result intake + deterministic triage  
2. Ownership handshake (accept / decline with reason)  
3. Insurance-aware navigator  
4. AR/EN result card + teach-back  
5. Guardrailed reassurance  
6. Escalation ladder (HITL)  
7. Evidence-gated closure  
8. Audit trail (fact / calculated / AI)

## What it is not
- Not an EMR, not Malaffi, not Sehatna (it plugs in)  
- Not a diagnostic model  
- **Not LangChain**

## Code map
| File | Job |
|---|---|
| \`state_machine.py\` | Legal states |
| \`coordinator.py\` | Supervisor |
| \`services/agents/*\` | Specialists |
| \`hitl.py\` | Human gates |
| \`apps/web\` | Patient + board |

**Remember:** deterministic code decides; LLM explains; humans gate unsafe paths.`,

  workflow: `# Agentic workflow (deep)

A **workflow** is a path **code** decides. In Rabt that path is a **state machine**. Agents run *inside* steps — they do not freely invent the journey.

## Why
If an LLM could jump \`New → Closed\`, you get false closures. So every edge is listed in \`ALLOWED\`.

## Happy path (Fatima)
\`New → Triaged → AwaitingOwner → Owned → PatientNotified → Understood → Referred → Booked → Attended → ClosurePending → Closed\`

## Side paths
| Trigger | Move |
|---|---|
| Bad data | \`DataQuery\` |
| CRITICAL | \`Escalated\` (no LLM) |
| Teach-back fail ×2 | \`HumanCallback\` |
| Consent withdrawn | \`OnHoldConsent\` |
| Close without evidence | blocked |

## Open in the IDE
\`services/orchestrator/app/state_machine.py\`  
\`coordinator.py\` methods that call \`transition()\`

## Mini-check
Can \`Booked\` go straight to \`Closed\`? **No** — need attendance + outcome or human 4-eyes.`,

  delegation: `# Agentic delegation (deep)

**Delegation** = supervisor asks a specialist for one step, then **verifies** before writing state.

Supervisor = **Coordinator** (\`coordinator.py\`).

## Contract
- \`DelegationRequest\`: step, depth ≤ 2, allowed_tools, inputs  
- \`DelegationResult\`: status, proposed_transition, outputs  

File: \`contracts.py\` + \`TOOL_SCOPES\`.

## Decide vs explain
| Decide (deterministic) | Explain (LLM / templates) |
|---|---|
| DQ, Triage, Ownership, Escalation, Navigator score, Closure | Comms, Reassurance, E-consult, Navigator rationale |

## Flow
Event → Coordinator → agent.run → DelegationResult → verify → \`state_machine.transition\`  
If verify fails / needs_human → HITL queue.

## Foundry
Optional: Microsoft Agent Framework → Azure OpenAI in **Azure AI Foundry**.  
Without keys: approved YAML templates. **Not LangChain.**`,

  hitl: `# Human-in-the-loop (deep)

HITL means automation **pauses** until a human acts. Gates are designed in — not bolted on when the LLM fails.

## Gates
1. **CRITICAL** → ladder + queue; SMS without values; no LLM  
2. **Ownership** → accept / decline with reason  
3. **Teach-back ×2 fail** → HumanCallback  
4. **Consent withdraw** → OnHoldConsent  
5. **Closure without evidence** → blocked; exceptional close needs **two different humans**  
6. **Unknown triage code** → needs_human_triage  

## Safe timeouts
\`SAFE_DEFAULTS\` in \`hitl.py\`: \`keep_open\`, \`next_ladder_step\` — **never silent auto-close**.

## See it
Board → coral escalation queue → Handle escalation.  
GC-10 → Try close → blocked.

## Open
\`services/orchestrator/app/hitl.py\`  
\`apps/web/app/board/page.tsx\``,

  architecture: `# Architecture bits

## Target boxes
Labs/FHIR → events → Orchestrator (state machine + coordinator)  
→ deterministic agents + LLM agents (Foundry) + MCP tools + HITL → Board / Patient app

## Local today
FastAPI + SQLite · Next.js · templates by default · Foundry if env set · synthetic data only

## Diagrams
- Workflow / Delegation / HITL under \`/learn-assets/\`  
- Full system: \`docs/assets/architecture-target.png\`

## After this lesson
1. **What Rabt adds (F1–F8)** → **/learn/features** (full deep dive per capability)  
2. Practice game → **/learn/game**  
3. Assessment (pass ≥ 80%) → **/learn/assessment**`,

  "features-deep-dive": `# What Rabt adds — session overview

This lesson is the **index**. Open each capability page for the full five-part deep dive:
**what → how we tackle → technology → scripts → how it resolves.**

## The eight capabilities

1. **F1 Result intake + deterministic triage** — Observation → case; YAML rules set urgency (no LLM).  
2. **F2 Ownership handshake** — One owner; accept / decline with reason.  
3. **F3 Insurance-aware navigator** — In-network ranking; book next step.  
4. **F4 AR/EN result card + teach-back** — Explain in Arabic/English; confirm understanding.  
5. **F5 Guardrailed reassurance** — KB-only answers; never diagnose.  
6. **F6 Escalation ladder (HITL)** — Critical/stuck → human ladder; SMS without values.  
7. **F7 Evidence-gated closure** — Close only with evidence or 4-eyes human decision.  
8. **F8 Audit trail (fact / calculated / AI)** — Every transition labelled for RAI.

## Where to click
Go to **/learn/features** and work **F1 → F8** in order.

## Rule
Deterministic code **decides**. LLM **explains**. Humans **gate** unsafe paths. Not LangChain — Coordinator + state machine; optional Agent Framework → Azure AI Foundry for text.
`,
};

export type AssessQ = {
  id: string;
  topic: string;
  q: string;
  choices: string[];
  answer: number;
  why: string;
};

export const ASSESSMENT = {
  title: "Rabt proficiency assessment",
  passPercent: 80,
  timeHintMin: 10,
  instructions:
    "Answer all questions. Pass at 80%. Covers product, workflow, delegation, HITL, and architecture.",
  questions: [
    {
      id: "a1",
      topic: "product",
      q: "Rabt’s core promise is…",
      choices: [
        "Predict who to screen next (#4)",
        "Every actionable result gets an owner, next step, and documented closure",
        "Replace Malaffi entirely",
        "Diagnose diabetes from HbA1c alone",
      ],
      answer: 1,
      why: "Challenge #5 — close the screening-to-care loop.",
    },
    {
      id: "a2",
      topic: "product",
      q: "Patient-facing Rabt UI stands in for…",
      choices: ["Databricks", "Sehatna-style patient app", "Service Bus", "Synthea"],
      answer: 1,
      why: "Prototype plays the Sehatna role.",
    },
    {
      id: "a3",
      topic: "workflow",
      q: "Who/what forbids New → Closed?",
      choices: ["The LLM", "The state machine ALLOWED map", "Mailpit", "next-intl"],
      answer: 1,
      why: "state_machine.transition raises IllegalTransition.",
    },
    {
      id: "a4",
      topic: "workflow",
      q: "CRITICAL BP first moves to…",
      choices: ["Closed", "Understood", "Escalated", "Booked"],
      answer: 2,
      why: "Triaged → Escalated; no LLM.",
    },
    {
      id: "a5",
      topic: "workflow",
      q: "Evidence-gated closure needs…",
      choices: [
        "Any LLM saying ‘done’",
        "Attended encounter + outcome (or human reason with 4-eyes)",
        "Only a booked slot",
        "A thumbs-up emoji",
      ],
      answer: 1,
      why: "Closure verifier — target 0 false closures.",
    },
    {
      id: "a6",
      topic: "delegation",
      q: "The supervisor that delegates is…",
      choices: ["Navigator", "Coordinator", "Mailpit", "Synthea"],
      answer: 1,
      why: "coordinator.py",
    },
    {
      id: "a7",
      topic: "delegation",
      q: "Urgency classification is done by…",
      choices: [
        "Comms LLM",
        "Triage YAML rules (deterministic)",
        "Patient teach-back",
        "Foundry Agent Service only",
      ],
      answer: 1,
      why: "Deterministic code decides.",
    },
    {
      id: "a8",
      topic: "delegation",
      q: "Delegation depth hard limit is…",
      choices: ["Unlimited", "≤ 2", "Exactly 10", "0 forever"],
      answer: 1,
      why: "contracts.py le=2",
    },
    {
      id: "a9",
      topic: "delegation",
      q: "Which stack is correct for LLM text?",
      choices: [
        "LangChain + OpenAI.com only",
        "Microsoft Agent Framework → Azure OpenAI in Foundry (optional; templates otherwise)",
        "Random GPT with no guardrails",
        "No templates allowed",
      ],
      answer: 1,
      why: "Not LangChain.",
    },
    {
      id: "a10",
      topic: "hitl",
      q: "CRITICAL SMS must…",
      choices: [
        "Include systolic/diastolic values",
        "Omit result values and avoid LLM on the path",
        "Be written only in English slang",
        "Auto-close the case",
      ],
      answer: 1,
      why: "No values on insecure channel.",
    },
    {
      id: "a11",
      topic: "hitl",
      q: "Teach-back fails twice →",
      choices: ["Closed", "HumanCallback", "DataQuery", "Booked"],
      answer: 1,
      why: "HITL callback gate.",
    },
    {
      id: "a12",
      topic: "hitl",
      q: "On approval timeout, Rabt…",
      choices: [
        "Auto-closes as success",
        "Applies safe default (e.g. keep_open) — never silent close",
        "Deletes the patient",
        "Marks NORMAL",
      ],
      answer: 1,
      why: "SAFE_DEFAULTS",
    },
    {
      id: "a13",
      topic: "architecture",
      q: "MCP servers in Rabt are for…",
      choices: [
        "Unrestricted DB wipe tools",
        "Scoped tools (FHIR / directory / messaging)",
        "Training Synthea",
        "Replacing the state machine",
      ],
      answer: 1,
      why: "Least-privilege tools.",
    },
    {
      id: "a14",
      topic: "architecture",
      q: "Local demo without Azure keys uses…",
      choices: [
        "Nothing — app won’t start",
        "Approved AR/EN YAML templates",
        "Only LangChain memory",
        "Live Malaffi",
      ],
      answer: 1,
      why: "Templates first.",
    },
    {
      id: "a15",
      topic: "product",
      q: "Timeline labels fact / calculated / AI exist because…",
      choices: [
        "Decoration",
        "Responsible AI — separate recorded facts, rules, and generated text",
        "FHIR forbids timelines",
        "Judges dislike colours",
      ],
      answer: 1,
      why: "Keep them visibly separate.",
    },
  ] as AssessQ[],
};
