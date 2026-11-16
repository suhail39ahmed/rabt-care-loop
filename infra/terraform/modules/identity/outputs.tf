output "ids" {
  description = "Identity resource IDs by key."
  value       = { for k, i in azurerm_user_assigned_identity.this : k => i.id }
}

output "principal_ids" {
  description = "Identity principal (object) IDs by key."
  value       = { for k, i in azurerm_user_assigned_identity.this : k => i.principal_id }
}

output "client_ids" {
  description = "Identity client IDs by key."
  value       = { for k, i in azurerm_user_assigned_identity.this : k => i.client_id }
}
