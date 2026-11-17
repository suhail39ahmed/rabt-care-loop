output "id" {
  description = "Language account ID."
  value       = azurerm_cognitive_account.this.id
}

output "endpoint" {
  description = "Language endpoint (direct; callers go through APIM)."
  value       = azurerm_cognitive_account.this.endpoint
}
