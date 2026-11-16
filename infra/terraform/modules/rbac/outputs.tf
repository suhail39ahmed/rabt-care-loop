output "ids" {
  description = "Role assignment IDs by key."
  value       = { for k, r in azurerm_role_assignment.this : k => r.id }
}
