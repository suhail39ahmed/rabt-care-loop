/** All abbreviations used in Rabt learn / product copy. */
export type Abbrev = {
  abbr: string;
  full: string;
  meaning: string;
  group: "clinical" | "product" | "tech" | "azure" | "demo";
};

export const ABBREVIATIONS: Abbrev[] = [
  // Clinical / screening
  { abbr: "HbA1c", full: "Hemoglobin A1c", meaning: "Blood marker used in metabolic / diabetes-related screening follow-up (not a diagnosis by itself).", group: "clinical" },
  { abbr: "BP", full: "Blood pressure", meaning: "Systolic/diastolic readings; extreme values can triage as CRITICAL.", group: "clinical" },
  { abbr: "FIT", full: "Faecal immunochemical test", meaning: "Stool test for hidden blood; positive means more checks may be needed — not “you have cancer”.", group: "clinical" },
  { abbr: "GP", full: "General practitioner / family physician", meaning: "Primary doctor who often becomes Task owner.", group: "clinical" },
  { abbr: "LOINC", full: "Logical Observation Identifiers Names and Codes", meaning: "Standard codes for lab/observation types (e.g. 4548-4 = HbA1c).", group: "clinical" },
  { abbr: "BI-RADS", full: "Breast Imaging-Reporting and Data System", meaning: "Mammography category scale; e.g. BI-RADS 4 needs specialist follow-up.", group: "clinical" },
  { abbr: "EFHAS", full: "Abu Dhabi adult screening programme (context)", meaning: "Referenced as a source of screening results Rabt can consume (illustrative in prototype).", group: "clinical" },
  { abbr: "ADPHC", full: "Abu Dhabi Public Health Centre", meaning: "Challenge stakeholder describing the screening-to-care loop gap.", group: "clinical" },
  { abbr: "DoH", full: "Department of Health (Abu Dhabi)", meaning: "Regulator / programme authority; clinical rules need their sign-off for real use.", group: "clinical" },

  // Product / process
  { abbr: "AR", full: "Arabic", meaning: "Patient language + RTL UI for Arabic-first personas (e.g. Fatima).", group: "product" },
  { abbr: "EN", full: "English", meaning: "Patient language for English-preferring personas.", group: "product" },
  { abbr: "AR/EN", full: "Arabic / English", meaning: "Bilingual result cards and templates.", group: "product" },
  { abbr: "RTL", full: "Right-to-left", meaning: "Layout direction for Arabic pages.", group: "product" },
  { abbr: "HITL", full: "Human-in-the-loop", meaning: "Automation pauses; a human must act (accept, escalate, callback, 4-eyes close).", group: "product" },
  { abbr: "HOTL", full: "Human-on-the-loop", meaning: "Human oversees but does not block every step (contrast with HITL gates).", group: "product" },
  { abbr: "SLA", full: "Service level agreement (time limit)", meaning: "Illustrative due times per urgency (e.g. hours to act); breaches escalate.", group: "product" },
  { abbr: "OON", full: "Out-of-network", meaning: "Provider not covered by the patient’s fictional insurance plan/network.", group: "product" },
  { abbr: "KB", full: "Knowledge base", meaning: "Approved FAQ markdown (or Search index) reassurance may quote.", group: "product" },
  { abbr: "RAI", full: "Responsible AI", meaning: "Safety, consent, audit, no-diagnosis, fairness controls.", group: "product" },
  { abbr: "SC-01…", full: "Scenario ID", meaning: "Named demo journeys (e.g. SC-01 happy path HbA1c).", group: "product" },
  { abbr: "GC-01…", full: "Golden case ID", meaning: "Hand-written test cases with fixed expected outcomes (GC-01…GC-10).", group: "demo" },
  { abbr: "F1–F8", full: "Feature 1–8", meaning: "The eight capabilities Rabt adds (intake → audit trail).", group: "product" },
  { abbr: "UC", full: "Use case", meaning: "Product use-case IDs in the solution plan.", group: "product" },
  { abbr: "PWA", full: "Progressive web app", meaning: "Installable mobile web app pattern for the patient UI.", group: "product" },

  // Tech
  { abbr: "LLM", full: "Large language model", meaning: "Generative AI for text (comms/reassurance). Never decides triage/closure in Rabt.", group: "tech" },
  { abbr: "AI", full: "Artificial intelligence", meaning: "In timelines: AI-generated text (vs recorded fact / calculated finding).", group: "tech" },
  { abbr: "DQ", full: "Data quality (agent)", meaning: "Checks missing values/units and contradictions before triage.", group: "tech" },
  { abbr: "API", full: "Application programming interface", meaning: "HTTP endpoints the UI and mocks call (FastAPI).", group: "tech" },
  { abbr: "HTTP", full: "Hypertext Transfer Protocol", meaning: "Web request protocol for ingest/webhooks.", group: "tech" },
  { abbr: "JSON", full: "JavaScript Object Notation", meaning: "Data format for API bodies and ledger fields.", group: "tech" },
  { abbr: "YAML", full: "YAML Ain’t Markup Language", meaning: "Human-readable config for triage rules and message templates.", group: "tech" },
  { abbr: "UI", full: "User interface", meaning: "Patient app, board, learn pages.", group: "tech" },
  { abbr: "UX", full: "User experience", meaning: "How the product feels to patients/clinicians.", group: "tech" },
  { abbr: "FHIR", full: "Fast Healthcare Interoperability Resources", meaning: "HL7 standard for health data (Patient, Observation, Task, …).", group: "tech" },
  { abbr: "R4", full: "FHIR Release 4", meaning: "FHIR version Rabt targets.", group: "tech" },
  { abbr: "HAPI", full: "HAPI FHIR server", meaning: "Open-source FHIR server used locally as Malaffi stand-in.", group: "tech" },
  { abbr: "MCP", full: "Model Context Protocol", meaning: "Standard for scoped agent tools (fhir-mcp, directory-mcp, messaging-mcp).", group: "tech" },
  { abbr: "RAG", full: "Retrieval-augmented generation", meaning: "Answer only from retrieved approved documents (reassurance KB).", group: "tech" },
  { abbr: "SMS", full: "Short Message Service", meaning: "Text message channel; critical SMS omits result values.", group: "tech" },
  { abbr: "DB", full: "Database", meaning: "SQLite locally (ledger); Postgres in Docker/Azure path.", group: "tech" },
  { abbr: "SQL", full: "Structured Query Language", meaning: "Query language for the ledger database.", group: "tech" },
  { abbr: "CI", full: "Continuous integration", meaning: "Automated tests on push (GitHub Actions).", group: "tech" },
  { abbr: "CD", full: "Continuous delivery/deployment", meaning: "Automated deploy path (azd / Actions).", group: "tech" },
  { abbr: "IaC", full: "Infrastructure as code", meaning: "Bicep/azd definitions for Azure resources.", group: "tech" },
  { abbr: "OIDC", full: "OpenID Connect", meaning: "Federated login for CI to Azure (no long-lived secrets).", group: "tech" },
  { abbr: "OTEL", full: "OpenTelemetry", meaning: "Tracing standard for agent/orchestrator spans.", group: "tech" },
  { abbr: "SDK", full: "Software development kit", meaning: "Libraries such as MCP SDK or Azure SDKs.", group: "tech" },
  { abbr: "CLI", full: "Command-line interface", meaning: "Tools like az, azd, uv.", group: "tech" },
  { abbr: "AF", full: "Microsoft Agent Framework", meaning: "Co-creator agent SDK used optionally for Foundry chat agents.", group: "tech" },
  { abbr: "PoC", full: "Proof of concept", meaning: "Prototype stage of Rabt for the challenge.", group: "demo" },
  { abbr: "E2E", full: "End-to-end", meaning: "Full-path tests (API + UI flows).", group: "tech" },
  { abbr: "KPI", full: "Key performance indicator", meaning: "Metrics like critical-escalation recall, false closures.", group: "product" },

  // Azure / platforms
  { abbr: "Azure OpenAI", full: "Azure OpenAI Service", meaning: "Hosted chat models used via Foundry for safe text rewrite.", group: "azure" },
  { abbr: "Foundry", full: "Azure AI Foundry (Microsoft Foundry)", meaning: "Azure AI platform hosting models, safety, evals; Rabt’s LLM home.", group: "azure" },
  { abbr: "AHDS", full: "Azure Health Data Services", meaning: "Managed FHIR in Azure (cloud Malaffi-shaped path).", group: "azure" },
  { abbr: "ACS", full: "Azure Communication Services", meaning: "Optional email/SMS provider for cloud demos.", group: "azure" },
  { abbr: "Entra ID", full: "Microsoft Entra ID (formerly Azure AD)", meaning: "Identity for staff and managed identities.", group: "azure" },
  { abbr: "SWA", full: "Azure Static Web Apps", meaning: "Hosting option for frontends.", group: "azure" },
  { abbr: "azd", full: "Azure Developer CLI", meaning: "Provision + deploy helper for the Azure skeleton.", group: "azure" },

  // Abu Dhabi systems
  { abbr: "Malaffi", full: "Abu Dhabi Health Information Exchange (HIE)", meaning: "Connected records network; prototype uses HAPI/synthetic stand-in.", group: "clinical" },
  { abbr: "Sehatna", full: "Abu Dhabi patient health app", meaning: "Patient channel; Rabt patient UI plays this role in the prototype.", group: "clinical" },
  { abbr: "HIE", full: "Health information exchange", meaning: "Shared clinical data network across providers.", group: "clinical" },
  { abbr: "EMR", full: "Electronic medical record", meaning: "Clinic system of record; Rabt does not replace it.", group: "clinical" },
  { abbr: "PII", full: "Personally identifiable information", meaning: "Data that identifies a person; scrubbed from LLM prompts when not needed.", group: "tech" },
  { abbr: "PHI", full: "Protected health information", meaning: "Health data tied to a person; prototype uses synthetic data only.", group: "tech" },
];

export const ABBREV_GROUPS: Array<{ id: Abbrev["group"]; label: string }> = [
  { id: "clinical", label: "Clinical & Abu Dhabi" },
  { id: "product", label: "Product & process" },
  { id: "tech", label: "Technology" },
  { id: "azure", label: "Azure / Microsoft" },
  { id: "demo", label: "Demo & tests" },
];
