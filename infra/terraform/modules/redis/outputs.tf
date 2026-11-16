output "id" {
  description = "Redis ID."
  value       = azurerm_managed_redis.this.id
}

output "hostname" {
  description = "Redis hostname."
  value       = azurerm_managed_redis.this.hostname
}

output "primary_access_key" {
  description = "Primary access key (only used by APIM's cache connection)."
  value       = azurerm_managed_redis.this.default_database[0].primary_access_key
  sensitive   = true
}
