# Non-secret outputs. Keys are never output in clear text: the APIM key goes to Key Vault and to the
# API container as a Container Apps secret; anything secret is marked sensitive.

output "resource_group_name" {
  description = "Resource group holding the Rabt stack."
  value       = azurerm_resource_group.main.name
}

output "names" {
  description = "Every resource name the naming convention produced (for docs and scripts)."
  value = {
    resource_group = local.names.resource_group
    apim           = local.names.apim
    key_vault      = local.names.key_vault
    storage_kb     = local.names.storage_kb
    search         = local.names.search
    foundry        = local.names.foundry
    log_analytics  = local.names.log_analytics
    app_insights   = local.names.app_insights
    registry       = local.names.registry
    environment    = local.names.cae
    api_app        = local.names.api_app
    web_app        = local.names.web_app
  }
}

output "apim_gateway_url" {
  description = "APIM gateway base URL (the only endpoint the Rabt API talks to for AI)."
  value       = module.apim.gateway_url
}

output "apim_name" {
  description = "APIM instance name."
  value       = module.apim.name
}

output "apim_subscription_resource_id" {
  description = "Resource ID of the Rabt APIM subscription (read the key with az rest .../listSecrets if needed)."
  value       = module.apim.subscription_id
}

output "openai_deployments" {
  description = "Deployment names by router role (hosted on Foundry)."
  value = {
    small     = local.deployments_by_role.small[0]
    strong    = local.deployments_by_role.strong[0]
    embedding = local.embedding_deployment
  }
}

output "openai_endpoints" {
  description = "Foundry endpoint map (app uses APIM; direct endpoint for fallback/scripts)."
  value       = { primary = module.foundry.endpoint }
}

output "foundry_endpoint" {
  description = "Microsoft Foundry (AIServices) multi-service endpoint behind APIM."
  value       = module.foundry.endpoint
}

output "foundry_project_id" {
  description = "Foundry project resource ID (null if project disabled)."
  value       = module.foundry.project_id
}

output "foundry_app_insights_connection_id" {
  description = "Foundry account ↔ Application Insights connection ID."
  value       = module.foundry.app_insights_connection_id
}

output "foundry_apim_gateway_connection_id" {
  description = "Foundry project ↔ APIM AI gateway connection ID (apim-rabt-pilot-sea)."
  value       = try(azapi_resource.foundry_apim_gateway[0].id, null)
}

output "foundry_apim_gateway_account_connection_id" {
  description = "Foundry account ↔ APIM AI gateway connection ID."
  value       = try(azapi_resource.foundry_apim_gateway_account[0].id, null)
}

output "insurer_a2a_gateway_url" {
  description = "Demo insurer A2A via APIM AI gateway (agent card at /.well-known/agent.json)."
  value       = var.enable_insurer_demo ? "${trimsuffix(module.apim.gateway_url, "/")}/insurer" : null
}

output "search_service_name" {
  description = "AI Search service name."
  value       = module.search.name
}

output "search_index_name" {
  description = "Index the ingestion script creates and the Rabt API queries."
  value       = var.search_index_name
}

output "storage_account_name" {
  description = "Storage account for KB documents."
  value       = module.storage.name
}

output "kb_container_name" {
  description = "Private blob container for KB documents."
  value       = module.storage.container_name
}

output "key_vault_name" {
  description = "Key Vault name."
  value       = module.keyvault.name
}

output "key_vault_secret_names" {
  description = "Secrets Terraform wrote to Key Vault (empty when the vault is fully private)."
  value       = local.write_secrets ? module.secrets[0].names : []
}

output "ingest_identity_client_id" {
  description = "Client ID of the ingestion managed identity."
  value       = module.identity.client_ids["ingest"]
}

output "application_insights_connection_string" {
  description = "App Insights connection string (sensitive)."
  value       = module.monitoring.app_insights_connection_string
  sensitive   = true
}

# --- Hosting (used by the deploy workflow) ---
output "acr_name" {
  description = "Container registry the deploy workflow pushes to."
  value       = module.hosting.registry_name
}

output "acr_login_server" {
  description = "Container registry login server."
  value       = module.hosting.registry_login_server
}

output "container_app_environment" {
  description = "Container Apps environment name."
  value       = module.hosting.environment_name
}

output "api_app_name" {
  description = "API container app name."
  value       = module.hosting.api_app_name
}

output "web_app_name" {
  description = "Web container app name."
  value       = module.hosting.web_app_name
}

output "kb_ingest_job_name" {
  description = "Start a KB re-index on demand: az containerapp job start -n <this> -g <resource group>."
  value       = module.hosting.ingest_job_name
}

output "api_url" {
  description = "Public API URL."
  value       = module.hosting.api_url
}

output "web_url" {
  description = "Public web URL."
  value       = module.hosting.web_url
}

output "security_summary" {
  description = "Security posture at a glance (also asserted by terraform test)."
  value = {
    private_networking        = local.private
    private_endpoints         = local.private ? sort(keys(module.private_endpoints[0].ids)) : []
    ai_local_auth_enabled     = module.foundry.local_auth_enabled
    apim_log_body_bytes       = module.apim.log_body_bytes
    apim_auth_mode            = var.apim_auth_mode
    key_vault_secrets_written = local.write_secrets
    diagnostics_targets       = sort(module.diagnostics.targets)
    min_tls                   = "TLS1_2"
    resource_lock             = var.enable_resource_lock
  }
}

output "insurer_url" {
  description = "Demo insurer A2A agent: its page (/) and agent card (/.well-known/agent.json)."
  value       = module.hosting.insurer_url
}
