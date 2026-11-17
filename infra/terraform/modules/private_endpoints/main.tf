resource "azurerm_private_endpoint" "this" {
  for_each            = var.endpoints
  name                = "pe-${var.name}-${each.key}"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.subnet_id
  tags                = var.tags

  private_service_connection {
    name                           = "psc-${each.key}"
    private_connection_resource_id = each.value.resource_id
    subresource_names              = [each.value.subresource]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = length(coalesce(each.value.dns_zone_ids, [])) > 0 ? each.value.dns_zone_ids : [each.value.dns_zone_id]
  }
}
