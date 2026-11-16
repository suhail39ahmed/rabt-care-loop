# Non-secret outputs. Keys are never output: the APIM subscription key is in Key Vault
# (or read with `az apim subscription keys list`), and anything secret is marked sensitive.

output "resource_group_name" {
  description = "Resource group holding the Rabt AI stack."
  value       = azurerm_resource_group.main.name
}

output "apim_gateway_url" {
  description = "APIM gateway base URL (the only endpoint Render talks to)."
  value       = azurerm_api_management.main.gateway_url
}

output "apim_name" {
  description = "APIM instance name."
  value       = azurerm_api_management.main.name
}

output "openai_deployments" {
  description = "Deployment names by router role."
  value = {
    small     = local.deployments_by_role.small[0]
    strong    = local.deployments_by_role.strong[0]
    embedding = local.embedding_deployment
  }
}

output "openai_endpoints" {
  description = "Direct Azure OpenAI endpoints (private when private networking is on; Render should use APIM)."
  value       = { for k, a in azurerm_cognitive_account.openai : k => a.endpoint }
}

output "search_endpoint" {
  description = "AI Search endpoint via APIM."
  value       = "${azurerm_api_management.main.gateway_url}/search"
}

output "search_service_name" {
  description = "AI Search service name (direct endpoint https://<name>.search.windows.net)."
  value       = azurerm_search_service.main.name
}

output "search_index_name" {
  description = "Index the ingestion script creates and the Rabt API queries."
  value       = var.search_index_name
}

output "content_safety_endpoint" {
  description = "Content Safety endpoint via APIM; the SDK appends /contentsafety/... itself (null when disabled)."
  value       = var.enable_content_safety ? azurerm_api_management.main.gateway_url : null
}

output "storage_account_name" {
  description = "Storage account for KB documents."
  value       = azurerm_storage_account.kb.name
}

output "kb_container_name" {
  description = "Private blob container for KB documents."
  value       = azurerm_storage_container.kb.name
}

output "key_vault_name" {
  description = "Key Vault name."
  value       = azurerm_key_vault.main.name
}

output "key_vault_secret_name_apim_key" {
  description = "Key Vault secret holding the APIM subscription key (null when Terraform could not write it)."
  value       = local.write_secrets ? azurerm_key_vault_secret.apim_rabt_key[0].name : null
}

output "ingest_identity_client_id" {
  description = "Client ID of the ingestion managed identity."
  value       = azurerm_user_assigned_identity.ingest.client_id
}

output "application_insights_connection_string" {
  description = "App Insights connection string (sensitive)."
  value       = azurerm_application_insights.main.connection_string
  sensitive   = true
}

output "render_env" {
  description = "Non-secret env vars for the Render API service. Secret values (the APIM key) come from Key Vault, never from Terraform output."
  value = {
    AZURE_OPENAI_ENDPOINT             = azurerm_api_management.main.gateway_url
    AZURE_OPENAI_API_VERSION          = var.openai_api_version
    AZURE_OPENAI_MODEL                = local.deployments_by_role.small[0]
    AZURE_OPENAI_MODEL_STRONG         = local.deployments_by_role.strong[0]
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT = local.embedding_deployment
    AZURE_SEARCH_ENDPOINT             = "${azurerm_api_management.main.gateway_url}/search"
    AZURE_SEARCH_INDEX                = var.search_index_name
    CONTENT_SAFETY_ENDPOINT           = var.enable_content_safety ? azurerm_api_management.main.gateway_url : ""
    KEY_VAULT_NAME                    = azurerm_key_vault.main.name
    KEY_VAULT_SECRET_APIM_KEY         = "apim-rabt-subscription-key"
  }
}

output "apim_subscription_resource_id" {
  description = "Resource ID of the Rabt APIM subscription (use with listSecrets to read the key when it is not in Key Vault)."
  value       = local.apim_subscription_required ? azurerm_api_management_subscription.rabt[0].id : null
}
