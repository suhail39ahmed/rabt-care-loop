resource "azurerm_search_service" "main" {
  #checkov:skip=CKV_AZURE_124:public access only when not private or for allowlisted deployer IPs
  name                          = "srch-${local.base}-${local.suffix}"
  location                      = local.locations.search
  resource_group_name           = azurerm_resource_group.main.name
  sku                           = var.search_sku
  replica_count                 = var.search_replica_count
  partition_count               = var.search_partition_count
  local_authentication_enabled  = !var.disable_local_auth
  authentication_failure_mode   = var.disable_local_auth ? null : "http403"
  semantic_search_sku           = var.search_semantic_ranker == "disabled" ? null : var.search_semantic_ranker
  public_network_access_enabled = local.setup_access_open
  allowed_ips                   = local.private ? var.deployer_ip_allowlist : []
  network_rule_bypass_option    = "AzureServices"
  tags                          = local.tags

  identity {
    type = "SystemAssigned"
  }
}
