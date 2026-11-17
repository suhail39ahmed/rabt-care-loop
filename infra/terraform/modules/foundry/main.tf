# Microsoft Foundry (Cognitive Services kind AIServices): portal hub for Content Safety,
# Language PII, evaluations and future agents. Production traffic still enters via APIM;
# this resource is the governed surface for monitoring, tracing and tool configuration.
resource "azurerm_cognitive_account" "this" {
  #checkov:skip=CKV_AZURE_236:local auth is off by default (root var.disable_local_auth = true); checkov cannot resolve the variable
  #checkov:skip=CKV_AZURE_134:public access is off when enable_private_networking = true (default); checkov cannot resolve the variable
  name                          = var.name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  kind                          = "AIServices"
  sku_name                      = var.sku_name
  custom_subdomain_name         = var.name
  local_auth_enabled            = var.local_auth_enabled
  public_network_access_enabled = var.public_network_access_enabled
  tags                          = merge(var.tags, { role = "foundry" })

  identity {
    type = "SystemAssigned"
  }

  network_acls {
    default_action = var.network_default_action
    bypass         = "AzureServices"
  }
}

# Foundry project (subresource): isolates the Rabt pilot workspace inside the hub.
resource "azapi_resource" "project" {
  count     = var.project_name == null ? 0 : 1
  type      = "Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview"
  name      = var.project_name
  parent_id = azurerm_cognitive_account.this.id
  body = {
    properties = {
      displayName = var.project_display_name
      description = var.project_description
    }
  }
  schema_validation_enabled = false
  locks                     = [azurerm_cognitive_account.this.id]
}
