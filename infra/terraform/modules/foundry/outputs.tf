output "id" {
  description = "Foundry (AIServices) account resource ID."
  value       = azurerm_cognitive_account.this.id
}

output "endpoint" {
  description = "Foundry account endpoint (portal / multi-tool; app still uses APIM)."
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

output "project_id" {
  description = "Foundry project resource ID (null if no project)."
  value       = try(azapi_resource.project[0].id, null)
}
