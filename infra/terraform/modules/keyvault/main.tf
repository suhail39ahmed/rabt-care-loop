resource "azurerm_key_vault" "this" {
  #checkov:skip=CKV_AZURE_189:public access only when not private or for allowlisted deployer IPs (default action Deny)
  name                          = var.name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  tenant_id                     = var.tenant_id
  sku_name                      = "standard"
  rbac_authorization_enabled    = true
  purge_protection_enabled      = true
  soft_delete_retention_days    = 90
  public_network_access_enabled = var.public_network_access_enabled
  tags                          = var.tags

  network_acls {
    bypass         = "AzureServices"
    default_action = var.network_default_action
    ip_rules       = var.ip_rules
  }
}
