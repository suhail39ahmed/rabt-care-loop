# Microsoft Foundry + APIM AI gateway (pilot)

**Foundry** (`kind=AIServices`, `aif-rabt-pilot-aue`) is the **sole AI backend**. **APIM** (`apim-rabt-pilot-sea`) is the **AI gateway** in front of it (quotas, MI auth, no body logs, metrics, semantic cache). The Foundry project `rabt-pilot` is registered with that APIM gateway and with Application Insights for portal tracing and evals.

There is **no** separate Content Safety or Language cognitive account — both are served from the Foundry multi-service endpoint through APIM APIs `/contentsafety` and `/language`.

```
Browser ──► ca-rabt-web-pilot ──► ca-rabt-api-pilot
                                      │ AI_ENABLED=true · LLM_API_KEY
                                      ▼
                           apim-rabt-pilot-sea (AI gateway)
                           /openai · /contentsafety · /language · /search · /insurer
                                      │ MI to Foundry; Redis semantic cache (opt-in)
                 ┌────────────────────┴────────────────────┐
                 ▼                                         ▼
      aif-rabt-pilot-aue (Foundry)              srch-rabt-pilot-sea
      OpenAI + CS + Language                    (KB index)
      project rabt-pilot ← APIM connection
                 │
                 └──► appi-rabt-pilot-sea (App Insights)
```

| Piece | Role |
|---|---|
| APIM | Production AI gateway: TPM / rate limits, MI to Foundry, no body logs, token metrics, traffic policy fragments, insurer A2A product API |
| Foundry account | Multi-service endpoint: chat/embed deployments, Content Safety, Language PII |
| Foundry project | Portal boundary; APIM gateway connection; evals against the same models |
| Redis | `redis-rabt-pilot-aue` — APIM external cache `semantic-cache` (`llm-semantic-cache-*`, score `0.15`, TTL 7 days) |
| App Insights | API traces + APIM gateway metrics + Foundry account connection for portal/evals |

## Quotas and throttling

Enforced on **APIM** (not as a second Foundry control plane):

- OpenAI: token / rate limits (`apim_tokens_per_minute`)
- Content Safety / Language / Search: `rate-limit-by-key` on those APIs
- Deployment SKU `capacity` on Foundry model deployments (Azure-side TPM)

## Semantic cache

- Only when the caller sends `x-rabt-cacheable: true` (RAG answers from `llm_client`)
- Partitioned by `x-rabt-cache-scope` (language / index version)
- Lookup score-threshold **0.15**; store duration **604800 s (7 days)**
- Response header `x-rabt-cache: hit|miss|none`; metric `SemanticCacheRequests`

## Evals

- **Portal / Foundry:** project `rabt-pilot` with App Insights connected (tracing).
- **Repo offline:** `scripts/rag_eval.py` and golden tests stay the CI regression path.

## MCP vs A2A

Demo agents are **signed A2A** (orchestrator ↔ `ca-rabt-insurer-pilot`), also exposed on APIM `/insurer`. `mcp-servers/` stubs exist but `mcp_in_demo_path` is false — **do not** register those as Foundry MCP tool servers for the pilot.

## Terraform

- Module: `infra/terraform/modules/foundry` (account + deployments + project + App Insights connection)
- Root: `azapi_resource.foundry_apim_gateway_account` (account → APIM `/openai`; project connection is AML-owned when shared)
- Flags: `enable_foundry` (required true); `enable_content_safety` / `enable_language_pii` toggle APIM APIs onto the Foundry endpoint; `enable_semantic_cache`; `ai_enabled` (pilot **true**)
- Name: `aif-rabt-pilot-aue` (australiaeast for model + CS availability)

## Ops

1. Portal → Foundry project `rabt-pilot` → playgrounds / evals (gateway connection `apim-rabt-pilot-sea`)
2. App Insights → APIM + API + Foundry diagnostics (no request bodies)
3. Admin `/ai/metrics` or `GET /ai/metrics` for in-app counters
4. APIM → External cache `semantic-cache`; OpenAI API policy for `llm-semantic-cache-*`

See also: [ai-monitoring.md](ai-monitoring.md), [rag-azure.md](rag-azure.md), [agent-security.md](agent-security.md), [architecture.md](architecture.md).
