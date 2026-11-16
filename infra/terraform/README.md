# Rabt – Azure AI stack (Terraform)

This is the **supported** way to provision Rabt's Azure AI services (RAG, LLM router, Content Safety and the APIM AI gateway).
`infra/main.bicep` and `azure.yaml` at the repo root are early `azd` skeletons. They are kept for reference only and are not maintained.

Rabt itself (API + web) keeps running on **Render**. Azure hosts only the AI services, and Render reaches all of them through **one APIM gateway** with **one subscription key**.

```
Render (rabt-api) ──HTTPS + api-key──► APIM (AI gateway, public endpoint)
                                         │  managed identity (no service keys)
                                         ├──► Azure OpenAI  (pool: primary [+ secondary], circuit breaker)
                                         ├──► AI Search     (read-only, KB index)
                                         └──► Content Safety (text:analyze, text:shieldPrompt)
               all behind private endpoints when enable_private_networking = true
```

> Never commit `terraform.tfvars`, `backend.hcl`, state, plans or keys (all are git-ignored here).

## What gets created

| Area | Resources | Notes |
|---|---|---|
| Base | Resource group, Log Analytics, workspace-based App Insights | Every resource has a diagnostic setting to Log Analytics (allLogs + metrics) |
| Secrets | Key Vault (RBAC, purge protection, 90-day soft delete) | Holds the APIM subscription key. Terraform outputs never contain secrets |
| LLM | Azure OpenAI account(s) with `small`, `strong` and `embedding` deployments | Local (key) auth disabled. `openai_deployments` is shaped for the router (#101) |
| Retrieval | AI Search (`basic`/`standard`), optional semantic ranker | Key auth disabled; RBAC only. The index (`search_index_name`) is created by the ingestion script (#94) |
| Safety | Content Safety (Prompt Shields + text analysis) | Local auth disabled |
| Gateway | APIM (`Developer_1` default) with the three APIs, product `rabt` and one subscription | Policies in `policies/` |
| Cache (optional) | Azure Managed Redis (RediSearch) + APIM external cache | `enable_semantic_cache` |
| Docs | Storage account + private `kb-docs` container | No shared keys, no anonymous access, versioning + soft delete |
| Identity | APIM, Search and an ingestion identity, all with least-privilege roles | See [Roles](#roles) |
| Network (default on) | VNet, PE subnet, APIM subnet + NSGs, private endpoints + private DNS zones | AOAI, Search, KV, Storage (blob), Content Safety and Redis |
| Governance | Budget + action group, optional Defender plans, optional resource lock, tags, region allowlist | |

### APIM policies (`policies/`)

- **Caller auth**: by default the APIM subscription key in the `api-key` header (`Ocp-Apim-Subscription-Key` for Content Safety), which is what the SDKs already send. `apim_auth_mode = "entra_jwt"` or `"both"` adds `validate-jwt` against your tenant.
- **Backend auth**: `authentication-managed-identity`. The caller's key header is deleted before forwarding, and no Azure service keys exist.
- **`azure-openai-token-limit`**: tokens per minute per subscription (`apim_tokens_per_minute`).
- **`azure-openai-emit-token-metric`**: custom metrics in App Insights by API, operation, `x-rabt-task` header and deployment. No patient data goes into dimensions.
- **Semantic cache** (optional): runs only when the client sends `x-rabt-cacheable: true`, and is partitioned by `x-rabt-cache-scope`. Only send it for generic, non-personal prompts such as KB FAQ answers.
- **Resilience**: a backend pool (priority failover primary → secondary) with a circuit breaker on 429/5xx, plus a retry in the `backend` section.
- **Search**: only `/indexes/<kb index>/docs...` paths are forwarded, rate-limited per subscription.
- **Content Safety**: only `text:analyze` and `text:shieldPrompt` are forwarded.
- **Logging**: body bytes are 0 for all four directions, client IP is not logged, and only the `x-rabt-task` / `x-rabt-remaining-tokens` headers are kept.

### Roles

| Principal | Role | Scope |
|---|---|---|
| APIM (system MI) | Cognitive Services OpenAI User | each AOAI account |
| APIM | Cognitive Services User | Content Safety |
| APIM | Search Index Data Reader | Search |
| APIM | Key Vault Secrets User | Key Vault |
| Search (system MI) | Cognitive Services OpenAI User, Storage Blob Data Reader | primary AOAI, Storage (integrated vectorisation / indexers) |
| Ingestion (user MI) | Storage Blob Data Reader, Search Index Data Contributor, Cognitive Services OpenAI User | Storage, Search, primary AOAI |
| Deployer (`grant_deployer_data_roles`) | Key Vault Secrets Officer, Search Index Data Contributor, Search Service Contributor, Storage Blob Data Contributor, Cognitive Services OpenAI User | for setup and running the ingestion script locally. Set it to `false` after setup |

## Prerequisites

- Terraform >= 1.6 (>= 1.7 to run `terraform test`), Azure CLI, and optionally `tflint` and `checkov`.
- An Azure subscription where you can create role assignments (**Owner** or **User Access Administrator + Contributor**).
- Resource providers registered: `Microsoft.CognitiveServices`, `Microsoft.Search`, `Microsoft.ApiManagement`, `Microsoft.KeyVault`, `Microsoft.Storage`, `Microsoft.Network`, `Microsoft.OperationalInsights`, `Microsoft.Insights`, `Microsoft.Cache` (Redis), `Microsoft.Security` (Defender), `Microsoft.Consumption`.
- **Azure OpenAI quota** for each deployment (TPM in thousands = `capacity`) in the chosen region and SKU.

## Region and model availability (read before apply)

- The default region is **`uaenorth`** and `allowed_locations` enforces an allowlist. Model, SKU and feature availability in UAE North changes over time and is **not guaranteed**. Check before apply:
  - Azure OpenAI models / versions per region and deployment type: <https://learn.microsoft.com/azure/ai-foundry/openai/concepts/models>
  - `az cognitiveservices model list -l uaenorth -o table` and `az cognitiveservices usage list -l uaenorth -o table` (quota)
  - Content Safety / Prompt Shields, APIM v2 tiers, Azure Managed Redis and AI Search semantic ranker availability per region.
- If a service isn't available in UAE North, move just that service with `location_overrides` (for example `{ openai = "swedencentral", content_safety = "swedencentral" }`). You can also add `openai_secondary_location` (for example `eastus2`) as a failover account in the APIM pool.
  **Data residency:** anything outside the UAE means patient-adjacent prompts are processed outside the UAE. Rabt only sends synthetic, PII-scrubbed text today, but you need a real residency and DoH review before any real data.
- **Deployment type matters:** `Standard` processes in the account's region. `DataZoneStandard` stays within a data zone (EU/US). `GlobalStandard` may process **in any Azure region**. The defaults are `Standard`.
- Private networking requires APIM in the same region as the VNet (`location`), which a guardrail enforces. Other services can be in other regions; their private endpoints still sit in the VNet.

## Cost caveats (rough, pay-as-you-go, check the pricing calculator)

| Item | Default | Rough monthly |
|---|---|---|
| APIM Developer_1 | yes | ~US$50 (no SLA, **30–90 min to create**, required for VNet injection on a budget) |
| APIM Premium (prod VNet) | no | ~US$2,800+ per unit |
| APIM BasicV2/StandardV2 | no (only with `enable_private_networking = false`) | ~US$150 / ~US$700 |
| AI Search Basic / S1 | Basic | ~US$75 / ~US$250 per SU |
| Private endpoints | 5 (6 with Redis) | ~US$7–8 each + data processed |
| Private DNS zones | 5–6 | < US$1 each |
| Azure Managed Redis Balanced_B0 | off | ~US$50–60 |
| Azure OpenAI / Content Safety | pay per token / call | depends on usage; token limit in APIM caps bursts |
| Log Analytics / App Insights | 30-day retention | per GB ingested |
| Defender plans | off | **subscription-wide**, per resource / transaction |

`enable_private_networking = true` (the default) costs roughly **US$40–50/month** for endpoints and DNS on top of the services, and forces a classic APIM SKU (Developer/Premium). For a quick, cheap demo you can set it to `false` together with `apim_sku_name = "BasicV2_1"`. That keeps managed identity + RBAC, but the services get public endpoints.

The budget (`budget_amount`, default US$100, scoped to the resource group) emails `budget_contact_emails` at 50/80/100% actual and 100% forecast. **It alerts only; it does not stop spend.**

## Deploy

```bash
cd infra/terraform
az login && az account set -s <subscription-id>

# 1. Remote state (once): see backend.hcl.example
cp backend.hcl.example backend.hcl   # edit
terraform init -backend-config=backend.hcl

# 2. Variables
cp terraform.tfvars.example terraform.tfvars   # edit: subscription_id, emails, regions, SKUs

# 3. Review and apply (APIM Developer takes 30-90 minutes)
terraform plan -out tfplan
terraform apply tfplan
```

Apply-time notes:

- **Model deployments on the same account can conflict (HTTP 409)** if created in parallel. If that happens, re-run `apply`, or use `terraform apply -parallelism=1`.
- **RBAC propagation**: a 90-second wait is built in before writing the Key Vault secret. If you still get a 403, re-run `apply`.
- **Fully private with an empty `deployer_ip_allowlist`**: Terraform can't reach Key Vault, so it doesn't write the secret. In that case read the APIM key directly, as shown below. To run the ingestion script from your machine, add your public IP (`curl ifconfig.me`) to `deployer_ip_allowlist` temporarily.
- Create the Search index and upload KB docs with the ingestion script (#94); Terraform only creates the empty service and container.

## Render environment variables

```bash
terraform output render_env      # non-secret values
```

| Render env var | Source |
|---|---|
| `AZURE_OPENAI_ENDPOINT` | `render_env.AZURE_OPENAI_ENDPOINT` (APIM gateway URL) |
| `AZURE_OPENAI_API_VERSION` | `render_env.AZURE_OPENAI_API_VERSION` |
| `AZURE_OPENAI_MODEL` / `AZURE_OPENAI_MODEL_STRONG` / `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | deployment names by router role |
| `AZURE_SEARCH_ENDPOINT` / `AZURE_SEARCH_INDEX` | APIM `/search` + index name |
| `CONTENT_SAFETY_ENDPOINT` | APIM gateway URL (the SDK appends `/contentsafety/...`) |
| `AZURE_OPENAI_API_KEY`, `AZURE_SEARCH_API_KEY`, `CONTENT_SAFETY_KEY` | **all the same APIM subscription key**, set as Render secrets (see below) |

Get the key without it ever appearing in Terraform output:

```bash
az keyvault secret show --vault-name "$(terraform output -raw key_vault_name)" \
  -n apim-rabt-subscription-key --query value -o tsv
# or, if the secret was not written (fully private):
az rest --method post \
  --url "https://management.azure.com$(terraform output -raw apim_subscription_resource_id)/listSecrets?api-version=2024-05-01" \
  --query primaryKey -o tsv
```

Paste it into the Render dashboard as a secret env var. Don't put it in `render.yaml`. To rotate, regenerate the key in APIM → Subscriptions, re-run `apply` to refresh the Key Vault copy, and update Render.

> The Rabt code currently reads `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_MODEL` / `CONTENT_SAFETY_ENDPOINT` and uses Entra credentials (`AzureCliCredential` / `DefaultAzureCredential`). Those work locally but not on Render. Wiring the key-based clients against the APIM endpoint is part of #93 / #98.

## Validation (no Azure access needed)

```bash
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
terraform test                      # mocked providers, offline plan assertions
tflint --init && tflint
checkov -d . --config-file .checkov.yaml
```

CI runs the same checks in the `terraform` job (checkov is soft-fail there). Skipped checkov rules are listed with reasons in `.checkov.yaml` and in inline `#checkov:skip` comments. Most are rules checkov can't evaluate because the value depends on `enable_private_networking`.

## Teardown

```bash
terraform destroy
```

- Remove the resource lock first if `enable_resource_lock = true`.
- Key Vault (purge protection, 90 days), Cognitive Services accounts and APIM are **soft-deleted, not purged**. Their names stay reserved, and re-applying with the same suffix recovers them. To free the names, purge the Cognitive Services accounts and APIM manually (`az cognitiveservices account purge`, `az apim deletedservice purge`). The Key Vault can't be purged until its retention period ends.
- Defender plans are subscription-wide. `destroy` sets them back to Free, which also affects other workloads in the subscription.
- Remote state storage is not managed here; delete it yourself if you no longer need it.

## Relationship to the rest of the repo

- `infra/main.bicep`, `infra/modules/` and `azure.yaml` are superseded by this folder.
- `render.yaml` is unchanged; Render stays the app host.
- Tracking: #92 (epic), #93 (Azure infra for RAG), #94 (ingestion), #98 (APIM AI gateway), #99 (PII scrubbing before LLM calls; the gateway logs no bodies), #100 (semantic cache), #101 (LLM router), #104 (Prompt Shields), #106 (agent security).
