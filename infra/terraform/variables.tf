# ---------------------------------------------------------------------------
# General
# ---------------------------------------------------------------------------
variable "subscription_id" {
  description = "Azure subscription to deploy into. Leave null to use ARM_SUBSCRIPTION_ID or the current `az account`."
  type        = string
  default     = null
}

variable "workload" {
  description = "Workload name used in every resource name (<type>-<workload>-<environment>-<region>)."
  type        = string
  default     = "rabt"

  validation {
    condition     = can(regex("^[a-z][a-z0-9]{1,7}$", var.workload))
    error_message = "workload must be 2-8 lowercase letters/digits and start with a letter."
  }
}

variable "name_suffix" {
  description = <<-EOT
    Optional short suffix appended to globally unique names (APIM, Key Vault, Storage, AI Search,
    Azure OpenAI, ACR) if one is already taken by someone else, e.g. "01". Empty = readable names only.
  EOT
  type        = string
  default     = ""

  validation {
    condition     = can(regex("^[a-z0-9]{0,4}$", var.name_suffix))
    error_message = "name_suffix must be 0-4 lowercase letters/digits."
  }
}

variable "environment" {
  description = "Environment name used in names and tags (e.g. demo, pilot)."
  type        = string
  default     = "pilot"

  validation {
    condition     = can(regex("^[a-z0-9]{2,6}$", var.environment))
    error_message = "environment must be 2-6 lowercase letters/digits."
  }
}

variable "location" {
  description = "Primary region (Singapore). Australia East is the fallback for services or models not offered in Southeast Asia."
  type        = string
  default     = "southeastasia"

  validation {
    condition     = contains(["southeastasia", "australiaeast"], var.location)
    error_message = "location must be one of the regions in local.region_codes (add a short code there to use another region)."
  }
}

variable "allowed_locations" {
  description = "Regions this stack may use. Every location and override must be in this list."
  type        = list(string)
  default     = ["southeastasia", "australiaeast"]
}

variable "location_overrides" {
  description = <<-EOT
    Per-service region overrides for services or models that are not available in var.location.
    Keys: openai, content_safety, apim, redis, search.
    Default: Azure OpenAI and Content Safety in Australia East, because Southeast Asia has no regional
    Standard deployment of gpt-4.1-mini / text-embedding-3-small and no standalone Content Safety
    text moderation or Prompt Shields (see infra/terraform/README.md, Regions).
  EOT
  type        = map(string)
  default = {
    openai         = "australiaeast"
    content_safety = "australiaeast"
  }

  validation {
    condition     = alltrue([for k in keys(var.location_overrides) : contains(["openai", "content_safety", "apim", "redis", "search"], k)])
    error_message = "location_overrides keys must be one of: openai, content_safety, apim, redis, search."
  }
}

variable "tags" {
  description = "Extra tags merged into the default tags."
  type        = map(string)
  default     = {}
}

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------
variable "enable_private_networking" {
  description = "Create a VNet, private endpoints and private DNS zones, and disable public access on data services. Adds cost (see README)."
  type        = bool
  default     = true
}

variable "vnet_address_space" {
  description = "Address space for the VNet (only used when private networking is on)."
  type        = list(string)
  default     = ["10.40.0.0/16"]
}

variable "subnet_private_endpoints_cidr" {
  description = "Subnet for private endpoints."
  type        = string
  default     = "10.40.1.0/24"
}

variable "subnet_apim_cidr" {
  description = "Subnet for API Management VNet injection (/27 or larger)."
  type        = string
  default     = "10.40.2.0/27"
}

variable "subnet_apps_cidr" {
  description = "Subnet for the Container Apps environment (/27 or larger, delegated)."
  type        = string
  default     = "10.40.4.0/27"
}

variable "deployer_ip_allowlist" {
  description = <<-EOT
    Public IPs/CIDRs (e.g. your own IP) allowed through the firewall of Key Vault, AI Search and Storage
    while private networking is on, so Terraform can write the APIM key secret and you can run the
    KB ingestion script from your machine. Empty = those services are fully private.
  EOT
  type        = list(string)
  default     = []
}

# ---------------------------------------------------------------------------
# Azure OpenAI
# ---------------------------------------------------------------------------
variable "openai_deployments" {
  description = <<-EOT
    Model deployments, keyed by deployment name. `role` tells the router which deployment serves which task class:
    small (intent, translation, rewording), strong (grounded RAG answers, call scripts), embedding.
    sku_name: Standard (regional processing), DataZoneStandard or GlobalStandard (data may be processed outside the region).
  EOT
  type = map(object({
    role          = string
    model_name    = string
    model_version = string
    sku_name      = string
    capacity      = number
  }))
  default = {
    "chat-small" = {
      role          = "small"
      model_name    = "gpt-4.1-mini"
      model_version = "2025-04-14"
      sku_name      = "Standard"
      capacity      = 20
    }
    "chat-strong" = {
      role          = "strong"
      model_name    = "gpt-4o"
      model_version = "2024-11-20"
      sku_name      = "Standard"
      capacity      = 10
    }
    "embed" = {
      role          = "embedding"
      model_name    = "text-embedding-3-small"
      model_version = "1"
      sku_name      = "Standard"
      capacity      = 20
    }
  }

  validation {
    condition     = alltrue([for d in values(var.openai_deployments) : contains(["small", "strong", "embedding"], d.role)])
    error_message = "Each deployment role must be small, strong or embedding."
  }

  validation {
    condition     = length([for d in values(var.openai_deployments) : d if d.role == "embedding"]) == 1
    error_message = "Exactly one deployment must have role = \"embedding\"."
  }

  validation {
    condition     = alltrue([for d in values(var.openai_deployments) : contains(["Standard", "DataZoneStandard", "GlobalStandard", "ProvisionedManaged"], d.sku_name)])
    error_message = "sku_name must be Standard, DataZoneStandard, GlobalStandard or ProvisionedManaged."
  }
}

variable "openai_secondary_location" {
  description = "Optional second Azure OpenAI account (same deployments) used as failover in the APIM backend pool. null = none."
  type        = string
  default     = null
}

variable "disable_local_auth" {
  description = "Disable API keys on Azure OpenAI, Content Safety and AI Search (Entra ID / managed identity only). Rabt reaches them through APIM."
  type        = bool
  default     = true
}

# ---------------------------------------------------------------------------
# Azure AI Search
# ---------------------------------------------------------------------------
variable "search_sku" {
  description = "AI Search tier: basic (demo/pilot) or standard (S1)."
  type        = string
  default     = "basic"

  validation {
    condition     = contains(["basic", "standard"], var.search_sku)
    error_message = "search_sku must be basic or standard."
  }
}

variable "search_semantic_ranker" {
  description = "Semantic ranker plan: disabled, free (1,000 queries/month) or standard (billed)."
  type        = string
  default     = "free"

  validation {
    condition     = contains(["disabled", "free", "standard"], var.search_semantic_ranker)
    error_message = "search_semantic_ranker must be disabled, free or standard."
  }
}

variable "search_replica_count" {
  description = "Search replicas (2+ for read SLA, 3+ for read/write SLA)."
  type        = number
  default     = 1
}

variable "search_partition_count" {
  description = "Search partitions."
  type        = number
  default     = 1
}

variable "search_index_name" {
  description = "Index name used by the KB ingestion script and Rabt (AZURE_SEARCH_INDEX)."
  type        = string
  default     = "rabt-kb-v2" # schema version suffix; a schema change means a new index (scripts/rag_ingest.py)
}

# ---------------------------------------------------------------------------
# Content Safety
# ---------------------------------------------------------------------------
variable "enable_content_safety" {
  description = "Create Azure AI Content Safety (text moderation + Prompt Shields)."
  type        = bool
  default     = true
}

# ---------------------------------------------------------------------------
# API Management (AI gateway)
# ---------------------------------------------------------------------------
variable "apim_sku_name" {
  description = "APIM SKU, e.g. Developer_1 (no SLA, VNet injection), BasicV2_1, StandardV2_1, Premium_1. Private networking needs Developer or Premium."
  type        = string
  default     = "Developer_1"

  validation {
    condition     = can(regex("^(Developer|BasicV2|StandardV2|Premium|PremiumV2)_[0-9]+$", var.apim_sku_name))
    error_message = "apim_sku_name must look like Developer_1, BasicV2_1, StandardV2_1 or Premium_1."
  }
}

variable "apim_publisher_name" {
  description = "Publisher name shown in APIM."
  type        = string
  default     = "Rabt"
}

variable "apim_publisher_email" {
  description = "Publisher / notification email for APIM."
  type        = string
}

variable "apim_auth_mode" {
  description = "How callers authenticate to the gateway: subscription_key (the Rabt API), entra_jwt (Entra ID token) or both."
  type        = string
  default     = "subscription_key"

  validation {
    condition     = contains(["subscription_key", "entra_jwt", "both"], var.apim_auth_mode)
    error_message = "apim_auth_mode must be subscription_key, entra_jwt or both."
  }
}

variable "apim_jwt_audience" {
  description = "Expected audience (app ID URI or client ID) when apim_auth_mode uses entra_jwt."
  type        = string
  default     = ""
}

variable "apim_tokens_per_minute" {
  description = "azure-openai-token-limit: tokens per minute per subscription."
  type        = number
  default     = 20000
}

variable "apim_search_calls_per_minute" {
  description = "Rate limit for the AI Search API per subscription."
  type        = number
  default     = 120
}

# ---------------------------------------------------------------------------
# Semantic cache (Azure Managed Redis)
# ---------------------------------------------------------------------------
variable "enable_semantic_cache" {
  description = "Create Azure Managed Redis (RediSearch) and the APIM semantic cache policies. Only requests sent with x-rabt-cacheable: true are cached."
  type        = bool
  default     = false
}

variable "redis_sku_name" {
  description = "Azure Managed Redis SKU."
  type        = string
  default     = "Balanced_B0"
}

variable "semantic_cache_score_threshold" {
  description = "azure-openai-semantic-cache-lookup score-threshold (lower = stricter match)."
  type        = number
  default     = 0.05
}

variable "semantic_cache_ttl_seconds" {
  description = "How long a cached answer lives (also invalidated by the index version in the cache scope header)."
  type        = number
  default     = 604800
}

# ---------------------------------------------------------------------------
# Storage, Key Vault, monitoring, governance
# ---------------------------------------------------------------------------
variable "storage_replication_type" {
  description = "Replication for the KB document storage account."
  type        = string
  default     = "ZRS"

  validation {
    condition     = contains(["LRS", "ZRS", "GRS", "GZRS"], var.storage_replication_type)
    error_message = "storage_replication_type must be LRS, ZRS, GRS or GZRS."
  }
}

variable "kb_container_name" {
  description = "Blob container for approved KB source documents."
  type        = string
  default     = "kb-docs"
}

variable "key_vault_secret_expiry_days" {
  description = "Expiry set on secrets written by Terraform (rotate before it)."
  type        = number
  default     = 180
}

variable "log_retention_days" {
  description = "Log Analytics retention in days."
  type        = number
  default     = 30

  validation {
    condition     = var.log_retention_days >= 30 && var.log_retention_days <= 730
    error_message = "log_retention_days must be between 30 and 730."
  }
}

variable "budget_amount" {
  description = "Monthly budget for the resource group, in the billing currency."
  type        = number
  default     = 100
}

variable "budget_contact_emails" {
  description = "Emails for budget and alert notifications."
  type        = list(string)

  validation {
    condition     = length(var.budget_contact_emails) > 0
    error_message = "Provide at least one budget_contact_emails address."
  }
}

variable "budget_start_date" {
  description = "Budget start (first day of a month, RFC3339). null = first day of the current month at first apply."
  type        = string
  default     = null
}

variable "enable_defender_plans" {
  description = "Enable Microsoft Defender for Cloud plans. These are subscription-wide and billed per resource."
  type        = bool
  default     = false
}

variable "defender_plans" {
  description = "Defender plans to enable when enable_defender_plans is true."
  type        = list(string)
  default     = ["AI", "Api", "KeyVaults", "StorageAccounts"]
}

variable "enable_resource_lock" {
  description = "Put a CanNotDelete lock on the resource group (remove it before terraform destroy)."
  type        = bool
  default     = false
}

variable "grant_deployer_data_roles" {
  description = "Give the identity running Terraform data-plane roles (Key Vault secrets, Search index, Blob data) for setup and ingestion."
  type        = bool
  default     = true
}

variable "openai_api_version" {
  description = "Azure OpenAI data-plane API version the Rabt API sends through APIM."
  type        = string
  default     = "2024-10-21"
}

# ---------------------------------------------------------------------------
# App hosting (Azure Container Apps + ACR)
# ---------------------------------------------------------------------------
variable "ai_enabled" {
  description = "Global AI kill switch for the deployed API (AI_ENABLED). false = every AI path stays on approved templates."
  type        = bool
  default     = false
}

variable "registry_sku" {
  description = "Azure Container Registry SKU: Basic, Standard or Premium."
  type        = string
  default     = "Basic"
}

variable "api_min_replicas" {
  description = "API replicas kept warm. Keep 1: the demo ledger is SQLite inside the container."
  type        = number
  default     = 1

  validation {
    condition     = var.api_min_replicas >= 0 && var.api_min_replicas <= 1
    error_message = "api_min_replicas must be 0 or 1 (single-writer SQLite ledger)."
  }
}

variable "web_min_replicas" {
  description = "Web replicas kept warm (0 = scale to zero, a few seconds cold start)."
  type        = number
  default     = 1
}

variable "llm_daily_token_budget" {
  description = "Daily token budget enforced by the API before each LLM call (prompt + completion, per replica). The APIM token limit is the hard per-minute cap."
  type        = number
  default     = 200000

  validation {
    condition     = var.llm_daily_token_budget >= 1000
    error_message = "llm_daily_token_budget must be at least 1000."
  }
}

variable "llm_router_escalate_chars" {
  description = "Small-model tasks escalate to the strong deployment when their input is longer than this many characters."
  type        = number
  default     = 6000
}

variable "enable_insurer_demo" {
  description = "Deploy the synthetic demo insurer as its own A2A agent (ca-<workload>-insurer-<env>), called over signed HTTP."
  type        = bool
  default     = true
}

variable "enable_kb_ingest_job" {
  description = "Create the Container Apps Job that indexes approved KB docs from blob storage into AI Search."
  type        = bool
  default     = true
}

variable "kb_ingest_cron" {
  description = "Schedule (UTC cron) for the KB ingestion job. Unchanged docs are skipped, so hourly runs are cheap."
  type        = string
  default     = "15 * * * *"
}
