locals {
  account_deployments = {
    for pair in setproduct(keys(var.accounts), keys(var.deployments)) :
    "${pair[0]}/${pair[1]}" => {
      account    = pair[0]
      deployment = pair[1]
      config     = var.deployments[pair[1]]
    }
  }
}

resource "azurerm_cognitive_account" "this" {
  #checkov:skip=CKV_AZURE_236:local auth is off by default (root var.disable_local_auth = true); checkov cannot resolve the variable
  #checkov:skip=CKV_AZURE_134:public access is off when enable_private_networking = true (default); checkov cannot resolve the variable
  for_each                      = var.accounts
  name                          = each.value.name
  location                      = each.value.location
  resource_group_name           = var.resource_group_name
  kind                          = "OpenAI"
  sku_name                      = "S0"
  custom_subdomain_name         = each.value.name
  local_auth_enabled            = var.local_auth_enabled
  public_network_access_enabled = var.public_network_access_enabled
  tags                          = merge(var.tags, { role = "openai-${each.key}" })

  identity {
    type = "SystemAssigned"
  }

  network_acls {
    default_action = var.network_default_action
    bypass         = "AzureServices"
  }
}

resource "azurerm_cognitive_deployment" "this" {
  for_each               = local.account_deployments
  name                   = each.value.deployment
  cognitive_account_id   = azurerm_cognitive_account.this[each.value.account].id
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
