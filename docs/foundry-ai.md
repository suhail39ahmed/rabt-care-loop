# Microsoft Foundry + APIM AI gateway (pilot)

**Foundry** (`kind=AIServices`) is the **sole AI backend**. **APIM** is the **AI gateway** in front of it (quotas, MI auth, no body logs, metrics). The Foundry project `rabt-pilot` is registered with that APIM gateway and with Application Insights for portal tracing and evals.

```
Rabt API ──► APIM AI gateway ──► Foundry (OpenAI + Content Safety + Language)
                 │                      │
                 │                      ├── project rabt-pilot
                 │                      │     ├── connection: APIM /openai (gateway)
                 │                      │     └── (portal evals / playgrounds)
                 ▼                      │
           App Insights ◄───────────────┘  (account connection + APIM logger)
```

| Piece | Role |
|---|---|
| APIM | Production AI gateway: TPM token limit, rate limits, MI to Foundry, no body logs, token metrics |
| Foundry account | Multi-service endpoint: chat/embed deployments, Content Safety, Language PII |
| Foundry project | Portal boundary; APIM gateway connection; evals against the same models |
| App Insights | API traces + APIM gateway metrics + Foundry account connection for portal/evals |

## Quotas and throttling

Enforced on **APIM** (not as a second Foundry control plane):

- OpenAI: `azure-openai-token-limit` (`apim_tokens_per_minute`)
- Content Safety / Language / Search: `rate-limit-by-key` on those APIs
- Deployment SKU `capacity` on Foundry model deployments (Azure-side TPM)

## Evals

- **Portal / Foundry:** use project `rabt-pilot` with App Insights connected (tracing).
- **Repo offline:** `scripts/rag_eval.py` and golden tests stay the CI regression path (`azure-ai-evaluation` optional for richer judges).

## MCP vs A2A

Demo agents are **signed A2A** (orchestrator ↔ insurer), not MCP. `mcp-servers/` stubs exist but `mcp_in_demo_path` is false — **do not** register those as Foundry MCP tool servers for the pilot. Optional Foundry Agent Service / MCP remains a later path.

## Terraform

- Module: `infra/terraform/modules/foundry` (account + deployments + project + App Insights connection)
- Root: `azapi_resource.foundry_apim_gateway` (project → APIM `/openai`)
- Flags: `enable_foundry` (required true); `enable_content_safety` / `enable_language_pii` only toggle APIM APIs onto the Foundry endpoint
- Name: `aif-rabt-pilot-aue` (australiaeast for model + CS availability)

## Ops

1. Portal → Foundry project → playgrounds / evals (traffic intended via APIM connection)  
2. App Insights → APIM + API + Foundry diagnostics (no request bodies)  
3. Admin `/ai/metrics` for in-app counters  

See also: [ai-monitoring.md](ai-monitoring.md), [rag-azure.md](rag-azure.md), [agent-security.md](agent-security.md).
