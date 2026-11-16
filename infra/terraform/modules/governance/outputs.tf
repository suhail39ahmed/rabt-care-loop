output "budget_id" {
  description = "Budget ID."
  value       = azurerm_consumption_budget_resource_group.this.id
}

output "lock_enabled" {
  description = "Whether the resource group delete lock exists."
  value       = var.enable_resource_lock
}
