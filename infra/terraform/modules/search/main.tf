resource "azurerm_search_service" "this" {
  #checkov:skip=CKV_AZURE_124:public access only when not private or for allowlisted deployer IPs
  name                          = var.name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  sku                           = var.sku
  replica_count                 = var.replica_count
  partition_count               = var.partition_count
  local_authentication_enabled  = var.local_auth_enabled
  authentication_failure_mode   = var.local_auth_enabled ? "http403" : null
  semantic_search_sku           = var.semantic_ranker == "disabled" ? null : var.semantic_ranker
  public_network_access_enabled = var.public_network_access_enabled
  allowed_ips                   = var.allowed_ips
  network_rule_bypass_option    = "AzureServices"
  tags                          = var.tags

  identity {
    type = "SystemAssigned"
  }
}
