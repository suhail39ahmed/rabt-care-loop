output "ids" {
  description = "Private endpoint IDs by key."
  value       = { for k, p in azurerm_private_endpoint.this : k => p.id }
}
