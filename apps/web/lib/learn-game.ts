export type Round = {
  q: string;
  choices: string[];
  answer: number;
  why: string;
};

export type Level = {
  id: string;
  title: string;
  blurb: string;
  diagram: string;
  rounds: Round[];
};

export type GameData = {
  title: string;
  tagline: string;
  levels: Level[];
  boss: {
    title: string;
    steps: Array<{ label: string; ok: string }>;
    win: string;
  };
};

export const GAME: GameData = {
  title: "Close the Loop",
  tagline: "Learn Rabt by playing — workflow, delegation, HITL",
  levels: [
    {
      id: "workflow",
      title: "Level 1 · Agentic workflow",
      blurb: "The case is a state machine. Only allowed edges work.",
      diagram: "/learn-assets/diagram-agentic-workflow.png",
      rounds: [
        {
          q: "Case just ingested. Data quality passed. What is the next legal state?",
          choices: ["Closed", "Triaged", "Booked", "ClosedByHuman"],
          answer: 1,
          why: "New → Triaged after DQ. You cannot jump to Closed without evidence.",
        },
        {
          q: "Triage says CRITICAL (very high BP). Next state?",
          choices: ["PatientNotified", "Escalated", "Closed", "Understood"],
          answer: 1,
          why: "CRITICAL goes to Escalated immediately — no LLM on this path.",
        },
        {
          q: "Owner accepted. Patient got the card and passed teach-back. Next?",
          choices: ["Closed", "DataQuery", "Understood → then Referred", "Escalated"],
          answer: 2,
          why: "PatientNotified → Understood → Referred (then book).",
        },
        {
          q: "Someone tries Booked → Closed with no attendance. Result?",
          choices: [
            "Allowed if LLM agrees",
            "Illegal — blocked by state machine / closure gate",
            "Auto-close after 1 hour",
            "Goes to Triaged",
          ],
          answer: 1,
          why: "False closures are blocked. Need Encounter + outcome, or human 4-eyes close.",
        },
      ],
    },
    {
      id: "delegation",
      title: "Level 2 · Agentic delegation",
      blurb: "The Coordinator is the supervisor. Agents propose; they don't freely rewrite state.",
      diagram: "/learn-assets/diagram-agentic-delegation.png",
      rounds: [
        {
          q: "HbA1c value arrived. Who classifies urgency?",
          choices: ["Comms LLM", "Triage agent (YAML rules)", "Patient app", "Navigator"],
          answer: 1,
          why: "Triage is deterministic rules — LLM must not decide urgency.",
        },
        {
          q: "Need an Arabic result card that never diagnoses. Who drafts it?",
          choices: [
            "Escalation ladder",
            "Closure verifier",
            "Comms agent (template ± Foundry)",
            "Data quality",
          ],
          answer: 2,
          why: "Comms is template-first; Foundry may rewrite reading level inside guardrails.",
        },
        {
          q: 'Patient asks "Do I have cancer?" after FIT+. Who answers?',
          choices: ["Triage agent", "Reassurance agent (KB only)", "Ownership agent", "labs-mock"],
          answer: 1,
          why: "Reassurance answers from approved KB with citations — never diagnoses.",
        },
        {
          q: "Agent returns proposed_transition = Closed but evidence is empty. Coordinator should…",
          choices: [
            "Apply it anyway",
            "Reject / raise to human — verifier fails",
            "Ask LangChain",
            "Delete the case",
          ],
          answer: 1,
          why: "DelegationResult must pass verify (allowed edge + evidence) before transition.",
        },
      ],
    },
    {
      id: "hitl",
      title: "Level 3 · Human-in-the-loop",
      blurb: "Humans are safety gates. Timeouts never auto-close a case.",
      diagram: "/learn-assets/diagram-hitl.png",
      rounds: [
        {
          q: "CRITICAL BP. Automation should…",
          choices: [
            "Let LLM decide SMS text with values",
            "Enqueue ladder, SMS without values, page coordinator",
            "Close the case",
            "Wait 7 days",
          ],
          answer: 1,
          why: "HITL critical path: no values on insecure channel, no LLM deciding.",
        },
        {
          q: "Teach-back failed twice. Next?",
          choices: [
            "Keep emailing forever",
            "HumanCallback — coordinator phones",
            "Mark Closed",
            "Switch to English only",
          ],
          answer: 1,
          why: "Two failures → human callback gate.",
        },
        {
          q: "Patient withdraws messaging consent. Automation…",
          choices: [
            "Continues quietly",
            "Pauses — OnHoldConsent, human-only path",
            "Deletes FHIR data",
            "Books anyway",
          ],
          answer: 1,
          why: "Consent withdrawal is an immediate HITL pause.",
        },
        {
          q: "Approval times out with no human vote. Safe default?",
          choices: [
            "Auto-close as success",
            "keep_open / next_ladder_step — never silent close",
            "Random close",
            "LLM picks",
          ],
          answer: 1,
          why: "SAFE_DEFAULTS in hitl.py never auto-close.",
        },
      ],
    },
  ],
  boss: {
    title: "Boss round · Close Fatima’s loop",
    steps: [
      { label: "Ingest HbA1c", ok: "Triaged → AwaitingOwner" },
      { label: "GP accepts", ok: "Owned" },
      { label: "Notify + teach-back", ok: "Understood" },
      { label: "In-network book", ok: "Booked" },
      { label: "Attend + note", ok: "Closed with evidence" },
    ],
    win: "Loop closed. No result left behind.",
  },
};
