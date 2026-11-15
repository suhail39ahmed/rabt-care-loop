export type FeatureDeep = {
  slug: string;
  num: string;
  title: string;
  oneLiner: string;
  what: string;
  tackle: string;
  tech: string[];
  scripts: Array<{ path: string; role: string }>;
  resolve: string;
  demo: string;
  relatedState?: string;
  abbrUsed: string[];
};

export const FEATURES: FeatureDeep[] = [
  {
    slug: "intake-triage",
    num: "F1",
    title: "Result intake + deterministic triage",
    oneLiner:
      "A screening result becomes a case; rules (not an LLM — large language model) set urgency.",
    what: `When a lab/screening programme posts a FHIR (Fast Healthcare Interoperability Resources) Observation (e.g. HbA1c = Hemoglobin A1c, BP = blood pressure, FIT = faecal immunochemical test), Rabt opens a **case** and classifies urgency: CRITICAL / URGENT / ROUTINE / NEEDS_HUMAN. Triage is **deterministic** — versioned YAML (config) rules with structured comparisons (no eval, no LLM). Bad or missing data is held in DataQuery first. LOINC (Logical Observation Identifiers Names and Codes) identifies the test type.`,
    tackle: `1) Idempotent ingest (same Observation twice → one case). 2) DQ (data quality) checks for value/unit/contradictions. 3) Match LOINC + thresholds in rules/v1.yaml. 4) CRITICAL → Escalated ladder; else → AwaitingOwner. Unknown codes → HITL (human-in-the-loop) triage queue.`,
    tech: [
      "FastAPI webhook API (application programming interface) /cases/ingest",
      "SQLite DB (database) ledger with idempotency keys",
      "YAML rules engine (Python)",
      "FHIR R4 Observation shape (synthetic / HAPI FHIR server optional as Malaffi HIE stand-in)",
      "State machine: New → Triaged | DataQuery | Escalated",
    ],
    scripts: [
      { path: "services/orchestrator/app/main.py", role: "HTTP ingest + FHIR webhook" },
      {
        path: "services/orchestrator/app/coordinator.py → open_from_observation()",
        role: "Orchestrates DQ → triage → ownership/escalation",
      },
      { path: "services/agents/data_quality/checks.py", role: "Missing unit/value, contradictions" },
      { path: "services/agents/triage/engine.py", role: "Rule matcher" },
      {
        path: "services/agents/triage/rules/v1.yaml",
        role: "Illustrative thresholds (need DoH / clinician sign-off)",
      },
      { path: "services/labs-mock/generator.py", role: "Posts synthetic results" },
    ],
    resolve: `Resolved when the case leaves New with a rule_id + urgency + pathway on the ledger, or sits in DataQuery/needs_human until a coordinator fixes data. CRITICAL never waits on an LLM.`,
    demo: "Seed GC-01 (golden case: HbA1c→URGENT) and GC-02 (BP→Escalated). Or POST /cases/ingest.",
    relatedState: "New → Triaged / DataQuery / Escalated",
    abbrUsed: ["FHIR", "HbA1c", "BP", "FIT", "LLM", "YAML", "LOINC", "DQ", "HITL", "HAPI", "HIE", "DoH", "GC-01…", "API", "HTTP", "DB"],
  },
  {
    slug: "ownership-handshake",
    num: "F2",
    title: "Ownership handshake (accept / decline with reason)",
    oneLiner: "Exactly one accountable owner — hand-off completes only when they accept.",
    what: `Every case has a FHIR Task-like owner (GP = general practitioner / family physician, or programme coordinator). Assignment alone is not enough: the next owner must **accept**. Decline requires a **reason** (capacity, wrong specialty, etc.) and the case stays visible / re-queued — no silent drop. This is a HITL (human-in-the-loop) gate.`,
    tackle: `Ownership agent picks generalPractitioner (else programme coordinator) + SLA (service level agreement / time-limit) due date. State = AwaitingOwner until API POST accept. Decline → self-loop AwaitingOwner + HITL queue item. Provenance records actor + reason.`,
    tech: [
      "Deterministic ownership agent",
      "State: AwaitingOwner ↔ Owned",
      "HITL enqueue on decline",
      "Board UI (user interface) Accept button",
      "Illustrative SLA hours map",
    ],
    scripts: [
      { path: "services/agents/ownership/assign.py", role: "Choose owner + due_at" },
      {
        path: "services/orchestrator/app/coordinator.py → accept_ownership() / decline_ownership()",
        role: "Handshake transitions",
      },
      { path: "services/orchestrator/app/main.py → POST /cases/{id}/accept", role: "API endpoint" },
      { path: "apps/web/app/board/page.tsx", role: "Clinician Accept ownership" },
      { path: "services/orchestrator/app/hitl.py → enqueue()", role: "Decline → board queue" },
    ],
    resolve: `Resolved when state is Owned with owner_id/owner_name set and a provenance row actor=human:…. Declines never auto-close; coordinator reassigns.`,
    demo: "Board → case in AwaitingOwner → Accept ownership. Demo seed already accepts Fatima’s GP.",
    relatedState: "AwaitingOwner → Owned (or decline → AwaitingOwner)",
    abbrUsed: ["FHIR", "GP", "HITL", "SLA", "API", "UI"],
  },
  {
    slug: "insurance-navigator",
    num: "F3",
    title: "Insurance-aware navigator",
    oneLiner: "Rank next-step providers by clinical pathway + in-network plan — exclude OON (out-of-network).",
    what: `After the patient understands the result, Rabt suggests where to go next (GP, gastroenterology, etc.). Options are scored by network membership, distance, earliest slot, language. **OON (out-of-network) options are excluded** (unless explicit self-pay). The LLM (large language model) must not change the ranking — only optional rationale text.`,
    tackle: `Map pathway → specialty. Filter providers by plan network_id. Score and return top 3. Patient books one option → Booked. Referral reject (capacity/OON) → ReferralRejected → re-navigate. MCP (Model Context Protocol) directory tools can expose providers/slots.`,
    tech: [
      "Deterministic scoring (Python)",
      "Synthetic plans/networks in reference_data.py",
      "State: Understood → Referred → Booked",
      "Optional LLM rationale later (not required today)",
      "MCP directory-mcp for providers/slots",
    ],
    scripts: [
      { path: "services/agents/navigator/scoring.py", role: "score_options() — in-network filter + rank" },
      { path: "services/orchestrator/app/reference_data.py", role: "Fictional Plan A/B/C + providers" },
      {
        path: "services/orchestrator/app/coordinator.py → navigate() / book() / reject_referral()",
        role: "Apply options + booking",
      },
      { path: "apps/web/app/patient/[caseId]/page.tsx", role: "Show options + Book" },
      { path: "mcp-servers/directory-mcp/server.py", role: "MCP list_providers / search_slots" },
    ],
    resolve: `Resolved when patient selects an in-network option and state=Booked (or coordinator re-routes after reject). GC-05 asserts org-gastro-oon never appears.`,
    demo: "Fatima: pass teach-back → see in-network cards → Book. Or GC-05 FIT case.",
    relatedState: "Understood → Referred → Booked (or ReferralRejected → Referred)",
    abbrUsed: ["GP", "OON", "LLM", "MCP", "FIT", "GC-01…"],
  },
  {
    slug: "result-card-teachback",
    num: "F4",
    title: "AR/EN result card + teach-back",
    oneLiner: "Explain the result in AR (Arabic) or EN (English), then check they understood.",
    what: `**Result card** = approved plain-language message (urgency, next step, “not a diagnosis”) in AR (Arabic) and/or EN (English) with RTL (right-to-left) layout when Arabic. **Teach-back** = 2 multiple-choice questions so the patient proves understanding before booking. Fail twice → human callback — a HITL gate, not more spam.`,
    tackle: `Load YAML template by result class + language. Fill tokens. Optionally rewrite via Microsoft Agent Framework (AF) + Azure OpenAI in Azure AI Foundry; if unsafe/unavailable → static template. Guardrails: no-diagnosis lexicon + optional Content Safety. Send → PatientNotified. Score teach-back; pass → Understood; 2 fails → HumanCallback + HITL.`,
    tech: [
      "YAML templates (data/templates/*.yaml)",
      "AR/EN + RTL UI (patient PWA-style web app)",
      "Optional: AF → Azure OpenAI in Foundry",
      "Guardrails: no-diagnosis + Content Safety hook",
      "State: Owned → PatientNotified → Understood | HumanCallback",
    ],
    scripts: [
      { path: "data/templates/hba1c_urgent.yaml", role: "EN/AR body + teach-back questions" },
      { path: "data/templates/fit_positive.yaml", role: "FIT wording (no cancer claim)" },
      { path: "services/agents/comms/agent.py", role: "render + optional Foundry draft" },
      { path: "services/agents/common/guardrails.py", role: "no_diagnosis / content_safe" },
      {
        path: "services/orchestrator/app/coordinator.py → notify_patient() / submit_teachback()",
        role: "State + messages",
      },
      { path: "apps/web/app/patient/[caseId]/page.tsx", role: "Card UI + teach-back choices" },
    ],
    resolve: `Resolved when teach-back passes (Understood) and navigator can run — or HITL callback task is created after two failures.`,
    demo: "Patient Fatima (AR) → read card → answer both questions correctly → options appear.",
    relatedState: "Owned → PatientNotified → Understood | HumanCallback",
    abbrUsed: ["AR", "EN", "AR/EN", "RTL", "HITL", "YAML", "AF", "Foundry", "Azure OpenAI", "UI", "PWA", "FIT"],
  },
  {
    slug: "guardrailed-reassurance",
    num: "F5",
    title: "Guardrailed reassurance",
    oneLiner: "Answer anxious questions from an approved KB (knowledge base) only — never diagnose.",
    what: `Patients ask “Do I have cancer?” after a positive FIT (faecal immunochemical test). Reassurance explains what the test means / doesn’t mean and the next step, with KB citations. It offers “talk to a person”. Red-flag language routes to a human immediately (HITL).`,
    tackle: `Keyword search over data/kb/*.md. Build extractive answer + preface “not a diagnosis”. Run no_diagnosis + red-flag checks. No KB hit → refuse and hand off. Target/pilot: Azure AI Search RAG (retrieval-augmented generation); today: local markdown RAG-lite. Scrub PII (personally identifiable information) from prompts when not needed.`,
    tech: [
      "Local KB markdown (RAG-lite)",
      "Guardrails lexicon",
      "Optional Azure AI Search + Foundry later",
      "Patient chat panel UI",
    ],
    scripts: [
      { path: "data/kb/fit_positive.md", role: "Approved FIT FAQ" },
      { path: "data/kb/hba1c.md", role: "Approved HbA1c FAQ" },
      { path: "services/agents/reassurance/agent.py", role: "search_kb + guarded answer" },
      { path: "services/agents/common/guardrails.py", role: "no_diagnosis / has_red_flag" },
      {
        path: "services/orchestrator/app/coordinator.py → reassure()",
        role: "API path + timeline AI row",
      },
      { path: "apps/web/app/patient/[caseId]/page.tsx", role: "Ask box" },
    ],
    resolve: `Resolved with a grounded non-diagnostic answer + citations, or HumanCallback / queue when red-flag or patient requests a person. GC-09 style checks.`,
    demo: "On patient page ask “Do I have cancer?” after FIT/HbA1c context — see KB-grounded reply.",
    relatedState: "Usually no state change; red flag may → HumanCallback",
    abbrUsed: ["KB", "FIT", "HITL", "RAG", "PII", "Foundry", "UI", "API", "AI", "HbA1c", "GC-01…"],
  },
  {
    slug: "escalation-ladder",
    num: "F6",
    title: "Escalation ladder (HITL)",
    oneLiner: "Critical or stuck cases climb coordinator → physician → programme lead — humans act (HITL).",
    what: `When triage is CRITICAL, the patient is unreachable, or an SLA (service level / time limit) breaches, Rabt does **not** invent clinical advice. It pages a human ladder and may send a generic “call us now” SMS (Short Message Service) **without result values**. No LLM on this path.`,
    tackle: `Escalation agent returns next ladder step (deterministic). Coordinator sets Escalated, enqueues board item, stores safe message. Human Handle escalation → Owned again. Timeouts use SAFE_DEFAULTS (e.g. next_ladder_step), never auto-close.`,
    tech: [
      "Deterministic ladder config (minutes placeholders)",
      "hitl.enqueue + board queue UI",
      "State: → Escalated → Owned (after human)",
      "No LLM on critical path",
    ],
    scripts: [
      { path: "services/agents/escalation/ladder.py", role: "Steps + safe SMS texts" },
      { path: "services/orchestrator/app/hitl.py", role: "enqueue, approvals, SAFE_DEFAULTS" },
      {
        path: "services/orchestrator/app/coordinator.py (CRITICAL branch + human_handle_escalation)",
        role: "Wire ladder",
      },
      { path: "apps/web/app/board/page.tsx", role: "Coral queue + Handle escalation" },
      { path: "services/orchestrator/app/main.py → /queue, /escalation/handle", role: "API" },
    ],
    resolve: `Resolved when a human handles the queue item and state returns to Owned (or next ladder step if timeout). GC-02: Escalated + SMS includes_values=false.`,
    demo: "Guest → Coordinator Sara → open CRITICAL case → Handle escalation (HITL).",
    relatedState: "Triaged/Unreachable → Escalated → Owned",
    abbrUsed: ["HITL", "SLA", "SMS", "LLM", "UI", "API", "GC-01…"],
  },
  {
    slug: "evidence-closure",
    num: "F7",
    title: "Evidence-gated closure",
    oneLiner: "A case closes only with real evidence — or a signed human decision. Target: 0 false closures.",
    what: `“Done” is not a vibe. Closure needs attended encounter + outcome note/document, **or** a human reason code with 4-eyes HITL approval (two different humans). Premature close attempts are blocked and list what’s missing. This is a KPI (key performance indicator) judges care about.`,
    tackle: `Closure verifier checks evidence dict. If closable → Closed (or ClosedByHuman). If not → bounce ClosurePending → Owned / keep open + timeline “blocked”. Exceptional path: request_approval required=2 distinct users.`,
    tech: [
      "Deterministic verifier",
      "State: Attended → ClosurePending → Closed | Owned",
      "HITL 4-eyes for exceptions",
      "IllegalTransition if Closed without closure_ok",
    ],
    scripts: [
      { path: "services/agents/closure/verifier.py", role: "closable? missing list" },
      {
        path: "services/orchestrator/app/state_machine.py → transition()",
        role: "Closed requires evidence.closure_ok",
      },
      {
        path: "services/orchestrator/app/coordinator.py → mark_attended() / try_close()",
        role: "Evidence write + gate",
      },
      { path: "services/orchestrator/app/hitl.py → request_approval()", role: "4-eyes exceptional close" },
      { path: "apps/web/app/board/page.tsx", role: "Try close / Mark attended + close" },
      { path: "tests/golden/test_golden.py → test_gc10_*", role: "False-close blocked (GC-10)" },
    ],
    resolve: `Resolved when state=Closed with evidence, or ClosedByHuman after dual approval. Otherwise case stays open — GC-10.`,
    demo: "Board → booked GC-10 → Try close (blocked). Then Mark attended + close (opens).",
    relatedState: "ClosurePending → Closed | Owned; ClosedByHuman via human gate",
    abbrUsed: ["HITL", "KPI", "GC-01…"],
  },
  {
    slug: "audit-trail",
    num: "F8",
    title: "Audit trail (fact / calculated / AI)",
    oneLiner: "Every step is logged and labelled for RAI (responsible AI): fact vs calculated vs AI text.",
    what: `RAI (responsible AI) requirement: keep **recorded facts** (results, accepts), **calculated findings** (triage rule, scores), and **AI-generated text** (message drafts, reassurance) visibly separate in the timeline and provenance. Prototype uses synthetic data only (no real PHI = protected health information).`,
    tackle: `On each _apply(), append provenance (from/to/actor/reason/fhir_status) and a timeline row with kind fact|calculated|ai based on actor. Board colours tags. Messages store ai_generated flag. Pilot: also FHIR Provenance/AuditEvent + OTEL (OpenTelemetry) traces.`,
    tech: [
      "Ledger JSON columns: provenance_json, timeline_json, messages_json",
      "UI tags: fact / calculated / AI",
      "Optional OTEL / Jaeger later",
      "Idempotency of ingest events",
    ],
    scripts: [
      { path: "services/orchestrator/app/ledger.py", role: "Persist provenance + timeline" },
      {
        path: "services/orchestrator/app/coordinator.py → _apply() / append_timeline()",
        role: "Classify kind + write",
      },
      { path: "apps/web/app/board/page.tsx", role: "Timeline with colour tags" },
      { path: "apps/web/app/patient/[caseId]/page.tsx", role: "AI badge on generated text" },
      { path: "services/orchestrator/app/state_machine.py", role: "Transition record shape" },
    ],
    resolve: `Always-on — a case is “auditable” when you can replay who moved it, which rule/prompt version, and whether text was AI. Not a terminal state; it’s the evidence for governance.`,
    demo: "Board → any case → Timeline: blue fact, gold calculated, violet AI.",
    relatedState: "All states — provenance grows each transition",
    abbrUsed: ["RAI", "AI", "PHI", "FHIR", "OTEL", "JSON", "UI"],
  },
];
