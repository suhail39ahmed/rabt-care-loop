output "id" {
  description = "Content Safety account ID."
  value       = azurerm_cognitive_account.this.id
}

output "endpoint" {
  description = "Content Safety endpoint (direct; callers go through APIM)."
  value       = azurerm_cognitive_account.this.endpoint
}
