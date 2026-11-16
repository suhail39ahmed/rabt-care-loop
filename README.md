# Rabt – AI Care-Loop Orchestrator for Abu Dhabi Screening Programs

![Rabt — no result left behind](docs/assets/rabt_thumbnail.jpg)

**Rabt: no result left behind.**  ·  Rabt (ربط) means "link" or "connection" in Arabic.

> **Prototype for the Future Health Digital Innovation Challenge.** Population Health track, challenge *Closing the Screening-to-Care Loop*.
> **Synthetic data only. Not a medical device. It does not diagnose or prescribe.** Clinical thresholds and time limits are illustrative and need clinician / DoH Abu Dhabi sign-off.

| Link | URL |
|---|---|
| Live web | https://rabt-web.onrender.com |
| API health | https://rabt-api-9oig.onrender.com/healthz |
| API docs | https://rabt-api-9oig.onrender.com/docs |
| Demo video | https://youtu.be/Qe9OF5uIzyg |
| Repo | https://github.com/suhail39ahmed/rabt-care-loop |

**Hosting:** Render free tier (Oregon). First request after idle can take ~20 s (cold start). SQLite reseeds on each API restart and is shared by all visitors.

---

## The problem

Population screening programmes find abnormal results such as raised HbA1c, critical blood pressure, a positive FIT or an abnormal cervical screen. The loop often leaks between the result and the follow-up care:

- nobody clearly owns the result
- the patient doesn't understand what to do next
- the suggested provider is outside the patient's insurance network
- referrals are rejected or patients don't attend
- cases are closed or forgotten without proof that care happened

## The solution

Rabt is an ownership and navigation layer that sits on top of FHIR-style data. Every actionable screening result becomes an **owned, time-boxed, insurance-aware case** that:

1. is checked for data quality and triaged by **versioned deterministic rules** (no LLM)
2. is handed to a named owner through an **accept/decline ownership handshake**, or goes straight to a **critical escalation queue**
3. is explained to the patient in **Arabic or English** using approved templates, with a "not a diagnosis" banner
4. confirms understanding with **teach-back** questions; two failures trigger a human callback
5. offers **in-network** follow-up options only, ranked by a deterministic navigator
6. **closes only with evidence** (attended encounter + outcome) or through a recorded human decision

Each timeline entry is labelled **fact**, **calculated** or **AI**, so reviewers can see what produced it.

## How Rabt works

![As-built architecture](docs/assets/architecture-asbuilt.png)

```mermaid
flowchart LR
  R[Screening result<br/>FHIR Observation] --> DQ[Data quality]
  DQ -->|bad data| Q1[Data query<br/>human fixes]
  DQ --> T[Deterministic triage<br/>rules v1.yaml]
  T -->|CRITICAL| E[Escalation queue<br/>SMS without values]
  T -->|URGENT / ROUTINE| O[Ownership handshake]
  T -->|unknown| H[Human triage queue]
  O --> C[Patient comms AR/EN<br/>template-first]
  C --> TB{Teach-back}
  TB -->|fails twice| CB[Human callback]
  TB -->|passes| N[In-network navigator]
  N --> B[Booked] --> A[Attended]
  A --> V{Closure verifier}
  V -->|evidence| CL[Closed]
  V -->|missing| O
```

The case lifecycle is a **state machine** with 20 states and an explicit allowed-transition table (`services/orchestrator/app/state_machine.py`). Illegal moves raise an error, and `Closed` needs verified evidence. Each state maps to a FHIR `Task.status`.

## Agents and roles

The **Coordinator** (`services/orchestrator/app/coordinator.py`) is the supervisor. It delegates each step to a specialist agent through a typed Pydantic contract (`DelegationResult` in `app/contracts.py`) and applies the proposed transition only if the state machine allows it.

| Agent | Path | Decides with | Role |
|---|---|---|---|
| Data Quality | `services/agents/data_quality/` | Deterministic | Missing units and contradictory repeats → data query |
| Triage | `services/agents/triage/` | Deterministic YAML rules | Urgency + pathway; unknown → human |
| Ownership | `services/agents/ownership/` | Deterministic | Assigns an owner who must accept or decline |
| Escalation | `services/agents/escalation/` | Deterministic, **no LLM** | Critical ladder; patient SMS never contains values |
| Patient Comms | `services/agents/comms/` | Approved templates; LLM optional | AR/EN message + teach-back |
| Navigator | `services/agents/navigator/` | Deterministic scoring | Ranks providers and excludes out-of-network ones |
| Reassurance | `services/agents/reassurance/` | Local approved KB | Cited, non-diagnostic answers; red flags → human |
| E-consult | `services/agents/econsult/` | Deterministic packet | Referral / e-consult summary |
| Closure Verifier | `services/agents/closure/` | Deterministic | Evidence gate before any closure |

**Where the LLM is (and isn't).** Triage, escalation, navigation scoring and closure never use an LLM. The Comms agent can optionally rewrite an approved template through Microsoft Agent Framework + Azure OpenAI when `AZURE_OPENAI_ENDPOINT` is set. The output must pass the no-diagnosis lexicon and Content Safety, otherwise the approved template is sent unchanged. **The local demo runs with templates only and needs no cloud account.**

## Human-in-the-loop gates

| Gate | Trigger | What happens |
|---|---|---|
| Critical escalation | Triage = CRITICAL | Queue item at ladder step 1 (coordinator); a human marks it handled |
| Human triage | No rule matches | Case is held for a human; no automated message |
| Data query | Data quality fails | Triage is held until the data is fixed |
| Ownership | Every non-critical case | Owner must accept; a decline goes to the queue |
| Teach-back callback | Two failed teach-backs | Human callback task |
| Consent withdrawn | Messaging consent off | Automation stops (`OnHoldConsent`); human-only path |
| Exceptional closure | Closing without evidence | Creates a 2-approver request; the same user can't vote twice |
| Timeouts | Approval past its due time | Safe defaults are defined and **never close a case** (`hitl.py` `SAFE_DEFAULTS`) |

See the **Limitations** section for what is still partial in these gates.

## Agentic delegation

- **Supervisor pattern:** one Coordinator, many narrow agents, each with a single responsibility.
- **Contracts:** every agent returns `case_id`, `step`, `status`, `proposed_transition`, `outputs` and `evidence_refs`, validated by Pydantic.
- **Propose, then verify:** agents only *propose* transitions. The state machine and the Closure Verifier decide.
- **Provenance:** every applied transition records the actor (`agent:*`, `human:*`, `patient:*`), the reason and the FHIR status.
- **MCP tools (stubs):** `mcp-servers/` defines scoped tools: `read_case_bundle`, `update_task_state`, `write_communication` (fhir-mcp), `list_providers`, `search_slots` (directory-mcp) and `send_message` (messaging-mcp). They aren't wired into the running demo yet.

## Golden cases and benchmark

Results measured locally with `pytest` / `make golden` / `make bench` (Python 3.12, seed 42):

| Suite | Result |
|---|---|
| All tests | **57 passed** locally (`uv run pytest -q`; CI runs the same suite) |
| Golden cases | **10/10** — see [benchmark/reports/golden_results.md](benchmark/reports/golden_results.md) |
| Safety tests | No-diagnosis lexicon (EN/AR), scrub_pii, grounded_numbers, tool scopes, red flags |
| State machine | Happy path, illegal transitions, closure needs evidence, human-only closure, property-based random walk |

| Benchmark (simulated, synthetic — seed 42, N=1000) | Rabt | Baseline |
|---|---|---|
| Closure rate | 100% | 100% |
| Median time to next step (min) | 104 | 331 |
| Critical escalation recall | 100% | ~53% |
| False closures | **0** | 129 |
| Fairness slices | age / sex / nationality / insurance in [benchmark/reports/report.md](benchmark/reports/report.md) |

All benchmark numbers are **simulated on synthetic data**, not real-world outcomes.

## Tech stack

| Layer | Used today | Target / pilot path |
|---|---|---|
| API / orchestration | Python 3.12, FastAPI, Pydantic v2, own state machine | Same, on Azure Container Apps |
| Case ledger | SQLite (aiosqlite) | PostgreSQL Flexible Server |
| Web | Next.js 16, React 19, TypeScript; Arabic RTL | Azure Static Web Apps |
| Rules / templates / KB | YAML rules, YAML AR/EN templates, Markdown KB | Clinician-approved versions |
| LLM (optional) | Microsoft Agent Framework + Azure OpenAI (off by default) | Azure AI Foundry |
| Safety | Lexicon guardrails; Azure AI Content Safety when configured | Content Safety always on |
| Tools | MCP Python SDK server stubs | Scoped MCP tools over AHDS FHIR |
| Local mocks | Docker Compose: HAPI FHIR R4, PostgreSQL, Mailpit, Jaeger | Azure Health Data Services, ACS, App Insights |
| Tests / CI | pytest, pytest-asyncio, Hypothesis; GitHub Actions | + lint, web build, security scans |
| Packaging | uv (`uv.lock`), npm | azd (`azure.yaml`, `infra/` scaffold) |

## Repository structure

```text
.
├── apps/web/                    # Next.js: home + personas, /patient/[caseId], /board, /admin
├── services/
│   ├── orchestrator/app/        # FastAPI main, coordinator, state machine, HITL, ledger, contracts, demo seed
│   ├── orchestrator/tests/      # state machine + triage unit tests
│   ├── agents/                  # triage, data_quality, ownership, escalation, comms, navigator,
│   │                            # reassurance, econsult, closure, common/guardrails.py
│   └── labs-mock/               # synthetic Observation generator + failure config
├── mcp-servers/                 # fhir-mcp, directory-mcp, messaging-mcp (stubs)
├── data/templates/              # approved AR/EN message templates (YAML)
├── data/kb/                     # reassurance knowledge base (Markdown)
├── benchmark/                   # golden_cases/, run_bench.py, config/, reports/
├── tests/golden/                # golden case tests
├── tests/safety/                # guardrail tests
├── docs/                        # architecture, responsible AI, data sources, assumptions, storyboard, assets
├── infra/main.bicep, azure.yaml # Azure scaffold (pilot path)
├── docker-compose.yml           # optional local mocks
├── scripts/dev-api.ps1, dev-web.ps1
└── Makefile                     # api | web | test | up
```

## Quick start

**Needs:** Python 3.12+, Node.js 22+, [uv](https://docs.astral.sh/uv/). Docker is optional.

### Windows PowerShell

```powershell
# Terminal 1 — API on http://localhost:8000 (creates .env from .env.example if missing)
.\scripts\dev-api.ps1

# Terminal 2 — web on http://localhost:3000
.\scripts\dev-web.ps1

# Tests
$env:PYTHONPATH = "services/orchestrator;services;."
uv run pytest -q
```

### bash / make

```bash
cp .env.example .env
uv sync --extra dev

make api     # FastAPI on :8000
make web     # Next.js on :3000 (run `npm install` in apps/web first)
make test    # pytest
make up      # optional: HAPI FHIR :8080, Postgres, Mailpit :8025, Jaeger :16686
```

Without make:

```bash
export PYTHONPATH=services/orchestrator:services:.
uv run uvicorn app.main:app --app-dir services/orchestrator --host 0.0.0.0 --port 8000
cd apps/web && npm install && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

The API rebuilds a fresh demo database (`data/rabt.db`) on every start, so guest mode is always predictable. Set `RABT_KEEP_DB=1` to keep it.

## Demo walkthrough

Open https://rabt-web.onrender.com (or http://localhost:3000). Guest mode — no login. Writes need the board persona header (`X-Rabt-Persona`).

1. **Fatima, patient (Arabic)** → patient card: RTL result with “not a diagnosis” → answer every teach-back question → book an in-network option.
2. **Dr Aisha** → `/board`: accept ownership of an awaiting case.
3. **Coordinator Sara** → `/board`: critical BP in the escalation queue (SMS has no values). Use **Advance +15m** to move the ladder, then **Handle escalation**.
4. **Evidence closure** → on a booked case: **Mark attended** (stays open) → **Record outcome** → closes with evidence.
5. **Two-person close** → on a case without evidence: **Request close** as persona A → switch persona → Approve twice with distinct non-requester personas → `ClosedByHuman`.
6. **KPIs** → `/admin`: false closures and critical recall on the synthetic seed.

API docs: https://rabt-api-9oig.onrender.com/docs

## API endpoints

Writes require `X-Rabt-Persona` (except ingest/webhook, which need `X-Rabt-Ingest-Secret` when configured). Reads are open for judges.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/healthz` | — | Health check |
| GET | `/demo` | — | Guest personas, seeded case IDs, disclaimer |
| POST | `/demo/advance?minutes=N` | persona | Fast-forward demo clock + ladder tick |
| GET | `/cases` · `/cases/{id}` | — | List / detail with timeline and provenance |
| POST | `/cases/ingest` | ingest secret | Observation intake |
| POST | `/webhook/fhir` | ingest secret | FHIR REST-hook intake |
| POST | `/cases/{id}/accept` · `/decline` | persona | Ownership handshake |
| POST | `/cases/{id}/notify` | persona | Patient message + teach-back |
| POST | `/cases/{id}/teachback` | persona | Teach-back answers (`min_length=1`) |
| POST | `/cases/{id}/book` | persona | Book navigator option |
| POST | `/cases/{id}/attend` | persona | Attendance only (not outcome) |
| POST | `/cases/{id}/outcome` | persona | Link outcome document / encounter ref |
| POST | `/cases/{id}/close` | persona | Evidence close or start two-person approval |
| POST | `/cases/{id}/consent/withdraw` | persona | Pause automation |
| POST | `/cases/{id}/reassure` | persona | KB reassurance or human |
| POST | `/cases/{id}/econsult` | persona | E-consult packet |
| POST | `/cases/{id}/escalation/handle` | persona | Stop ladder / take ownership |
| GET | `/queue` | — | HITL queue |
| GET | `/approvals` | — | Open 4-eyes requests |
| POST | `/approvals/{token}/decision` | persona | Approve / reject (identity from header) |
| GET | `/directory/providers` · `/plans` | — | Fictional directory |
| GET | `/kpis` | — | Computed false closures + critical recall |

## Responsible AI

- **No diagnosis:** a lexicon in English and Arabic blocks diagnostic claims, Azure AI Content Safety runs when configured, and every patient card carries a banner.
- **Deterministic safety path:** triage, escalation, navigation scoring and closure never use an LLM.
- **Human oversight:** critical queue, human triage, teach-back callback, consent pause and two-approver exceptional closure.
- **Fail safe:** if the LLM or Content Safety is unavailable, the approved template is sent; timeouts never auto-close.
- **Privacy:** critical SMS never contains result values; synthetic data only.
- **Transparency:** a provenance trail on every transition, and timeline items labelled fact / calculated / AI.

Details: [docs/responsible-ai.md](docs/responsible-ai.md) · [docs/assumptions-limitations.md](docs/assumptions-limitations.md) · [docs/data-sources.md](docs/data-sources.md)

## Synthetic data and mock disclaimers

- **All data is synthetic.** Demo patients and results are hand-crafted. No real personal or health data is used. [Synthea](https://github.com/synthetichealth/synthea) (Apache-2.0) is planned for the benchmark cohort and isn't required for the demo.
- **Malaffi and Sehatna are mocked.** Rabt has no access to Abu Dhabi's HIE or patient app. A local FHIR intake and the web patient app play those roles. Real integration is the pilot path.
- **Insurance plans, networks and providers are fictional.**
- **Not a medical device.** It does not diagnose, prescribe or replace clinical judgement. Triage thresholds, ladder delays and time limits are **illustrative placeholders**.

## Deploy / hosting

- **Live today:** Render free web services — [rabt-web](https://rabt-web.onrender.com) + [rabt-api](https://rabt-api-9oig.onrender.com). See `render.yaml`.
- **Docker:** `services/orchestrator/Dockerfile` and `apps/web/Dockerfile` (bind `0.0.0.0:$PORT`).
- **Azure (pilot path):** `infra/main.bicep` + `azure.yaml` scaffold for Container Apps later.
- Local: `make api` / `make web`, or `docker compose up`.

## Limitations

- **Demo auth only:** persona header + ingest secret — not Entra ID / UAE PASS yet ([docs/responsible-ai.md](docs/responsible-ai.md)).
- **MCP servers:** importable (`mcp>=1.1,<2`) and smoke-tested; not the live tool bus for the guest demo.
- **Ledger:** SQLite, single replica, ephemeral on free Render; reseeds on restart.
- **Deck PDF** link in Hack2Skill may still need a final export if the form requires a file upload.

## Done vs next

**Shipped:** FHIR BP shapes, two-person close, outcome evidence, board approvals, ladder tick + demo clock, real KPIs, golden 10/10, seeded benchmark, Render deploy, MCP pin, guardrail wiring, demo auth, CI jobs.

| Next (pilot) | Description |
|---|---|
| Data | Azure Health Data Services (FHIR R4) + Event Grid / Service Bus; Synthea cohort |
| AI | Azure AI Foundry + Content Safety always on for LLM paths |
| Identity | Entra ID / UAE PASS |
| Pilot site | Malaffi + Sehatna FHIR integration; clinician / DoH sign-off |

## Challenge context

Built for the **Future Health Digital Innovation Challenge**, **Population Health** track, challenge **Closing the Screening-to-Care Loop**. Judging covers health impact, technical depth, working demo, responsible AI, scalability, and the commercial / pilot path.

## License

MIT. See [LICENSE](LICENSE).
