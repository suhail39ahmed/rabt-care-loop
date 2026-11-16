# ---------------------------------------------------------------------------
# API Management: Rabt's single AI gateway (Azure OpenAI, AI Search, Content Safety)
# Render holds one APIM subscription key; every backend call uses APIM's managed identity.
# ---------------------------------------------------------------------------
resource "azurerm_api_management" "main" {
  name                          = "apim-${local.base}-${local.suffix}"
  location                      = local.locations.apim
  resource_group_name           = azurerm_resource_group.main.name
  publisher_name                = var.apim_publisher_name
  publisher_email               = var.apim_publisher_email
  sku_name                      = var.apim_sku_name
  min_api_version               = "2021-08-01"
  public_network_access_enabled = true
  virtual_network_type          = local.private ? "External" : "None"
  public_ip_address_id          = local.private ? azurerm_public_ip.apim[0].id : null
  tags                          = local.tags

  identity {
    type = "SystemAssigned"
  }

  dynamic "virtual_network_configuration" {
    for_each = local.private ? [1] : []
    content {
      subnet_id = azurerm_subnet.apim[0].id
    }
  }

  security {
    backend_ssl30_enabled  = false
    backend_tls10_enabled  = false
    backend_tls11_enabled  = false
    frontend_ssl30_enabled = false
    frontend_tls10_enabled = false
    frontend_tls11_enabled = false
    # Weak ciphers off
    triple_des_ciphers_enabled                          = false
    tls_ecdhe_ecdsa_with_aes128_cbc_sha_ciphers_enabled = false
    tls_ecdhe_ecdsa_with_aes256_cbc_sha_ciphers_enabled = false
    tls_ecdhe_rsa_with_aes128_cbc_sha_ciphers_enabled   = false
    tls_ecdhe_rsa_with_aes256_cbc_sha_ciphers_enabled   = false
    tls_rsa_with_aes128_cbc_sha256_ciphers_enabled      = false
    tls_rsa_with_aes128_cbc_sha_ciphers_enabled         = false
    tls_rsa_with_aes256_cbc_sha256_ciphers_enabled      = false
    tls_rsa_with_aes256_cbc_sha_ciphers_enabled         = false
  }

  sign_up {
    enabled = false
    terms_of_service {
      consent_required = false
      enabled          = false
    }
  }

  timeouts {
    create = "3h"
    update = "3h"
  }

  depends_on = [azurerm_subnet_network_security_group_association.apim]
}

# --- Logging: App Insights logger + diagnostics with NO request/response bodies ---
resource "azurerm_api_management_logger" "appinsights" {
  name                = "appinsights"
  api_management_name = azurerm_api_management.main.name
  resource_group_name = azurerm_resource_group.main.name
  resource_id         = azurerm_application_insights.main.id

  application_insights {
    connection_string = azurerm_application_insights.main.connection_string
  }
}

resource "azurerm_api_management_diagnostic" "appinsights" {
  identifier                = "applicationinsights"
  api_management_name       = azurerm_api_management.main.name
  resource_group_name       = azurerm_resource_group.main.name
  api_management_logger_id  = azurerm_api_management_logger.appinsights.id
  sampling_percentage       = 100
  always_log_errors         = true
  log_client_ip             = false
  verbosity                 = "information"
  http_correlation_protocol = "W3C"

  frontend_request {
    body_bytes     = 0
    headers_to_log = ["x-rabt-task"]
  }
  frontend_response {
    body_bytes     = 0
    headers_to_log = ["x-rabt-remaining-tokens"]
  }
  backend_request {
    body_bytes = 0
  }
  backend_response {
    body_bytes = 0
  }
}

# Custom metrics (azure-openai-emit-token-metric) need "metrics": true on the diagnostic.
resource "azapi_update_resource" "apim_diagnostic_metrics" {
  type        = "Microsoft.ApiManagement/service/diagnostics@2024-05-01"
  resource_id = azurerm_api_management_diagnostic.appinsights.id

  body = {
    properties = {
      metrics = true
    }
  }
}

# --- Backends ---
resource "azurerm_api_management_backend" "openai" {
  #checkov:skip=CKV_AZURE_215:protocol "http" is the APIM REST-backend type; the url is https and TLS validation is on
  for_each            = azurerm_cognitive_account.openai
  name                = "aoai-${each.key}"
  api_management_name = azurerm_api_management.main.name
  resource_group_name = azurerm_resource_group.main.name
  protocol            = "http"
  url                 = "${trimsuffix(each.value.endpoint, "/")}/openai"
  description         = "Azure OpenAI (${each.key}, ${each.value.location})"

  tls {
    validate_certificate_chain = true
    validate_certificate_name  = true
  }

  circuit_breaker_rule {
    name                       = "aoai-breaker"
    trip_duration              = "PT1M"
    accept_retry_after_enabled = true

    failure_condition {
      count             = 3
      interval_duration = "PT1M"

      status_code_range {
        min = 429
        max = 429
      }
      status_code_range {
        min = 500
        max = 599
      }
    }
  }
}

# Load-balanced / failover pool: primary priority 1, secondary priority 2.
resource "azapi_resource" "openai_pool" {
  type      = "Microsoft.ApiManagement/service/backends@2024-05-01"
  name      = "aoai-pool"
  parent_id = azurerm_api_management.main.id

  body = {
    properties = {
      description = "Azure OpenAI backend pool (priority failover)"
      type        = "Pool"
      pool = {
        services = [
          for k, b in azurerm_api_management_backend.openai : {
            id       = b.id
            priority = k == "primary" ? 1 : 2
            weight   = 1
          }
        ]
      }
    }
  }
}

# Embeddings backend for the semantic cache lookup.
resource "azurerm_api_management_backend" "embeddings" {
  #checkov:skip=CKV_AZURE_215:protocol "http" is the APIM REST-backend type; the url is https and TLS validation is on
  count               = var.enable_semantic_cache ? 1 : 0
  name                = "aoai-embeddings"
  api_management_name = azurerm_api_management.main.name
  resource_group_name = azurerm_resource_group.main.name
  protocol            = "http"
  url                 = "${trimsuffix(azurerm_cognitive_account.openai["primary"].endpoint, "/")}/openai/deployments/${local.embedding_deployment}/embeddings"
  description         = "Embeddings for the APIM semantic cache"

  tls {
    validate_certificate_chain = true
    validate_certificate_name  = true
  }
}

resource "azurerm_api_management_backend" "search" {
  #checkov:skip=CKV_AZURE_215:protocol "http" is the APIM REST-backend type; the url is https and TLS validation is on
  name                = "search"
  api_management_name = azurerm_api_management.main.name
  resource_group_name = azurerm_resource_group.main.name
  protocol            = "http"
  url                 = "https://${azurerm_search_service.main.name}.search.windows.net"
  description         = "Azure AI Search"

  tls {
    validate_certificate_chain = true
    validate_certificate_name  = true
  }
}

resource "azurerm_api_management_backend" "content_safety" {
  #checkov:skip=CKV_AZURE_215:protocol "http" is the APIM REST-backend type; the url is https and TLS validation is on
  count               = var.enable_content_safety ? 1 : 0
  name                = "content-safety"
  api_management_name = azurerm_api_management.main.name
  resource_group_name = azurerm_resource_group.main.name
  protocol            = "http"
  url                 = "${trimsuffix(azurerm_cognitive_account.content_safety[0].endpoint, "/")}/contentsafety"
  description         = "Azure AI Content Safety"

  tls {
    validate_certificate_chain = true
    validate_certificate_name  = true
  }
}

# --- Semantic cache link ---
resource "azurerm_api_management_redis_cache" "semantic" {
  count             = var.enable_semantic_cache ? 1 : 0
  name              = "semantic-cache"
  api_management_id = azurerm_api_management.main.id
  connection_string = "${azurerm_managed_redis.cache[0].hostname}:10000,password=${azurerm_managed_redis.cache[0].default_database[0].primary_access_key},ssl=True,abortConnect=False"
  cache_location    = "default"
  redis_cache_id    = azurerm_managed_redis.cache[0].id
}

# --- APIs ---
locals {
  apim_subscription_required = var.apim_auth_mode != "entra_jwt"

  apim_auth_fragment = templatefile("${path.module}/policies/auth.xml.tftpl", {
    mode      = var.apim_auth_mode
    tenant_id = data.azurerm_client_config.current.tenant_id
    audience  = var.apim_jwt_audience
  })
}

resource "azurerm_api_management_api" "openai" {
  name                  = "azure-openai"
  api_management_name   = azurerm_api_management.main.name
  resource_group_name   = azurerm_resource_group.main.name
  revision              = "1"
  display_name          = "Azure OpenAI (Rabt)"
  path                  = "openai"
  protocols             = ["https"]
  subscription_required = local.apim_subscription_required

  # Same header the OpenAI SDKs send, so LLM_API_KEY works unchanged.
  subscription_key_parameter_names {
    header = "api-key"
    query  = "subscription-key"
  }
}

resource "azurerm_api_management_api_operation" "openai" {
  for_each = {
    chat_completions = { method = "POST", url = "/deployments/{deployment-id}/chat/completions", display = "Chat completions" }
    embeddings       = { method = "POST", url = "/deployments/{deployment-id}/embeddings", display = "Embeddings" }
  }
  operation_id        = replace(each.key, "_", "-")
  api_name            = azurerm_api_management_api.openai.name
  api_management_name = azurerm_api_management.main.name
  resource_group_name = azurerm_resource_group.main.name
  display_name        = each.value.display
  method              = each.value.method
  url_template        = each.value.url

  template_parameter {
    name     = "deployment-id"
    required = true
    type     = "string"
    values   = keys(var.openai_deployments)
  }
}

resource "azurerm_api_management_api_policy" "openai" {
  api_name            = azurerm_api_management_api.openai.name
  api_management_name = azurerm_api_management.main.name
  resource_group_name = azurerm_resource_group.main.name

  xml_content = templatefile("${path.module}/policies/openai-api.xml.tftpl", {
    auth                  = local.apim_auth_fragment
    pool_backend_id       = azapi_resource.openai_pool.name
    tokens_per_minute     = var.apim_tokens_per_minute
    semantic_cache        = var.enable_semantic_cache
    embeddings_backend_id = var.enable_semantic_cache ? azurerm_api_management_backend.embeddings[0].name : ""
    cache_score_threshold = var.semantic_cache_score_threshold
    cache_ttl_seconds     = var.semantic_cache_ttl_seconds
  })

  depends_on = [azurerm_api_management_redis_cache.semantic, azurerm_api_management_api_operation.openai]
}

resource "azurerm_api_management_api" "search" {
  name                  = "ai-search"
  api_management_name   = azurerm_api_management.main.name
  resource_group_name   = azurerm_resource_group.main.name
  revision              = "1"
  display_name          = "Azure AI Search (Rabt KB, read-only)"
  path                  = "search"
  protocols             = ["https"]
  subscription_required = local.apim_subscription_required

  subscription_key_parameter_names {
    header = "api-key"
    query  = "subscription-key"
  }
}

resource "azurerm_api_management_api_operation" "search" {
  for_each = {
    query_post = { method = "POST", display = "Query (POST)" }
    query_get  = { method = "GET", display = "Query (GET)" }
  }
  operation_id        = replace(each.key, "_", "-")
  api_name            = azurerm_api_management_api.search.name
  api_management_name = azurerm_api_management.main.name
  resource_group_name = azurerm_resource_group.main.name
  display_name        = each.value.display
  method              = each.value.method
  url_template        = "/*"
}

resource "azurerm_api_management_api_policy" "search" {
  api_name            = azurerm_api_management_api.search.name
  api_management_name = azurerm_api_management.main.name
  resource_group_name = azurerm_resource_group.main.name

  xml_content = templatefile("${path.module}/policies/search-api.xml.tftpl", {
    auth             = local.apim_auth_fragment
    backend_id       = azurerm_api_management_backend.search.name
    index_name       = var.search_index_name
    calls_per_minute = var.apim_search_calls_per_minute
  })

  depends_on = [azurerm_api_management_api_operation.search]
}

resource "azurerm_api_management_api" "content_safety" {
  count                 = var.enable_content_safety ? 1 : 0
  name                  = "content-safety"
  api_management_name   = azurerm_api_management.main.name
  resource_group_name   = azurerm_resource_group.main.name
  revision              = "1"
  display_name          = "Azure AI Content Safety (Rabt)"
  path                  = "contentsafety"
  protocols             = ["https"]
  subscription_required = local.apim_subscription_required

  # Header the Content Safety SDK sends.
  subscription_key_parameter_names {
    header = "Ocp-Apim-Subscription-Key"
    query  = "subscription-key"
  }
}

resource "azurerm_api_management_api_operation" "content_safety" {
  count               = var.enable_content_safety ? 1 : 0
  operation_id        = "text-post"
  api_name            = azurerm_api_management_api.content_safety[0].name
  api_management_name = azurerm_api_management.main.name
  resource_group_name = azurerm_resource_group.main.name
  display_name        = "Text analyze / shieldPrompt"
  method              = "POST"
  url_template        = "/*"
}

resource "azurerm_api_management_api_policy" "content_safety" {
  count               = var.enable_content_safety ? 1 : 0
  api_name            = azurerm_api_management_api.content_safety[0].name
  api_management_name = azurerm_api_management.main.name
  resource_group_name = azurerm_resource_group.main.name

  xml_content = templatefile("${path.module}/policies/content-safety-api.xml.tftpl", {
    auth       = local.apim_auth_fragment
    backend_id = azurerm_api_management_backend.content_safety[0].name
  })

  depends_on = [azurerm_api_management_api_operation.content_safety]
}

# --- Product + subscription for the Rabt API (Render) ---
resource "azurerm_api_management_product" "rabt" {
  product_id            = "rabt"
  api_management_name   = azurerm_api_management.main.name
  resource_group_name   = azurerm_resource_group.main.name
  display_name          = "Rabt"
  description           = "Rabt orchestrator access to the AI gateway"
  subscription_required = local.apim_subscription_required
  approval_required     = local.apim_subscription_required ? true : null
  subscriptions_limit   = local.apim_subscription_required ? 2 : null
  published             = true
}

resource "azurerm_api_management_product_api" "rabt" {
  for_each = merge(
    { openai = azurerm_api_management_api.openai.name, search = azurerm_api_management_api.search.name },
    var.enable_content_safety ? { content_safety = azurerm_api_management_api.content_safety[0].name } : {}
  )
  api_name            = each.value
  product_id          = azurerm_api_management_product.rabt.product_id
  api_management_name = azurerm_api_management.main.name
  resource_group_name = azurerm_resource_group.main.name
}

resource "azurerm_api_management_subscription" "rabt" {
  count               = local.apim_subscription_required ? 1 : 0
  display_name        = "rabt-orchestrator"
  api_management_name = azurerm_api_management.main.name
  resource_group_name = azurerm_resource_group.main.name
  product_id          = azurerm_api_management_product.rabt.id
  state               = "active"
  allow_tracing       = false
}
