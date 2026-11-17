output "id" {
  description = "Foundry (AIServices) account resource ID."
  value       = azurerm_cognitive_account.this.id
}

output "endpoint" {
  description = "Foundry multi-service endpoint (APIM backends for OpenAI, Content Safety, Language)."
  value       = azurerm_cognitive_account.this.endpoint
}

output "name" {
  description = "Foundry account name."
  value       = azurerm_cognitive_account.this.name
}

output "principal_id" {
  description = "System-assigned managed identity principal ID."
  value       = azurerm_cognitive_account.this.identity[0].principal_id
}

output "local_auth_enabled" {
  description = "Whether API keys are allowed on the account."
  value       = var.local_auth_enabled
}

output "deployment_names" {
  description = "OpenAI deployment names on this Foundry account."
  value       = keys(azurerm_cognitive_deployment.this)
}

output "project_id" {
  description = "Foundry project resource ID (null if no project)."
  value       = try(azapi_resource.project[0].id, null)
}

output "app_insights_connection_id" {
  description = "Foundry ↔ Application Insights connection ID (null if skipped)."
  value       = try(azapi_resource.app_insights_connection[0].id, null)
}
