output "names" {
  description = "Names of the secrets written."
  value       = [for s in azurerm_key_vault_secret.this : s.name]
}

output "versionless_ids" {
  description = "Versionless secret IDs by name (for Key Vault references)."
  value       = { for k, s in azurerm_key_vault_secret.this : k => s.versionless_id }
}
