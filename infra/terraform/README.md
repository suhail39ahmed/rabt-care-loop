# Rabt – Azure infrastructure (Terraform)

One Terraform stack provisions everything Rabt needs on Azure: the app hosting (Container Apps + ACR), the AI services (Azure OpenAI, AI Search, Content Safety, optional Redis semantic cache), the APIM AI gateway in front of them, and the security baseline.
GitHub Actions runs it (`.github/workflows/infra.yml`) and deploys the app images (`.github/workflows/deploy.yml`). See [First-time bootstrap](#first-time-bootstrap) for the few things created by hand.

```
Browser ──HTTPS──► ca-rabt-web-pilot (Next.js) ──HTTPS──► ca-rabt-api-pilot (FastAPI)
                                                                 │ api-key (Container Apps secret)
                                                                 ▼
                                          apim-rabt-pilot-sea (AI gateway, External VNet mode)
                                                                 │ managed identity, no service keys
                         ┌───────────────────────────┬───────────┴──────────────┐
                         ▼                           ▼                          ▼
              oai-rabt-pilot-aue          srch-rabt-pilot-sea        cs-rabt-pilot-aue
              (pool + circuit breaker)     (read-only KB index)        (Prompt Shields, moderation)
                 all behind private endpoints when enable_private_networking = true
```

> Never commit `terraform.tfvars`, `backend.hcl`, state, plans or keys (all are git-ignored).

## Layout

```
infra/terraform/
├── versions.tf / providers.tf      pinned Terraform + providers, azurerm remote backend
├── variables.tf                    inputs with validation
├── locals.tf                       naming convention, regions, tags
├── main.tf                         composition only: resource group, guardrails, module calls
├── outputs.tf                      names, URLs, security_summary (no secrets)
├── environments/pilot.tfvars       committed sizing for the pilot (no secrets, no personal data)
├── terraform.tfvars.example        personal values for local runs (subscription, emails, your IP)
├── backend.hcl.example             remote state location
├── tests/plan_mocked.tftest.hcl    offline plan tests (mocked providers)
└── modules/
    ├── network            VNet, 3 subnets + NSGs, private DNS zones, APIM public IP
    ├── private_endpoints  one endpoint per data service, DNS zone groups
    ├── monitoring         Log Analytics, App Insights, action group
    ├── identity           user-assigned identities (app, ingest)
    ├── rbac               least-privilege role assignments
    ├── keyvault           Key Vault (RBAC, purge protection, firewall)
    ├── keyvault_secret    secrets with expiry, written only when the vault is reachable
    ├── storage            KB document storage (no shared keys, TLS 1.2, versioning)
    ├── openai             Azure OpenAI accounts + router deployments
    ├── search             AI Search (RBAC only)
    ├── content_safety     Content Safety (Prompt Shields)
    ├── redis              Azure Managed Redis for the APIM semantic cache (optional)
    ├── apim               API Management AI gateway: APIs, policies, backends, product
    ├── container_apps     ACR + Container Apps environment + API and web apps
    ├── diagnostics        diagnostic settings to Log Analytics for every resource
    └── governance         budget, delete lock, Defender plans (optional)
```

## Naming convention

`<type>-<workload>-<environment>-<region code>[-<suffix>]`, with the Microsoft Cloud Adoption Framework abbreviations. With the committed `environments/pilot.tfvars`:

| Resource | Name |
|---|---|
| Resource group | `rg-rabt-pilot-sea` |
| API Management | `apim-rabt-pilot-sea` |
| Azure OpenAI | `oai-rabt-pilot-aue` (failover account: `oai-rabt-pilot-<region>-2`) |
| AI Search | `srch-rabt-pilot-sea` |
| Content Safety | `cs-rabt-pilot-aue` |
| Key Vault | `kv-rabt-pilot-sea` |
| Storage (KB docs) | `strabtpilotseakb` |
| Container registry | `crrabtpilotsea` |
| Container Apps environment | `cae-rabt-pilot-sea` |
| API / web apps | `ca-rabt-api-pilot` / `ca-rabt-web-pilot` |
| Log Analytics / App Insights | `log-rabt-pilot-sea` / `appi-rabt-pilot-sea` |
| Identities | `id-rabt-pilot-sea-app`, `id-rabt-pilot-sea-ingest` |
| VNet | `vnet-rabt-pilot-sea` |
| Budget / lock | `budget-rabt-pilot-sea` / `lock-rabt-pilot-sea` |
| **State (created by hand)** | `rg-rabt-tfstate-sea`, storage `strabttfstatesea`, container `tfstate`, key `rabt/pilot.tfstate` |

APIM, Key Vault, Storage, AI Search, Azure OpenAI and ACR names are global. If one is taken, set `name_suffix = "01"` (it is appended to those names only).

## What gets created

| Area | Module | Notes |
|---|---|---|
| Hosting | `container_apps` | ACR (admin user off) and a Container Apps environment (VNet-integrated when private). Two apps run as a user-assigned identity with AcrPull. The APIM key and the webhook secret are Container Apps secrets, never env values in images |
| LLM | `openai` | `small`, `strong` and `embedding` deployments for the LLM router. Local (key) auth is off |
| Retrieval | `search`, `storage` | RBAC-only Search. KB docs live in a private blob container; the ingestion script creates the index |
| Safety | `content_safety` | Prompt Shields + text analysis, local auth off |
| Gateway | `apim` | Three APIs (OpenAI, Search, Content Safety), one product and one subscription. Policies are in `modules/apim/policies/` |
| Cache (optional) | `redis` | `enable_semantic_cache` |
| Secrets | `keyvault`, `keyvault_secret` | RBAC, purge protection, 90-day soft delete. Secrets carry an expiry |
| Identity | `identity`, `rbac` | APIM, Search, app and ingestion identities with least-privilege roles |
| Network (default on) | `network`, `private_endpoints` | VNet with a PE subnet, APIM subnet and apps subnet (NSG on each). Private endpoints and DNS for AOAI, Search, KV, Storage, Content Safety and Redis |
| Observability | `monitoring`, `diagnostics` | Every resource sends allLogs + metrics to Log Analytics. App Insights masks IPs |
| Governance | `governance` + root guardrails | Budget alerts, optional delete lock, optional Defender plans, region allowlist, tags |

### APIM policies

- **Caller auth**: the APIM subscription key in the `api-key` header (`Ocp-Apim-Subscription-Key` for Content Safety). `apim_auth_mode = "entra_jwt"` or `"both"` adds `validate-jwt` against your tenant.
- **Backend auth**: `authentication-managed-identity`. The caller's key header is deleted before forwarding; no Azure service keys exist.
- **`azure-openai-token-limit`** per subscription and **`azure-openai-emit-token-metric`** to App Insights. No patient data goes into the dimensions.
- **Semantic cache** (optional): only for requests sent with `x-rabt-cacheable: true`, partitioned by `x-rabt-cache-scope`.
- **Resilience**: a priority-failover backend pool (primary → secondary) with a circuit breaker on 429/5xx, plus a retry.
- **Search**: only `/indexes/<kb index>/docs...` is forwarded, rate-limited. **Content Safety**: only `text:analyze` and `text:shieldPrompt`.
- **Logging**: body bytes are 0 in all four directions and the client IP isn't logged.

### Roles

| Principal | Role | Scope |
|---|---|---|
| APIM (system MI) | Cognitive Services OpenAI User / Cognitive Services User / Search Index Data Reader / Key Vault Secrets User | AOAI accounts / Content Safety / Search / Key Vault |
| Search (system MI) | Cognitive Services OpenAI User, Storage Blob Data Reader | primary AOAI, KB storage |
| Ingestion (user MI) | Storage Blob Data Reader, Search Index Data Contributor, Cognitive Services OpenAI User | KB storage, Search, primary AOAI |
| App (user MI) | AcrPull | container registry |
| Deployer (`grant_deployer_data_roles`) | Key Vault Secrets Officer, Search Index Data Contributor, Search Service Contributor, Storage Blob Data Contributor, Cognitive Services OpenAI User, AcrPush | for setup, image pushes and the ingestion script |

## First-time bootstrap

Three things exist outside this stack, because Terraform needs them before it can run:

1. **State storage**: `rg-rabt-tfstate-sea`, storage account `strabttfstatesea` (Standard_ZRS, TLS 1.2, no public blob access, shared keys off) and container `tfstate`. Commands are in `backend.hcl.example`.
2. **A GitHub OIDC identity**: an Entra app registration with two federated credentials for this repo, `pull_request` (plan) and `environment:pilot` (apply / deploy).
   - On the subscription it needs Contributor and Role Based Access Control Administrator, because the stack creates role assignments.
   - On the state account it needs Storage Blob Data Contributor.
   - No client secret.
3. **GitHub settings**:
   - An environment named `pilot` with required reviewers.
   - Repository variables:

| Variable | Example | Used by |
|---|---|---|
| `AZURE_CLIENT_ID` | app (client) ID of the OIDC app | infra, deploy |
| `AZURE_TENANT_ID` | Entra tenant ID | infra, deploy |
| `AZURE_SUBSCRIPTION_ID` | subscription ID | infra, deploy |
| `APIM_PUBLISHER_EMAIL` | `you@example.com` | infra |
| `BUDGET_CONTACT_EMAILS` | `["you@example.com"]` (JSON list) | infra |
| `DEPLOY_ENABLED` | `true`, after the first successful apply | deploy |
| `TF_STATE_RESOURCE_GROUP` / `TF_STATE_STORAGE_ACCOUNT` / `TF_STATE_CONTAINER` / `TF_STATE_KEY` | optional; default to the names above | infra |
| `AZURE_RESOURCE_GROUP` / `ACR_NAME` / `API_APP_NAME` / `WEB_APP_NAME` | optional; default to the pilot names | deploy |

Until the variables are set, both workflows skip their Azure jobs and stay green.

## Remote state

State lives in an Azure Storage account that you create once by hand. It uses Entra ID auth (`use_azuread_auth = true`), and shared keys are disabled on the account. Commands are in `backend.hcl.example`.

```bash
cp backend.hcl.example backend.hcl            # values already match the naming convention
terraform init -backend-config=backend.hcl
```

The GitHub workflow passes the same four values from repository variables (`TF_STATE_RESOURCE_GROUP`, `TF_STATE_STORAGE_ACCOUNT`, `TF_STATE_CONTAINER`, `TF_STATE_KEY`).

## Run locally

```bash
cd infra/terraform
az login && az account set -s <subscription-id>
cp terraform.tfvars.example terraform.tfvars   # subscription_id, emails, optional your IP
terraform init -backend-config=backend.hcl
terraform plan -var-file=environments/pilot.tfvars -out tfplan
terraform apply tfplan                          # APIM Developer takes 30-90 minutes the first time
```

Notes:

- **Model deployments can conflict (HTTP 409)** when created in parallel. Re-run `apply`, or use `-parallelism=1`.
- **Fully private with an empty `deployer_ip_allowlist`**: Terraform can't reach Key Vault, so it doesn't write the secrets there. The API still gets the APIM key, because Container Apps secrets are set through the control plane. Add your IP temporarily to run the ingestion script.
- The apps start on a placeholder image. The deploy workflow pushes the real images and switches the ports. Terraform ignores image and port changes after that.
- `ai_enabled = false` (the default) keeps every AI path on approved templates even though the gateway is wired. Turn it on for a recorded AI demo, then turn it off again.

## Region, model availability and cost

- **Regions:** primary **`southeastasia` (Singapore)**, fallback **`australiaeast`**. `allowed_locations` only allows these two, and the guardrail fails the plan otherwise. Checked against Microsoft Learn on 16 Nov 2026:

| Service | Southeast Asia | Australia East | Placed in | Source |
|---|---|---|---|---|
| gpt-4.1-mini (2025-04-14), Standard (regional) | no | yes | Australia East | [model region availability](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-region-availability) |
| text-embedding-3-small (1), Standard (regional) | no | yes | Australia East | same |
| gpt-4.1 (2025-04-14), Standard (regional) | no | no (Global/Provisioned only in APAC) | strong tier uses **gpt-4o (2024-11-20)** Standard in Australia East | same |
| Content Safety text moderation + Prompt Shields (standalone resource) | no | yes | Australia East | [Content Safety region availability](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/region-availability) |
| AI Search (Basic, semantic ranker) | yes | yes | Southeast Asia | [AI Search region support](https://learn.microsoft.com/en-us/azure/search/search-region-support) |
| APIM Developer, Container Apps, Key Vault, Storage, ACR, Log Analytics | yes | yes | Southeast Asia | [products by region](https://azure.microsoft.com/explore/global-infrastructure/products-by-region/) |

  - **Data processing is honest:** prompts and embeddings are processed in **Australia** (Azure OpenAI, Content Safety). Everything else is in **Singapore**.
  - Nothing is claimed to stay in the UAE. Rabt only sends synthetic, PII-scrubbed text to the models.
  - To use gpt-4.1 as the strong model, set its `sku_name = "GlobalStandard"`. Microsoft may then process prompts in any region, so the README and consent text must say that.
  - Check quota before you apply: `az cognitiveservices usage list -l australiaeast -o table`.
  - Model retirement: gpt-4.1-mini and gpt-4o (2024-11-20) retire on 14 Apr 2027.
- Deployment type: `Standard` processes in-region. `DataZoneStandard` stays within a data zone. `GlobalStandard` may process in any region.
- Rough monthly cost with the pilot defaults: APIM Developer ~US$50, AI Search Basic ~US$75, private endpoints ~US$40, Container Apps (two small always-on replicas) ~US$30–40, ACR Basic ~US$5, plus per-token AI usage and log ingestion. Setting `enable_private_networking = false` with `apim_sku_name = "BasicV2_1"` drops the endpoints but costs ~US$150 for APIM.
- The budget (`budget_amount`, default 100) emails at 50/80/100% actual and 100% forecast. **It alerts; it does not stop spend.**

## Validation (no Azure access needed)

```bash
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
terraform test                      # mocked providers, offline plan assertions
tflint --init && tflint --recursive
checkov -d . --config-file .checkov.yaml
```

CI runs the same checks in the `terraform` job. Skipped checkov rules are justified in `.checkov.yaml` and in inline `#checkov:skip` comments.

## Teardown

```bash
terraform destroy -var-file=environments/pilot.tfvars
```

- Remove the lock first if `enable_resource_lock = true`.
- Key Vault, Cognitive Services accounts and APIM are **soft-deleted**. Re-applying with the same names recovers them. To free the names, purge AOAI/Content Safety and APIM manually; the Key Vault can't be purged until its 90-day retention ends.
- Defender plans are subscription-wide, so `destroy` sets them back to Free for the whole subscription.
- The state storage (`rg-rabt-tfstate-sea`) isn't managed here.
