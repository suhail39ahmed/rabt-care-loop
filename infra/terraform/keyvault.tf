resource "azurerm_key_vault" "main" {
  #checkov:skip=CKV_AZURE_189:public access only when not private or for allowlisted deployer IPs (default action Deny)
  name                          = substr("kv${local.compact}", 0, 24)
  location                      = azurerm_resource_group.main.location
  resource_group_name           = azurerm_resource_group.main.name
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  sku_name                      = "standard"
  rbac_authorization_enabled    = true
  purge_protection_enabled      = true
  soft_delete_retention_days    = 90
  public_network_access_enabled = local.setup_access_open
  tags                          = local.tags

  network_acls {
    bypass         = "AzureServices"
    default_action = local.private ? "Deny" : "Allow"
    ip_rules       = local.private ? var.deployer_ip_allowlist : []
  }
}

# Secrets are only written by Terraform when its runner can reach the vault.
locals {
  write_secrets = local.setup_access_open && var.grant_deployer_data_roles && local.apim_subscription_required
}

resource "time_sleep" "kv_rbac" {
  count           = local.write_secrets ? 1 : 0
  create_duration = "90s"
  depends_on      = [azurerm_role_assignment.roles]
}

resource "time_static" "secret_created" {}

resource "azurerm_key_vault_secret" "apim_rabt_key" {
  count           = local.write_secrets ? 1 : 0
  name            = "apim-rabt-subscription-key"
  value           = azurerm_api_management_subscription.rabt[0].primary_key
  key_vault_id    = azurerm_key_vault.main.id
  content_type    = "APIM subscription key for Rabt (set as LLM_API_KEY / AZURE_SEARCH_KEY / CONTENT_SAFETY_KEY on Render)"
  expiration_date = timeadd(time_static.secret_created.rfc3339, "${var.key_vault_secret_expiry_days * 24}h")
  tags            = local.tags

  depends_on = [time_sleep.kv_rbac]
}
