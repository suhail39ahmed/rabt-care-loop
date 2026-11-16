output "id" {
  description = "Search service ID."
  value       = azurerm_search_service.this.id
}

output "name" {
  description = "Search service name."
  value       = azurerm_search_service.this.name
}

output "principal_id" {
  description = "System-assigned identity principal ID."
  value       = azurerm_search_service.this.identity[0].principal_id
}
