# AI gateway, token control and monitoring

Every model call goes through one path: `services/agents/common/llm_client.py` (API side), then the APIM AI gateway (`infra/terraform/modules/apim/policies/openai-api.xml.tftpl`), then Azure OpenAI.

## What happens on each call

| Step | Where | Notes |
|---|---|---|
| Kill switch | `llm_client.ai_enabled()` | `AI_ENABLED=false` (Terraform `ai_enabled`): no call, approved templates only. Counted as `kill_switch_skips`. |
| PII scrub | `agents/common/pii.py`, `language_pii.py` | Regex always, on system, user and source text. Then Azure AI Language PII when `LANGUAGE_PII_ENABLED` (Terraform `enable_language_pii`). If Language fails, the call is skipped and counted as `pii_fail_closed`; `language_pii_errors` and `language_pii_calls` are also tracked. |
| Prompt Shields | `agents/common/injection.py`, `content_safety.py` | For untrusted input (`rag_answer`, `classify_concern`, `translate`): deny-list, then Prompt Shields through APIM. Fails closed. |
| Prompt registry | `agents/common/prompts.py`, `data/prompts/*.yaml` | Only `reviewed: true` prompts are used; `id@version#sha` is sent as `x-rabt-prompt`. |
| Router | `agents/common/llm_router.py` | Small model first; per-task `max_tokens` and input cap; escalation on long input; one failover to the other tier. |
| Compression | `llm_router.compress()` | Collapses whitespace, drops repeated lines, trims at a sentence boundary. |
| Budget | `agents/common/ai_metrics.py` | `LLM_DAILY_TOKEN_BUDGET` (Terraform `llm_daily_token_budget`). Calls are refused before sending once it is used up. |
| Gateway | APIM | `azure-openai-token-limit` (`apim_tokens_per_minute`), token metrics by task/deployment, retries on 429/5xx, backend pool with circuit breaker. |
| Semantic cache | APIM + Redis | Only for requests marked `x-rabt-cacheable: true` (RAG answers). It is scoped by `x-rabt-cache-scope` (language and index version), so answers never mix across languages or KB versions. APIM returns `x-rabt-cache: hit` or `miss` and emits `SemanticCacheRequests{Result,Task}`. |
| Output checks | callers | Number grounding, no-diagnosis lexicon, Content Safety `text:analyze` (fails closed). |

## Router table

| Task | Tier (deployment) | max_tokens | Input cap | Cacheable |
|---|---|---|---|---|
| `comms_rewrite` | small (`chat-small`, gpt-4.1-mini) | 400 | 4000 chars | no |
| `classify_concern` | small | 5 | 1500 | no |
| `translate` | small | 400 | 3000 | no |
| `rag_answer` | strong (`chat-strong`, gpt-4o) | 350 | 9000 | yes |

- Small tasks move to the strong tier when their input exceeds `LLM_ROUTER_ESCALATE_CHARS` (default 6000).
- Crisis detection never uses a model.

## Foundry hub

Microsoft Foundry (`docs/foundry-ai.md`) is the **sole AI backend** behind APIM. App Insights is connected to the Foundry account; the project registers APIM as the AI gateway. Quotas and body-safe logging stay on **APIM**.

## Where to see it

- **API:** `GET /ai/metrics`, also shown on the admin page. It reports, per replica:
  - calls and tokens per deployment;
  - cache hit/miss counts and hit rate;
  - PII redactions, safety blocks and failovers;
  - budget use, router config, and the prompt list.
- **App Insights:** `APPLICATIONINSIGHTS_CONNECTION_STRING` is set by Terraform, and `app/monitoring.py` enables OpenTelemetry. The `rabt.ai` log events carry `customDimensions.ai_event`, `ai_task`, `ai_deployment`, `ai_prompt_tokens`, `ai_completion_tokens` and `ai_cache`. Prompt text is never logged.
- **APIM:** custom metrics in namespace `rabt-ai-gateway`: `Total Tokens`, `Prompt Tokens`, `Completion Tokens` and `SemanticCacheRequests`.

Useful queries (App Insights → Logs):

```kusto
// tokens per task and deployment, last 24h (API side)
traces | where timestamp > ago(24h) and customDimensions.ai_event == "llm_call"
| summarize prompt=sum(toint(customDimensions.ai_prompt_tokens)), completion=sum(toint(customDimensions.ai_completion_tokens)), calls=count()
  by task=tostring(customDimensions.ai_task), deployment=tostring(customDimensions.ai_deployment)

// semantic cache hit rate (gateway side)
customMetrics | where name == "SemanticCacheRequests" | summarize n=sum(valueSum) by result=tostring(customDimensions.Result)

// safety and routing events
traces | where customDimensions.ai_event in ("pii_redactions","pii_fail_closed","language_pii_errors","prompt_shield_blocks","content_safety_blocks","injection_blocks","failovers","budget_refusals")
| summarize count() by tostring(customDimensions.ai_event), bin(timestamp, 1h)
```

## Alerts (Terraform, `modules/monitoring`)

| Alert | Condition (default) |
|---|---|
| `safety-blocks` | > 5 Content Safety / Prompt Shields / injection blocks in 15 min |
| `llm-errors` | > 5 LLM or Content Safety errors in 15 min |
| `budget-refusals` | any refusal because of the daily token budget |
| `token-burn` | > 50,000 gateway tokens in 1 hour |

All four alerts email the budget contacts through the `ag-…` action group.
