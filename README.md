# Rabt – AI Care-Loop Orchestrator for Abu Dhabi Screening Programs

**Rabt: no result left behind.**  Rabt (ربط) means "link" or "connection" in Arabic.

Rabt is a working prototype for the Future Health Digital Innovation Challenge, Population Health track, *Closing the Screening-to-Care Loop*. It turns an abnormal screening result into an owned, time-boxed, insurance-aware case, and it will not close that case until there is evidence that care happened, or a recorded human decision.

**Synthetic data only. Not a medical device. It does not diagnose or prescribe.** Clinical thresholds and time limits are illustrative and need clinician / Department of Health – Abu Dhabi sign-off. Nothing in this repository implies affiliation with, or integration into, DoH Abu Dhabi, ADPHC, Malaffi or Sahatna / Sehatna.

| | |
|---|---|
| Demo video | _To be added_ |
| Live web | https://ca-rabt-web-pilot.salmonwave-97737d51.southeastasia.azurecontainerapps.io |
| Live API | https://ca-rabt-api-pilot.salmonwave-97737d51.southeastasia.azurecontainerapps.io · [`/healthz`](https://ca-rabt-api-pilot.salmonwave-97737d51.southeastasia.azurecontainerapps.io/healthz) · [`/docs`](https://ca-rabt-api-pilot.salmonwave-97737d51.southeastasia.azurecontainerapps.io/docs) |
| Insurer agent | https://ca-rabt-insurer-pilot.salmonwave-97737d51.southeastasia.azurecontainerapps.io (scales to zero when idle) |

## Try the live demo

Guest access — no login. Board writes use the persona switcher (`X-Rabt-Persona`). **Reset demo** on `/board` restores the seed. AI is on for the Azure pilot (`AI_ENABLED=true`).

**Wow path:** Ravi’s abnormal FIT → cashless network option → one-tap book → the same case on the coordinator board.

- FIT / cashless (English): [`/patient/case-gc05-fit?lang=en`](https://ca-rabt-web-pilot.salmonwave-97737d51.southeastasia.azurecontainerapps.io/patient/case-gc05-fit?lang=en)
- Fatima’s patient card (Arabic, RTL): [`/patient/case-gc01-fatima`](https://ca-rabt-web-pilot.salmonwave-97737d51.southeastasia.azurecontainerapps.io/patient/case-gc01-fatima)
- Senior easy mode (Arabic): [`/patient/case-gc11-senior?lang=ar`](https://ca-rabt-web-pilot.salmonwave-97737d51.southeastasia.azurecontainerapps.io/patient/case-gc11-senior?lang=ar) — large text, one step per screen, read aloud, *call me instead*
- Coordinator board: [`/board`](https://ca-rabt-web-pilot.salmonwave-97737d51.southeastasia.azurecontainerapps.io/board) — critical BP ladder (**Advance +15m**), two-person close
- Follow-up tracker and claim status live on the board
- Split screen: [`/demo/split`](https://ca-rabt-web-pilot.salmonwave-97737d51.southeastasia.azurecontainerapps.io/demo/split) — the patient’s phone and the live board side by side
- Admin proof numbers: [`/admin`](https://ca-rabt-web-pilot.salmonwave-97737d51.southeastasia.azurecontainerapps.io/admin)
- Insurer A2A: [`/insurer`](https://ca-rabt-web-pilot.salmonwave-97737d51.southeastasia.azurecontainerapps.io/insurer)
- API OpenAPI: [`/docs`](https://ca-rabt-api-pilot.salmonwave-97737d51.southeastasia.azurecontainerapps.io/docs)

## What Rabt does

Population screening finds abnormal results — raised HbA1c, critical blood pressure, a positive FIT, an abnormal cervical screen. The loop often leaks between the result and follow-up care: nobody owns the result, the patient does not understand the next step, the suggested provider is out of network, or the case is closed without proof that care happened.

Rabt sits on top of FHIR-style intake and runs a 20-state machine with an allowed-transition table. For each actionable result it:

1. Checks data quality and triages with versioned deterministic rules (no LLM).
2. Hands the case to a named owner, or sends it straight to a critical escalation queue (15- and 45-minute ladder).
3. Explains the next step in the patient’s language with approved templates and a “not a diagnosis” banner.
4. Confirms understanding with teach-back; two failures trigger a human callback.
5. Ranks follow-up options with a payment path: cashless at a network hospital first, pay-and-claim when the plan covers it, out-of-network only when reimbursable or explicitly self-pay.
6. Closes only with evidence (attended encounter + outcome) or through a recorded two-person human decision.

Each timeline entry is labelled **fact**, **calculated** or **AI**.

## Key features

- **Deterministic safety path.** Triage, escalation, navigation scoring and closure never use an LLM.
- **Human-in-the-loop.** Critical queue, human triage, ownership handshake, teach-back callback, consent pause, and two-approver exceptional closure. Timeouts never auto-close a case.
- **Patient app.** Seven languages (English, Arabic, Hindi, Urdu, Malayalam, Filipino, Bengali), Arabic and Urdu RTL, Easy mode, an installable PWA, and an assistant that answers only from the approved knowledge base.
- **Document safety.** Uploaded claim files are checked before any model, index, insurer or coordinator sees their content. Active content or hidden instructions are quarantined and flagged on the board.
- **Signed insurer A2A.** A separate insurer agent exchanges eligibility, payment options and claims over HMAC-SHA256 signed HTTP. Replies are schema-checked; a bad reply is not used and goes to a coordinator.
- **AI, when on.** Comms, RAG answers and translation go through the APIM AI gateway to Azure AI Foundry (`gpt-4.1-mini` and `gpt-4o`). PII is scrubbed first. Output must pass the no-diagnosis lexicon and Content Safety, or the approved template is sent. A kill switch (`AI_ENABLED`) turns every AI path back to templates. Locally, AI is off by default.
- **Prompt-injection defence.** App deny-list and Prompt Shields, then the APIM `llm-content-safety` policy at the gateway.

## Stack

- **API / orchestration:** Python 3.12, FastAPI, Pydantic v2, SQLite ledger
- **Web:** Next.js 16, React 19, TypeScript, Arabic RTL
- **Hosting:** Azure Container Apps in Southeast Asia
- **AI:** Azure OpenAI in Australia East, behind APIM, with Content Safety, Language PII and AI Search (`rabt-kb-v2`)
- **Infra / CI:** Terraform and GitHub Actions (`ci.yml`, `infra.yml`, `deploy.yml`)

## Safety notes

- Synthetic data only. Demo patients, plans, networks and providers are fictional. No real personal or health data is used.
- Malaffi and Sehatna are mocked. Rabt has no live connection to Abu Dhabi’s HIE or patient app.
- Demo authentication is a persona header (`X-Rabt-Persona`) plus an ingest secret. It is not Entra ID or UAE PASS.
- Uploaded documents go through a gate (magic-byte type, size and page limits, PDF structure, EICAR, PII and injection checks) before use. Rejected files are quarantined, recorded on the case, and raised on the coordinator board.
- APIM publishes an `/insurer` API, but the live pilot calls the insurer container directly (`INSURER_A2A_URL` points at `ca-rabt-insurer-pilot`). Do not assume insurer traffic is routed through the gateway.
- The ledger is SQLite on a single replica and reseeds on container restart. PostgreSQL is the pilot path.
- MCP tool servers in `mcp-servers/` are smoke-tested stubs and are not on the guest demo path.

## Run locally

**Needs:** Python 3.12+, Node.js 22+, [uv](https://docs.astral.sh/uv/). Docker is optional.

### Windows PowerShell

```powershell
# Terminal 1 — API on http://localhost:8000
.\scripts\dev-api.ps1

# Terminal 2 — web on http://localhost:3000
.\scripts\dev-web.ps1
```

### bash / make

```bash
cp .env.example .env
uv sync --extra dev

make api     # FastAPI on :8000
make web     # Next.js on :3000 (run `npm ci --legacy-peer-deps` in apps/web first)
make test    # pytest
make up      # optional local mocks: HAPI FHIR, Postgres, Mailpit, Jaeger
```

The API rebuilds a fresh demo database (`data/rabt.db`) on every start. Set `RABT_KEEP_DB=1` to keep it. Local AI stays off unless you set `AI_ENABLED=true` and a provider in `.env`.

## Tests

```bash
# API, agents, golden cases, safety
export PYTHONPATH=services/orchestrator:services:.
uv run pytest -q

# Seeded benchmark (synthetic, seed 42)
make bench

# Web build and Playwright e2e (API on :8000, web on :3000)
cd apps/web && npm ci --legacy-peer-deps && npm run build
npx playwright test
```

CI runs on every pull request and on `main`: ruff, pytest (including golden cases), the seeded benchmark, pip-audit, gitleaks, npm audit, the web build, both Docker images, Terraform checks, and Playwright end-to-end tests.

Benchmark numbers in `benchmark/reports/` are simulated on synthetic data, not real-world outcomes. The last local run (seed 42, N=1000) scored 10/10 golden cases, 100% closure, 100% critical escalation recall and 0 false closures, against a baseline of 129 false closures and about 53% critical recall.

## Deploy

The live pilot is on Azure Container Apps in `rg-rabt-pilot-sea` (Southeast Asia; Foundry and Redis in Australia East). Infrastructure lives in [`infra/terraform`](infra/terraform). GitHub Actions plans and applies Terraform (`infra.yml`) and builds and rolls container images (`deploy.yml`).

## License

MIT. See [LICENSE](LICENSE).
