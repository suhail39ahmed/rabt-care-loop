# Microsoft Foundry hub (pilot)

Rabt keeps **APIM as the AI gateway** for production calls (OpenAI, Content Safety, Language PII, Search). **Foundry** (`kind=AIServices`) is the governed **portal + monitoring hub** so Content Safety, Language PII, evals and future agents share one Azure surface with App Insights / Log Analytics diagnostics.

```
Rabt API ──► APIM AI gateway ──► OpenAI / Content Safety / Language / Search
                    │                      ▲
                    │                      │ (same RG; Foundry portal for CS/PII/evals)
                    ▼                      │
              App Insights ◄──────── Foundry (AIServices + project)
```

## Why both

| Piece | Role |
|---|---|
| APIM | TPM limits, MI auth, no body logs, token metrics, failovers |
| Foundry | Studio for Content Safety / Language PII / evals; project boundary; improve-over-time in portal |
| App Insights | Traces + custom `ai_event` dims from the API; APIM gateway metrics |

Foundry does **not** replace the orchestrator or MCP-as-the-app. Optional Foundry MCP tools stay off the demo path.

## Terraform

- Module: `infra/terraform/modules/foundry`
- Flag: `enable_foundry` (pilot `true`)
- Name: `aif-rabt-pilot-aue` (australiaeast — Content Safety region)
- Project: `rabt-pilot`
- Keys off (`disable_local_auth`); Path B public + Entra, or private with the rest of the stack

Standalone `cs-*` and `lang-*` accounts remain the APIM backends (import-friendly). Foundry is the hub to operate and improve them over time; consolidating backends onto the Foundry endpoint is a later cutover.

## Ops

1. Portal → Foundry resource / project → Content Safety + Language playgrounds  
2. App Insights → APIM + cognitive diagnostics (no request bodies)  
3. Admin `/ai/metrics` for in-app counters  

See also: [ai-monitoring.md](ai-monitoring.md), [rag-azure.md](rag-azure.md).
