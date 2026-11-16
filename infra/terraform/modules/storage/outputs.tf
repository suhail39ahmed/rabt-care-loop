output "id" {
  description = "Storage account ID."
  value       = azurerm_storage_account.this.id
}

output "name" {
  description = "Storage account name."
  value       = azurerm_storage_account.this.name
}

output "blob_service_id" {
  description = "Blob service resource ID (diagnostic target)."
  value       = "${azurerm_storage_account.this.id}/blobServices/default"
}

output "container_name" {
  description = "KB container name."
  value       = azurerm_storage_container.kb.name
}
