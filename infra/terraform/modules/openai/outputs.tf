output "ids" {
  description = "Account IDs by key."
  value       = { for k, a in azurerm_cognitive_account.this : k => a.id }
}

output "endpoints" {
  description = "Account endpoints by key (direct; callers should go through APIM)."
  value       = { for k, a in azurerm_cognitive_account.this : k => a.endpoint }
}

output "locations" {
  description = "Account regions by key."
  value       = { for k, a in var.accounts : k => a.location }
}

output "local_auth_enabled" {
  description = "Whether API keys are allowed on the accounts."
  value       = var.local_auth_enabled
}

output "deployment_names" {
  description = "Deployment names (all accounts carry the same set)."
  value       = keys(var.deployments)
}
