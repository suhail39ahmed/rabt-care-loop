# Root composition: one resource group, guardrails, and module calls only.
data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "main" {
  name     = local.names.resource_group
  location = var.location
  tags     = local.tags
}

# Cross-variable checks (kept here so Terraform can evaluate them before any module runs).
resource "terraform_data" "guardrails" {
  input = local.all_locations

  lifecycle {
    precondition {
      condition     = alltrue([for l in local.all_locations : contains(var.allowed_locations, l)])
      error_message = "All locations (location, location_overrides) must be in allowed_locations."
    }
    precondition {
      condition     = alltrue([for l in local.all_locations : contains(keys(local.region_codes), l)])
      error_message = "Every location needs a short code in local.region_codes."
    }
    precondition {
      condition     = !local.private || local.apim_classic_sku
      error_message = "enable_private_networking needs an APIM SKU with VNet injection (Developer_* or Premium_*) so the gateway can reach private endpoints."
    }
    precondition {
      condition     = !local.private || local.locations.apim == var.location
      error_message = "With enable_private_networking, APIM must be in var.location (same region as the VNet it is injected into)."
    }
    precondition {
      condition     = var.enable_foundry
      error_message = "enable_foundry must be true: Foundry (AIServices) is the sole AI backend behind APIM."
    }
    precondition {
      condition     = var.apim_auth_mode == "subscription_key" || length(var.apim_jwt_audience) > 0
      error_message = "apim_jwt_audience is required when apim_auth_mode is entra_jwt or both."
    }
    precondition {
      condition     = length(local.deployments_by_role.small) > 0 && length(local.deployments_by_role.strong) > 0
      error_message = "openai_deployments needs at least one small and one strong deployment for the router."
    }
    precondition {
      condition     = length(local.names.storage_kb) <= 24 && length(local.names.key_vault) <= 24
      error_message = "Storage / Key Vault names exceed 24 characters; shorten workload, environment or name_suffix."
    }
  }
}

# ---------------------------------------------------------------------------
# Foundation: network, monitoring, identities
# ---------------------------------------------------------------------------
module "network" {
  source = "./modules/network"
  count  = local.private ? 1 : 0

  name                          = local.names.vnet
  resource_group_name           = azurerm_resource_group.main.name
  location                      = var.location
  address_space                 = var.vnet_address_space
  subnet_private_endpoints_cidr = var.subnet_private_endpoints_cidr
  subnet_apim_cidr              = var.subnet_apim_cidr
  subnet_apps_cidr              = var.subnet_apps_cidr
  private_dns_zones             = local.private_dns_zones
  apim_public_ip = {
    name              = "pip-${local.names.apim}"
    location          = local.locations.apim
    domain_name_label = local.names.apim_pip_label
  }
  tags = local.tags
}

module "monitoring" {
  source = "./modules/monitoring"

  names = {
    log_analytics = local.names.log_analytics
    app_insights  = local.names.app_insights
    action_group  = local.names.action_group
  }
  resource_group_name     = azurerm_resource_group.main.name
  location                = var.location
  retention_days          = var.log_retention_days
  alert_emails            = var.budget_contact_emails
  action_group_short_name = "${var.workload}alert"
  tags                    = local.tags
}

module "identity" {
  source = "./modules/identity"

  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  identities = {
    app    = local.names.id_app
    ingest = local.names.id_ingest
  }
  tags = local.tags
}

# ---------------------------------------------------------------------------
# Data and AI services
# ---------------------------------------------------------------------------
module "keyvault" {
  source = "./modules/keyvault"

  name                          = local.names.key_vault
  resource_group_name           = azurerm_resource_group.main.name
  location                      = var.location
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  public_network_access_enabled = local.setup_access_open
  network_default_action        = local.private ? "Deny" : "Allow"
  ip_rules                      = local.private ? var.deployer_ip_allowlist : []
  tags                          = local.tags
}

module "storage" {
  source = "./modules/storage"

  name                          = local.names.storage_kb
  resource_group_name           = azurerm_resource_group.main.name
  location                      = var.location
  replication_type              = var.storage_replication_type
  container_name                = var.kb_container_name
  public_network_access_enabled = local.setup_access_open
  network_default_action        = local.private ? "Deny" : "Allow"
  ip_rules                      = local.private ? var.deployer_ip_allowlist : []
  tags                          = local.tags
}

module "search" {
  source = "./modules/search"

  name                          = local.names.search
  resource_group_name           = azurerm_resource_group.main.name
  location                      = local.locations.search
  sku                           = var.search_sku
  semantic_ranker               = var.search_semantic_ranker
  replica_count                 = var.search_replica_count
  partition_count               = var.search_partition_count
  local_auth_enabled            = !var.disable_local_auth
  public_network_access_enabled = local.setup_access_open
  allowed_ips                   = local.private ? var.deployer_ip_allowlist : []
  tags                          = local.tags
}

# Sole AI backend: Foundry AIServices (OpenAI deployments + CS + Language on one endpoint).
module "foundry" {
  source = "./modules/foundry"

  name                                   = local.names.foundry
  resource_group_name                    = azurerm_resource_group.main.name
  location                               = local.locations.foundry
  deployments                            = var.openai_deployments
  local_auth_enabled                     = !var.disable_local_auth
  public_network_access_enabled          = !local.private
  network_default_action                 = local.private ? "Deny" : "Allow"
  project_name                           = var.foundry_project_name
  enable_application_insights_connection = true
  application_insights_id                = module.monitoring.app_insights_id
  application_insights_connection_string = module.monitoring.app_insights_connection_string
  tags                                   = local.tags
}

module "redis" {
  source = "./modules/redis"
  count  = var.enable_semantic_cache ? 1 : 0

  name                          = local.names.redis
  resource_group_name           = azurerm_resource_group.main.name
  location                      = local.locations.redis
  sku_name                      = var.redis_sku_name
  public_network_access_enabled = !local.private
  tags                          = local.tags
}

module "private_endpoints" {
  source = "./modules/private_endpoints"
  count  = local.private ? 1 : 0

  name                = local.base
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  subnet_id           = module.network[0].subnet_ids.private_endpoints
  endpoints = merge(
    {
      # One PE; both DNS zones so *.openai.azure.com and *.cognitiveservices.azure.com resolve privately.
      foundry = {
        resource_id = module.foundry.id
        subresource = "account"
        dns_zone_ids = [
          module.network[0].private_dns_zone_ids["openai"],
          module.network[0].private_dns_zone_ids["cognitive"],
        ]
      }
      search = { resource_id = module.search.id, subresource = "searchService", dns_zone_id = module.network[0].private_dns_zone_ids["search"] }
      vault  = { resource_id = module.keyvault.id, subresource = "vault", dns_zone_id = module.network[0].private_dns_zone_ids["vault"] }
      blob   = { resource_id = module.storage.id, subresource = "blob", dns_zone_id = module.network[0].private_dns_zone_ids["blob"] }
    },
    var.enable_semantic_cache ? {
      redis = { resource_id = module.redis[0].id, subresource = "redisEnterprise", dns_zone_id = module.network[0].private_dns_zone_ids["redis"] }
    } : {}
  )
  tags = local.tags
}

# ---------------------------------------------------------------------------
# AI gateway (APIM): only door to Foundry (OpenAI / CS / Language) and AI Search.
# Quotas: llm-token-limit on OpenAI + rate-limit-by-key on CS/Language/Search policies.
# ---------------------------------------------------------------------------
module "apim" {
  source = "./modules/apim"

  name                           = local.names.apim
  resource_group_name            = azurerm_resource_group.main.name
  location                       = local.locations.apim
  tenant_id                      = data.azurerm_client_config.current.tenant_id
  sku_name                       = var.apim_sku_name
  publisher_name                 = var.apim_publisher_name
  publisher_email                = var.apim_publisher_email
  subnet_id                      = local.private ? module.network[0].subnet_ids.apim : null
  public_ip_id                   = local.private ? module.network[0].apim_public_ip_id : null
  auth_mode                      = var.apim_auth_mode
  jwt_audience                   = var.apim_jwt_audience
  app_insights_id                = module.monitoring.app_insights_id
  app_insights_connection_string = module.monitoring.app_insights_connection_string
  openai_backends = {
    primary = {
      endpoint = module.foundry.endpoint
      location = local.locations.foundry
    }
  }
  openai_deployment_names        = keys(var.openai_deployments)
  embedding_deployment           = local.embedding_deployment
  tokens_per_minute              = var.apim_tokens_per_minute
  search_service_name            = module.search.name
  search_index_name              = var.search_index_name
  search_calls_per_minute        = var.apim_search_calls_per_minute
  enable_content_safety          = var.enable_content_safety
  content_safety_endpoint        = var.enable_content_safety ? module.foundry.endpoint : null
  enable_language                = var.enable_language_pii
  language_endpoint              = var.enable_language_pii ? module.foundry.endpoint : null
  enable_semantic_cache          = var.enable_semantic_cache
  redis                          = var.enable_semantic_cache ? { id = module.redis[0].id, hostname = module.redis[0].hostname, primary_access_key = module.redis[0].primary_access_key } : null
  semantic_cache_score_threshold = var.semantic_cache_score_threshold
  semantic_cache_ttl_seconds     = var.semantic_cache_ttl_seconds
  tags                           = local.tags
}

# Register APIM as the Foundry project AI gateway (portal/evals go through quotas).
# After APIM so subscription key is available; avoids module cycle with backends.
resource "azapi_resource" "foundry_apim_gateway" {
  # Static count (known at plan): project + subscription-key auth mode.
  count     = var.foundry_project_name != null && local.apim_subscription_required ? 1 : 0
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview"
  name      = "apim-ai-gateway"
  parent_id = module.foundry.project_id
  body = {
    properties = {
      category      = "ApiManagement"
      target        = "${trimsuffix(module.apim.gateway_url, "/")}/openai"
      authType      = "ApiKey"
      isSharedToAll = true
      credentials = {
        key = module.apim.subscription_primary_key
      }
      metadata = {
        ApiType             = "Azure"
        ResourceId          = module.apim.id
        deploymentInPath    = "true"
        inferenceAPIVersion = var.openai_api_version
        modelDiscovery      = "false"
      }
    }
  }
  schema_validation_enabled = false
}

# ---------------------------------------------------------------------------
# Least-privilege role assignments
#  - APIM (system MI): Foundry OpenAI User + Cognitive Services User (CS/Language), Search read, KV.
#  - AI Search / ingest: embeddings via Foundry; blob + index roles.
# ---------------------------------------------------------------------------
module "rbac" {
  source = "./modules/rbac"

  assignments = merge(
    {
      "apim-foundry-openai"  = { scope = module.foundry.id, role = "Cognitive Services OpenAI User", principal_id = module.apim.principal_id, principal_type = "ServicePrincipal" }
      "apim-foundry-user"    = { scope = module.foundry.id, role = "Cognitive Services User", principal_id = module.apim.principal_id, principal_type = "ServicePrincipal" }
      "app-kb-blob-writer"   = { scope = "${module.storage.id}/blobServices/default/containers/${var.kb_container_name}", role = "Storage Blob Data Contributor", principal_id = module.identity.principal_ids["app"], principal_type = "ServicePrincipal" }
      "apim-search-reader"   = { scope = module.search.id, role = "Search Index Data Reader", principal_id = module.apim.principal_id, principal_type = "ServicePrincipal" }
      "apim-kv-secrets"      = { scope = module.keyvault.id, role = "Key Vault Secrets User", principal_id = module.apim.principal_id, principal_type = "ServicePrincipal" }
      "search-foundry"       = { scope = module.foundry.id, role = "Cognitive Services OpenAI User", principal_id = module.search.principal_id, principal_type = "ServicePrincipal" }
      "search-blob-read"     = { scope = module.storage.id, role = "Storage Blob Data Reader", principal_id = module.search.principal_id, principal_type = "ServicePrincipal" }
      "ingest-blob-read"     = { scope = module.storage.id, role = "Storage Blob Data Reader", principal_id = module.identity.principal_ids["ingest"], principal_type = "ServicePrincipal" }
      "ingest-search-writer" = { scope = module.search.id, role = "Search Index Data Contributor", principal_id = module.identity.principal_ids["ingest"], principal_type = "ServicePrincipal" }
      "ingest-foundry"       = { scope = module.foundry.id, role = "Cognitive Services OpenAI User", principal_id = module.identity.principal_ids["ingest"], principal_type = "ServicePrincipal" }
    },
    var.grant_deployer_data_roles ? {
      "deployer-kv-secrets"     = { scope = module.keyvault.id, role = "Key Vault Secrets Officer", principal_id = data.azurerm_client_config.current.object_id }
      "deployer-search-index"   = { scope = module.search.id, role = "Search Index Data Contributor", principal_id = data.azurerm_client_config.current.object_id }
      "deployer-search-service" = { scope = module.search.id, role = "Search Service Contributor", principal_id = data.azurerm_client_config.current.object_id }
      "deployer-blob"           = { scope = module.storage.id, role = "Storage Blob Data Contributor", principal_id = data.azurerm_client_config.current.object_id }
      "deployer-foundry"        = { scope = module.foundry.id, role = "Cognitive Services OpenAI User", principal_id = data.azurerm_client_config.current.object_id }
      "deployer-acr-push"       = { scope = module.hosting.registry_id, role = "AcrPush", principal_id = data.azurerm_client_config.current.object_id }
    } : {}
  )
}

# ---------------------------------------------------------------------------
# Secrets: the APIM key (for people / scripts) and the webhook ingest secret
# ---------------------------------------------------------------------------
resource "random_password" "ingest_secret" {
  length  = 40
  special = false
}

# HMAC secret for signed A2A traffic between the API and the demo insurer agent
resource "random_password" "a2a_secret" {
  length  = 48
  special = false
}

module "secrets" {
  source = "./modules/keyvault_secret"
  count  = local.write_secrets ? 1 : 0

  key_vault_id = module.keyvault.id
  secret_names = ["apim-rabt-subscription-key", "rabt-ingest-secret"]
  secrets = {
    "apim-rabt-subscription-key" = {
      value        = module.apim.subscription_primary_key
      content_type = "APIM subscription key for the Rabt API (LLM_API_KEY)"
    }
    "rabt-ingest-secret" = {
      value        = random_password.ingest_secret.result
      content_type = "Shared secret for POST /fhir/webhook (RABT_INGEST_SECRET)"
    }
  }
  expiry_days = var.key_vault_secret_expiry_days
  tags        = local.tags

  depends_on = [module.rbac]
}

# ---------------------------------------------------------------------------
# App hosting: ACR + Container Apps (API + web). The deploy workflow ships the images.
# ---------------------------------------------------------------------------
module "hosting" {
  source = "./modules/container_apps"

  names = {
    registry    = local.names.registry
    environment = local.names.cae
    api_app     = local.names.api_app
    web_app     = local.names.web_app
    ingest_job  = local.names.ingest_job
    insurer_app = local.names.insurer_app
  }
  resource_group_name        = azurerm_resource_group.main.name
  location                   = var.location
  log_analytics_workspace_id = module.monitoring.log_analytics_workspace_id
  infrastructure_subnet_id   = local.private ? module.network[0].subnet_ids.apps : null
  app_identity_id            = module.identity.ids["app"]
  app_identity_principal_id  = module.identity.principal_ids["app"]
  app_identity_client_id     = module.identity.client_ids["app"]
  registry_sku               = var.registry_sku

  api = {
    min_replicas = var.api_min_replicas
    max_replicas = 1
    env = {
      AI_ENABLED                        = tostring(var.ai_enabled)
      LLM_PROVIDER                      = "azure"
      LLM_BASE_URL                      = module.apim.gateway_url
      LLM_MODEL                         = local.deployments_by_role.small[0]
      LLM_MODEL_SMALL                   = local.deployments_by_role.small[0]
      LLM_MODEL_STRONG                  = local.deployments_by_role.strong[0]
      LLM_DAILY_TOKEN_BUDGET            = tostring(var.llm_daily_token_budget)
      LLM_ROUTER_ESCALATE_CHARS         = tostring(var.llm_router_escalate_chars)
      AZURE_OPENAI_API_VERSION          = var.openai_api_version
      AZURE_OPENAI_MODEL_STRONG         = local.deployments_by_role.strong[0]
      AZURE_OPENAI_EMBEDDING_DEPLOYMENT = local.embedding_deployment
      AZURE_SEARCH_ENDPOINT             = "${module.apim.gateway_url}/search"
      AZURE_SEARCH_INDEX                = var.search_index_name
      AZURE_SEARCH_SEMANTIC_CONFIG      = var.search_semantic_ranker == "disabled" ? "" : "rabt-semantic"
      KB_BLOB_CONTAINER_URL             = local.kb_container_url
      CONTENT_SAFETY_ENDPOINT           = var.enable_content_safety ? module.apim.gateway_url : ""
      LANGUAGE_PII_ENABLED              = tostring(var.enable_language_pii)
      LANGUAGE_ENDPOINT                 = var.enable_language_pii ? module.apim.gateway_url : ""
      LANGUAGE_PII_MIN_CONFIDENCE       = tostring(var.language_pii_min_confidence)
      GUEST_MODE                        = "true"
      RABT_DB                           = "/tmp/rabt.db"
      OTEL_SERVICE_NAME                 = "rabt-orchestrator"
    }
    secret_env = merge(
      { RABT_INGEST_SECRET = "rabt-ingest-secret", APPLICATIONINSIGHTS_CONNECTION_STRING = "appinsights-connection" },
      local.apim_subscription_required ? { LLM_API_KEY = "llm-api-key" } : {}
    )
  }
  web = {
    min_replicas = var.web_min_replicas
  }
  ingest_job = var.enable_kb_ingest_job ? {
    identity_id           = module.identity.ids["ingest"]
    identity_principal_id = module.identity.principal_ids["ingest"]
    identity_client_id    = module.identity.client_ids["ingest"]
    cron                  = var.kb_ingest_cron
    # Embeddings go through the APIM AI gateway (metrics, quotas, failover); direct Azure OpenAI is the fallback.
    secret_env = local.apim_subscription_required ? { LLM_API_KEY = "llm-api-key" } : {}
    env = {
      LLM_PROVIDER                      = "azure"
      LLM_BASE_URL                      = module.apim.gateway_url
      KB_BLOB_CONTAINER_URL             = local.kb_container_url
      AZURE_SEARCH_SERVICE_ENDPOINT     = "https://${local.names.search}.search.windows.net"
      AZURE_SEARCH_INDEX                = var.search_index_name
      AZURE_OPENAI_ENDPOINT             = module.foundry.endpoint
      AZURE_OPENAI_EMBEDDING_DEPLOYMENT = local.embedding_deployment
      AZURE_OPENAI_API_VERSION          = var.openai_api_version
    }
  } : null
  insurer           = var.enable_insurer_demo ? {} : null
  a2a_shared_secret = random_password.a2a_secret.result
  secret_names      = concat(["rabt-ingest-secret", "appinsights-connection"], local.apim_subscription_required ? ["llm-api-key"] : [])
  secrets = merge(
    { "rabt-ingest-secret" = random_password.ingest_secret.result, "appinsights-connection" = module.monitoring.app_insights_connection_string },
    local.apim_subscription_required ? { "llm-api-key" = module.apim.subscription_primary_key } : {}
  )
  tags = local.tags
}

# ---------------------------------------------------------------------------
# Diagnostics and governance
# ---------------------------------------------------------------------------
module "diagnostics" {
  source = "./modules/diagnostics"

  log_analytics_workspace_id = module.monitoring.log_analytics_workspace_id
  targets = {
    foundry         = { resource_id = module.foundry.id }
    search          = { resource_id = module.search.id }
    keyvault        = { resource_id = module.keyvault.id }
    apim            = { resource_id = module.apim.id }
    storage-blob    = { resource_id = module.storage.blob_service_id, metric_category = "Transaction" }
    storage-account = { resource_id = module.storage.id, metric_category = "Transaction", logs = false }
    registry        = { resource_id = module.hosting.registry_id }
  }
}

module "governance" {
  source = "./modules/governance"

  name                 = local.base
  resource_group_id    = azurerm_resource_group.main.id
  budget_amount        = var.budget_amount
  budget_start_date    = var.budget_start_date
  contact_emails       = var.budget_contact_emails
  action_group_id      = module.monitoring.action_group_id
  enable_resource_lock = var.enable_resource_lock
  defender_plans       = var.enable_defender_plans ? var.defender_plans : []
}
