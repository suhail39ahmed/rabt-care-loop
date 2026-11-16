output "id" {
  description = "APIM ID."
  value       = azurerm_api_management.main.id
}

output "name" {
  description = "APIM name."
  value       = azurerm_api_management.main.name
}

output "gateway_url" {
  description = "Gateway base URL."
  value       = azurerm_api_management.main.gateway_url
}

output "principal_id" {
  description = "APIM system-assigned identity principal ID."
  value       = azurerm_api_management.main.identity[0].principal_id
}

output "subscription_required" {
  description = "Whether callers need an APIM subscription key."
  value       = local.apim_subscription_required
}

output "subscription_id" {
  description = "Resource ID of the Rabt APIM subscription (null in entra_jwt mode)."
  value       = one(azurerm_api_management_subscription.rabt[*].id)
}

output "subscription_primary_key" {
  description = "Primary key of the Rabt APIM subscription (null in entra_jwt mode)."
  value       = one(azurerm_api_management_subscription.rabt[*].primary_key)
  sensitive   = true
}

output "log_body_bytes" {
  description = "Request/response body bytes logged by the APIM diagnostic (must stay 0)."
  value       = azurerm_api_management_diagnostic.appinsights.frontend_request[0].body_bytes
}

output "openai_policy_xml" {
  description = "Rendered Azure OpenAI API policy (for tests and review)."
  value       = azurerm_api_management_api_policy.openai.xml_content
}

output "openai_backend_count" {
  description = "Number of Azure OpenAI backends in the pool."
  value       = length(azurerm_api_management_backend.openai)
}
