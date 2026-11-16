# Least-privilege identities and role assignments.
#  - APIM (system MI): calls Azure OpenAI, Content Safety, AI Search (read) and may read Key Vault secrets.
#  - AI Search (system MI): integrated vectorisation (embeddings) and reading KB blobs.
#  - Ingestion (user-assigned MI): for a pilot ingestion job (#94) reading blobs and writing the index.
#  - Deployer (optional): the identity running Terraform, for setup and the local ingestion script.

resource "azurerm_user_assigned_identity" "ingest" {
  name                = "id-${local.base}-ingest"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

locals {
  role_assignments = merge(
    {
      for k, a in azurerm_cognitive_account.openai : "apim-openai-${k}" => {
        scope = a.id, role = "Cognitive Services OpenAI User", principal = azurerm_api_management.main.identity[0].principal_id
      }
    },
    {
      "apim-search-reader" = { scope = azurerm_search_service.main.id, role = "Search Index Data Reader", principal = azurerm_api_management.main.identity[0].principal_id }
      "apim-kv-secrets"    = { scope = azurerm_key_vault.main.id, role = "Key Vault Secrets User", principal = azurerm_api_management.main.identity[0].principal_id }

      "search-openai"    = { scope = azurerm_cognitive_account.openai["primary"].id, role = "Cognitive Services OpenAI User", principal = azurerm_search_service.main.identity[0].principal_id }
      "search-blob-read" = { scope = azurerm_storage_account.kb.id, role = "Storage Blob Data Reader", principal = azurerm_search_service.main.identity[0].principal_id }

      "ingest-blob-read"     = { scope = azurerm_storage_account.kb.id, role = "Storage Blob Data Reader", principal = azurerm_user_assigned_identity.ingest.principal_id }
      "ingest-search-writer" = { scope = azurerm_search_service.main.id, role = "Search Index Data Contributor", principal = azurerm_user_assigned_identity.ingest.principal_id }
      "ingest-openai"        = { scope = azurerm_cognitive_account.openai["primary"].id, role = "Cognitive Services OpenAI User", principal = azurerm_user_assigned_identity.ingest.principal_id }
    },
    var.enable_content_safety ? {
      "apim-content-safety" = { scope = azurerm_cognitive_account.content_safety[0].id, role = "Cognitive Services User", principal = azurerm_api_management.main.identity[0].principal_id }
    } : {},
    var.grant_deployer_data_roles ? {
      "deployer-kv-secrets"     = { scope = azurerm_key_vault.main.id, role = "Key Vault Secrets Officer", principal = data.azurerm_client_config.current.object_id }
      "deployer-search-index"   = { scope = azurerm_search_service.main.id, role = "Search Index Data Contributor", principal = data.azurerm_client_config.current.object_id }
      "deployer-search-service" = { scope = azurerm_search_service.main.id, role = "Search Service Contributor", principal = data.azurerm_client_config.current.object_id }
      "deployer-blob"           = { scope = azurerm_storage_account.kb.id, role = "Storage Blob Data Contributor", principal = data.azurerm_client_config.current.object_id }
      "deployer-openai"         = { scope = azurerm_cognitive_account.openai["primary"].id, role = "Cognitive Services OpenAI User", principal = data.azurerm_client_config.current.object_id }
    } : {}
  )

  # Static keys so for_each works before principals are known.
  role_assignment_keys = concat(
    [for k in keys(local.openai_accounts) : "apim-openai-${k}"],
    ["apim-search-reader", "apim-kv-secrets", "search-openai", "search-blob-read", "ingest-blob-read", "ingest-search-writer", "ingest-openai"],
    var.enable_content_safety ? ["apim-content-safety"] : [],
    var.grant_deployer_data_roles ? ["deployer-kv-secrets", "deployer-search-index", "deployer-search-service", "deployer-blob", "deployer-openai"] : []
  )
}

resource "azurerm_role_assignment" "roles" {
  for_each             = toset(local.role_assignment_keys)
  scope                = local.role_assignments[each.key].scope
  role_definition_name = local.role_assignments[each.key].role
  principal_id         = local.role_assignments[each.key].principal
  principal_type       = startswith(each.key, "deployer-") ? null : "ServicePrincipal"
  description          = "rabt: ${each.key}"
}
