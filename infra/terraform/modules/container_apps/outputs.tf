output "registry_name" {
  description = "ACR name (deploy workflow pushes here)."
  value       = azurerm_container_registry.this.name
}

output "registry_login_server" {
  description = "ACR login server."
  value       = azurerm_container_registry.this.login_server
}

output "registry_id" {
  description = "ACR ID (grant AcrPush to the deploy identity on this scope)."
  value       = azurerm_container_registry.this.id
}

output "environment_name" {
  description = "Container Apps environment name."
  value       = azurerm_container_app_environment.this.name
}

output "api_app_name" {
  description = "API container app name."
  value       = azurerm_container_app.api.name
}

output "web_app_name" {
  description = "Web container app name."
  value       = azurerm_container_app.web.name
}

output "api_url" {
  description = "Public HTTPS URL of the API."
  value       = "https://${azurerm_container_app.api.ingress[0].fqdn}"
}

output "web_url" {
  description = "Public HTTPS URL of the web app."
  value       = "https://${azurerm_container_app.web.ingress[0].fqdn}"
}

output "app_ids" {
  description = "Container app IDs (diagnostics / role scopes)."
  value       = { api = azurerm_container_app.api.id, web = azurerm_container_app.web.id }
}

output "ingest_job_name" {
  description = "KB ingestion job name (null when disabled)."
  value       = var.ingest_job == null ? null : azurerm_container_app_job.ingest[0].name
}

output "insurer_app_name" {
  description = "Demo insurer A2A app name (null when disabled)."
  value       = var.insurer == null ? null : azurerm_container_app.insurer[0].name
}

output "insurer_url" {
  description = "Public HTTPS URL of the demo insurer agent (its page and agent card)."
  value       = var.insurer == null ? null : "https://${azurerm_container_app.insurer[0].ingress[0].fqdn}"
}
