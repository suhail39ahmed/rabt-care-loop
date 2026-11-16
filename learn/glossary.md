# Rabt abbreviations (A–Z)

Source: this file (`learn/glossary.md`). In-app glossary route was removed with `/learn`; keep studying here.

## Clinical & Abu Dhabi
| Abbr | Full | Meaning |
|---|---|---|
| ADPHC | Abu Dhabi Public Health Centre | Challenge stakeholder for the screening-to-care loop |
| BI-RADS | Breast Imaging-Reporting and Data System | Mammography category scale |
| BP | Blood pressure | Systolic/diastolic; extreme → CRITICAL |
| DoH | Department of Health (Abu Dhabi) | Rules need sign-off for real use |
| EFHAS | Abu Dhabi adult screening (context) | Example screening source |
| EMR | Electronic medical record | Rabt does not replace it |
| FIT | Faecal immunochemical test | Stool occult blood screen |
| GP | General practitioner / family physician | Typical case owner |
| HbA1c | Hemoglobin A1c | Metabolic screening marker |
| HIE | Health information exchange | Shared clinical network |
| LOINC | Logical Observation Identifiers Names and Codes | Lab/observation codes |
| Malaffi | Abu Dhabi HIE | Prototype uses HAPI stand-in |
| Sehatna | Abu Dhabi patient app | Patient UI plays this role |

## Product & process
| Abbr | Full | Meaning |
|---|---|---|
| AR / EN / AR/EN | Arabic / English | Bilingual cards |
| F1–F12 | Feature 1–12 | Capabilities Rabt adds (see modules 06–07) |
| HITL | Human-in-the-loop | Human must act before continue |
| A2A | Agent-to-agent | Structured insurer exchange (Demo Health Insurance) |
| APIM | Azure API Management | AI gateway in Terraform |
| HOTL | Human-on-the-loop | Oversight without blocking every step |
| KB | Knowledge base | Approved FAQ for reassurance |
| KPI | Key performance indicator | e.g. false closures, critical recall |
| OON | Out-of-network | Not on patient’s plan network |
| PWA | Progressive web app | Installable patient web UI |
| RAI | Responsible AI | Safety, consent, audit |
| RTL | Right-to-left | Arabic layout |
| SC / GC | Scenario / Golden case | Demo journeys / fixed tests |
| SLA | Service level agreement | Time limits per stage |
| UC | Use case | Solution-plan use-case IDs |

## Technology
| Abbr | Full | Meaning |
|---|---|---|
| AF | Microsoft Agent Framework | Optional Foundry agent SDK |
| AI | Artificial intelligence | Timeline label for generated text |
| API | Application programming interface | FastAPI HTTP endpoints |
| CI/CD | Continuous integration / delivery | GitHub Actions + deploy |
| CLI | Command-line interface | az, azd, uv |
| DB | Database | SQLite local / Postgres cloud |
| DQ | Data quality (agent) | Missing unit/value checks |
| E2E | End-to-end | Full-path tests |
| FHIR R4 | Fast Healthcare Interoperability Resources Release 4 | Health data standard |
| HAPI | HAPI FHIR server | Local FHIR server |
| HTTP | Hypertext Transfer Protocol | Web requests |
| IaC | Infrastructure as code | Bicep / azd |
| JSON | JavaScript Object Notation | API/ledger data format |
| LLM | Large language model | Text only — never triage/closure |
| MCP | Model Context Protocol | Scoped agent tools |
| OIDC | OpenID Connect | Federated CI→Azure auth |
| OTEL | OpenTelemetry | Tracing |
| PHI / PII | Protected health / personally identifiable info | Prototype is synthetic only |
| RAG | Retrieval-augmented generation | Answer from approved docs (mock/Azure; off by default) |
| SDK | Software development kit | Azure / MCP libraries |
| SMS | Short Message Service | Text alerts; no values if critical |
| STRIDE | Spoofing… Elevation | Threat-model categories (`docs/threat-model.md`) |
| TTS | Text-to-speech | Browser Listen button on patient messages |
| SQL | Structured Query Language | Ledger queries |
| UI/UX | User interface / experience | Apps people use |
| YAML | YAML Ain’t Markup Language | Rules + templates |

## Azure / Microsoft
| Abbr | Full | Meaning |
|---|---|---|
| ACS | Azure Communication Services | Optional email/SMS |
| AHDS | Azure Health Data Services | Managed FHIR |
| azd | Azure Developer CLI | Provision + deploy |
| Entra ID | Microsoft Entra ID | Staff identity |
| Foundry | Azure AI Foundry | Models, safety, evals |
| SWA | Azure Static Web Apps | Frontend hosting |
| Azure OpenAI | Azure OpenAI Service | Chat model hosting |
