output "vnet_id" {
  description = "VNet ID."
  value       = azurerm_virtual_network.this.id
}

output "subnet_ids" {
  description = "Subnet IDs by purpose: private_endpoints, apim, apps."
  value = {
    private_endpoints = azurerm_subnet.private_endpoints.id
    apim              = azurerm_subnet.apim.id
    apps              = azurerm_subnet.apps.id
  }
  # NSGs must be attached before APIM / Container Apps use the subnets.
  depends_on = [
    azurerm_subnet_network_security_group_association.private_endpoints,
    azurerm_subnet_network_security_group_association.apim,
    azurerm_subnet_network_security_group_association.apps,
  ]
}

output "private_dns_zone_ids" {
  description = "Private DNS zone IDs keyed like var.private_dns_zones."
  value       = { for k, z in azurerm_private_dns_zone.this : k => z.id }
}

output "apim_public_ip_id" {
  description = "Public IP ID for APIM (null when not created)."
  value       = one(azurerm_public_ip.apim[*].id)
}
