# Azure AI stack — manual create now, Terraform import later

This guide mirrors what `infra/terraform/` would create, so you can click through the Portal (or CLI) first and **import** into Terraform later without renaming everything.

Rabt **API + web stay on Render**. Azure holds only AI: LLM router models, embeddings, RAG search, PII/safety, and one APIM gateway.

```
Render rabt-api ── api-key ──► APIM (public gateway)
                                 ├─ Azure OpenAI  (small / strong / embedding)
                                 ├─ AI Search     (KB index)
                                 └─ Content Safety (analyze + Prompt Shields)
```

Recommended first pass: **public endpoints, no VNet** (cheaper, faster). Private networking can wait for pilot.

---

## 0. Decisions (fill these in)

| Setting | Recommended value | Notes |
|---|---|---|
| Subscription | *(your pay-as-you-go / credits)* | Need Owner or Contributor + User Access Admin |
| Region (primary) | `uaenorth` | If OpenAI / Content Safety missing, use `swedencentral` for those only |
| Environment | `pilot` | Used in every name |
| Name prefix | `rabt` | Keep short |
| Unique suffix | pick **5 chars**, e.g. `a7k2m` | Terraform uses random; you choose once and stick to it |
| Demo networking | **Public** for manual day-1 | Set private later |

**Resource group name (create this first):**

```text
rg-rabt-pilot-<suffix>
```

Example: `rg-rabt-pilot-a7k2m`

Tags on the RG (and every resource):

```text
app=rabt
environment=pilot
managed_by=manual   # change to terraform after import
repo=suhail39ahmed/rabt-care-loop
data=synthetic
owner=<you>
```

---

## 1. Resource group

Portal → **Resource groups → Create**

| Field | Value |
|---|---|
| Subscription | your subscription |
| Resource group | `rg-rabt-pilot-<suffix>` |
| Region | UAE North (`uaenorth`) |

CLI:

```bash
az group create -n rg-rabt-pilot-a7k2m -l uaenorth \
  --tags app=rabt environment=pilot managed_by=manual repo=suhail39ahmed/rabt-care-loop data=synthetic
```

---

## 2. Observability (do early)

### 2.1 Log Analytics

| Field | Value |
|---|---|
| Name | `log-rabt-pilot-<suffix>` |
| RG | `rg-rabt-pilot-<suffix>` |
| Region | uaenorth |
| Retention | 30 days |

### 2.2 Application Insights (workspace-based)

| Field | Value |
|---|---|
| Name | `appi-rabt-pilot-<suffix>` |
| Workspace | the Log Analytics above |

Save the **connection string** for later (Render / local). Never commit it.

---

## 3. Key Vault (holds APIM subscription key)

| Field | Value |
|---|---|
| Name | `kv-rabt-pilot-<suffix>` (≤24 chars; if too long use `kv-rabtpilot-<suffix>`) |
| RG / Region | same RG, uaenorth |
| Permission model | **Azure role-based access control** |
| Soft delete | 90 days |
| Purge protection | On (recommended) |
| Public access | Allow (for manual setup); tighten later |

Grant yourself **Key Vault Secrets Officer** on this vault.

---

## 4. LLM router — Azure OpenAI (small / strong / embedding)

### 4.1 Account

| Field | Value |
|---|---|
| Name | `aoai-rabt-pilot-primary-<suffix>` |
| Kind | `OpenAI` |
| Pricing | Standard S0 |
| Custom subdomain | `rabt-pilot-aoai-primary-<suffix>` |
| Network | All networks (manual demo) |
| Local auth (keys) | Prefer **Disabled** if you will use APIM MI; enable temporarily if Portal testing needs keys |

Optional failover account later: `aoai-rabt-pilot-secondary-<suffix>` in e.g. `eastus2`.

### 4.2 Deployments (router roles)

Create **three** deployments on the primary account. Names matter for the app router (`llm_router.py` / Terraform `openai_deployments`):

| Deployment name | Role | Model (check region availability) | Capacity (TPM thousands) |
|---|---|---|---|
| `chat-small` | small / fast | e.g. `gpt-4.1-mini` (or `gpt-4o-mini` if that’s what’s listed) | 20 |
| `chat-strong` | strong / RAG answer | e.g. `gpt-4.1` (or `gpt-4o`) | 10 |
| `embed` | embedding | `text-embedding-3-small` | 20 |

**Router policy (app):**

| Task | Tier | Deployment |
|---|---|---|
| `comms_rewrite`, `classify_concern`, `translate` | small | `chat-small` |
| `rag_answer` | strong | `chat-strong` |
| ingest / vectorise | embedding | `embed` |

Before creating, verify quota:

```bash
az cognitiveservices usage list -l uaenorth -o table
az cognitiveservices model list -l uaenorth -o table
```

If UAE North has no model, create the OpenAI account in `swedencentral` instead (same names).

---

## 5. PII + prompt injection — Content Safety

| Field | Value |
|---|---|
| Name | `cs-rabt-pilot-<suffix>` |
| Kind | Content Safety / Cognitive Services ContentSafety |
| Region | uaenorth **or** swedencentral if unavailable |
| Pricing | pay-as-you-go |

Enable / use:

- **Text Analyze** — hate/self-harm/sexual/violence severity (app `CS_MAX_SEVERITY`, default 2)
- **Prompt Shields** (`text:shieldPrompt`) — user prompt + document attack detection

**App-side PII (always on, no Azure required):**

- `agents/common/guardrails.scrub_pii` — phones + token map  
- `agents/common/pii.scrub_pii_uae` — Emirates ID `784-…`, Arabic name placeholders  

**Flow before every LLM call:**

1. Crisis / injection deny-list (`injection.py`)  
2. UAE PII scrub → reversible placeholders  
3. If `AI_ENABLED=false` → stop (templates only)  
4. Else call via APIM → OpenAI  
5. Optional Content Safety on model output; fail closed → template  

---

## 6. RAG — Storage + AI Search + index

### 6.1 Storage (KB docs)

| Field | Value |
|---|---|
| Storage account | `strabtpilot<suffix>` (≤24 chars, no hyphens) e.g. `strabtpilota7k2m` |
| Redundancy | LRS |
| Access | Disable shared key if you can use RBAC; for manual day-1 keys OK then rotate |
| Container | `kb-docs` (private, no anonymous) |
| Versioning + soft delete | On |

Upload approved markdown from `data/kb/*.md` (not `_pending/`).

### 6.2 AI Search

| Field | Value |
|---|---|
| Name | `srch-rabt-pilot-<suffix>` |
| Pricing | **Basic** (manual demo) |
| Semantic ranker | Free tier if offered |
| Auth | Prefer RBAC; keys OK for first ingest |

### 6.3 Index (create with script or Portal)

Index name (must match app / Terraform): **`rabt-kb`**

Suggested fields:

| Field | Type | Notes |
|---|---|---|
| `id` | String, key | e.g. `filename_chunkN` |
| `content` | String, searchable | chunk text |
| `source` | String, filterable | file name |
| `language` | String, filterable | `en` / `ar` |
| `contentVector` | Collection(Single) | dim = embedding model (1536 for text-embedding-3-small) |

Ingest:

```bash
# After OpenAI + Search exist and env is set:
python scripts/rag_ingest.py --dry-run   # shapes chunks
# Full embed+upload: extend script or use Portal “Import data” once
```

**App RAG modes:**

| `RAG_PROVIDER` | Behaviour |
|---|---|
| `off` (default) | Keyword FAQ in `reassurance` — no Azure |
| `mock` | Local `agents/rag/mock_retrieve.py` over `data/kb` |
| `azure` | Query Search via APIM; answer with `chat-strong`; citations required |

Human learning loop: unanswered → `data/kb/_pending/` → `scripts/kb_approve.py` → versioned file in `data/kb/` → re-ingest.

---

## 7. Optional semantic cache (Redis)

Skip for first manual pass (`enable_semantic_cache = false` in Terraform).

If you want it:

| Field | Value |
|---|---|
| Name | `redis-rabt-pilot-<suffix>` |
| SKU | Balanced_B0 (Managed Redis) or cheapest Cache for Redis |
| Modules | RediSearch if Managed Redis |

Cache key shape (app): `language|index_version|normalized_question` — only for **generic KB** answers (`x-rabt-cacheable: true`), never for patient-specific prompts.

---

## 8. AI gateway — API Management

This is the **only** public AI URL Render should call.

| Field | Value |
|---|---|
| Name | `apim-rabt-pilot-<suffix>` |
| Org / admin email | Rabt / your email |
| SKU (manual cheap) | **Developer** (slow create 30–90 min) **or** **Basic v2** if no VNet |
| Region | same as RG for simple setup |

### 8.1 APIs to add (three)

| API path prefix | Backend | Operations to allow |
|---|---|---|
| `/openai` | Azure OpenAI primary | Chat completions + embeddings for deployments above |
| `/search` | AI Search | Only `/indexes/rabt-kb/docs...` |
| `/contentsafety` (or root CS paths) | Content Safety | `text:analyze`, `text:shieldPrompt` only |

### 8.2 Product + subscription

| Item | Value |
|---|---|
| Product | `rabt` |
| Subscription | one subscription named `rabt-render` |
| Auth | Subscription key in header `api-key` (and `Ocp-Apim-Subscription-Key` if CS SDK needs it) |

Store the key in Key Vault secret name: **`apim-rabt-subscription-key`**.

### 8.3 Managed identity + roles

Enable **system-assigned MI** on APIM, then assign:

| Role | Scope |
|---|---|
| Cognitive Services OpenAI User | OpenAI account(s) |
| Cognitive Services User | Content Safety |
| Search Index Data Reader | AI Search |
| Key Vault Secrets User | Key Vault |

Backend policy idea: `authentication-managed-identity` + delete incoming `api-key` before forward (caller uses APIM key only).

### 8.4 Token limit / metrics (manual approx)

- Rate / token limit per subscription (e.g. ~60k TPM) on OpenAI API  
- App Insights metrics; **do not** log request/response bodies (PHI risk)  
- Optional header `x-rabt-task` for router task name  

---

## 9. Ingestion identity (for later scripts)

Create user-assigned managed identity:

| Field | Value |
|---|---|
| Name | `id-rabt-pilot-ingest-<suffix>` |

Roles:

| Role | Scope |
|---|---|
| Storage Blob Data Reader | KB storage |
| Search Index Data Contributor | Search |
| Cognitive Services OpenAI User | OpenAI (embeddings) |

---

## 10. Budget alert

| Field | Value |
|---|---|
| Scope | Resource group `rg-rabt-pilot-<suffix>` |
| Amount | 100 USD / month |
| Alerts | 50%, 80%, 100% actual + 100% forecast |
| Email | your address |

Alerts do **not** stop spend.

---

## 11. Wire Render (after gateway works)

On **rabt-api** environment:

| Env | Example |
|---|---|
| `AI_ENABLED` | `true` only when ready; keep `false` on public demo until judged |
| `LLM_PROVIDER` | `azure` or `openai_compatible` |
| `LLM_BASE_URL` | `https://apim-rabt-pilot-<suffix>.azure-api.net/openai` |
| `LLM_API_KEY` | APIM subscription key (from Key Vault) |
| `LLM_MODEL` | `chat-small` (default rewrite); router overrides per task |
| `CONTENT_SAFETY_ENDPOINT` | `https://apim-rabt-pilot-<suffix>.azure-api.net` |
| `RAG_PROVIDER` | `off` → `azure` when index is live |
| Search index | `rabt-kb` (via APIM `/search`) |

Confirm: `GET https://rabt-api-…/healthz` shows `ai_enabled`, `llm`, `llm_provider`.

---

## 12. Name checklist (copy/paste)

Replace `a7k2m` with your suffix.

| Resource | Exact name pattern |
|---|---|
| Resource group | `rg-rabt-pilot-a7k2m` |
| Log Analytics | `log-rabt-pilot-a7k2m` |
| App Insights | `appi-rabt-pilot-a7k2m` |
| Key Vault | `kv-rabt-pilot-a7k2m` |
| OpenAI | `aoai-rabt-pilot-primary-a7k2m` |
| Deployments | `chat-small`, `chat-strong`, `embed` |
| Content Safety | `cs-rabt-pilot-a7k2m` |
| Storage | `strabtpilota7k2m` |
| Blob container | `kb-docs` |
| AI Search | `srch-rabt-pilot-a7k2m` |
| Search index | `rabt-kb` |
| APIM | `apim-rabt-pilot-a7k2m` |
| APIM product | `rabt` |
| Ingest MI | `id-rabt-pilot-ingest-a7k2m` |
| Redis (optional) | `redis-rabt-pilot-a7k2m` |

---

## 13. Import into Terraform later

When Portal names match the patterns above:

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# set name_prefix=rabt, environment=pilot, location=uaenorth
# IMPORTANT: Terraform normally randomises the 5-char suffix.
# For import, either:
#   (a) set a fixed suffix via a small TF change / tfvars once, or
#   (b) import using the real resource IDs and accept state rename carefully.

terraform init -backend-config=backend.hcl
terraform import azurerm_resource_group.main /subscriptions/<sub>/resourceGroups/rg-rabt-pilot-a7k2m
# then import each resource by address — see terraform state list after a plan
# against an empty state with -generate-config-out (TF 1.5+) or manual import blocks
```

Practical tip: after manual create, run `az resource list -g rg-rabt-pilot-a7k2m -o table`, save IDs, and import one resource type at a time (`openai`, `search`, `apim`, …). Prefer **not** renaming Azure resources after they exist — import is much easier if Portal names already match Terraform’s scheme.

Full automated path (preferred once ready): fill `terraform.tfvars` and `terraform apply` instead of Portal — see `infra/terraform/README.md`.

---

## 14. Smoke test order

1. Portal: OpenAI chat playground on `chat-small`  
2. Portal: Content Safety text analyze  
3. Search: upload 1 doc → query index `rabt-kb`  
4. APIM: test console with subscription key → OpenAI via gateway  
5. Local: `AI_ENABLED=true` + APIM URL → notify path uses LLM only when safe  
6. Keep production demo `AI_ENABLED=false` until you want judges to see live model calls  

---

## Related repo docs

- `infra/terraform/README.md` — supported IaC path  
- `docs/rag-azure.md` — RAG / gateway map  
- `docs/agent-security.md` — OWASP-style controls  
- `docs/threat-model.md` — STRIDE  
- App: `services/agents/common/llm_client.py`, `llm_router.py`, `pii.py`, `injection.py`  
