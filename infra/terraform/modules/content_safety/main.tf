# Text moderation + Prompt Shields (text:shieldPrompt) for patient input, retrieved chunks and
# external agent replies. Reached through APIM with managed identity.
resource "azurerm_cognitive_account" "this" {
  #checkov:skip=CKV_AZURE_236:local auth is off by default (root var.disable_local_auth = true); checkov cannot resolve the variable
  #checkov:skip=CKV_AZURE_134:public access is off when enable_private_networking = true (default); checkov cannot resolve the variable
  name                          = var.name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  kind                          = "ContentSafety"
  sku_name                      = "S0"
  custom_subdomain_name         = var.name
  local_auth_enabled            = var.local_auth_enabled
  public_network_access_enabled = var.public_network_access_enabled
  tags                          = var.tags

  identity {
    type = "SystemAssigned"
  }

  # bypass is only valid for OpenAI / AIServices / TextAnalytics — ContentSafety rejects it.
  network_acls {
    default_action = var.network_default_action
  }
}
