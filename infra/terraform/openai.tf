resource "azurerm_cognitive_account" "openai" {
  #checkov:skip=CKV_AZURE_236:local auth is off by default (var.disable_local_auth = true); checkov cannot resolve the variable
  #checkov:skip=CKV_AZURE_134:public access is off when enable_private_networking = true (default); checkov cannot resolve the variable
  for_each                      = local.openai_accounts
  name                          = "aoai-${local.base}-${each.key}-${local.suffix}"
  location                      = each.value
  resource_group_name           = azurerm_resource_group.main.name
  kind                          = "OpenAI"
  sku_name                      = "S0"
  custom_subdomain_name         = "${var.name_prefix}-${var.environment}-aoai-${each.key}-${local.suffix}"
  local_auth_enabled            = !var.disable_local_auth
  public_network_access_enabled = !local.private
  tags                          = merge(local.tags, { role = "openai-${each.key}" })

  identity {
    type = "SystemAssigned"
  }

  network_acls {
    default_action = local.private ? "Deny" : "Allow"
    bypass         = "AzureServices"
  }
}

resource "azurerm_cognitive_deployment" "openai" {
  for_each               = local.openai_account_deployments
  name                   = each.value.deployment
  cognitive_account_id   = azurerm_cognitive_account.openai[each.value.account].id
  rai_policy_name        = "Microsoft.DefaultV2"
  version_upgrade_option = "NoAutoUpgrade"

  model {
    format  = "OpenAI"
    name    = each.value.config.model_name
    version = each.value.config.model_version
  }

  sku {
    name     = each.value.config.sku_name
    capacity = each.value.config.capacity
  }
}
