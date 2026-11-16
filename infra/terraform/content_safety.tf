# Text moderation + Prompt Shields (text:shieldPrompt) for patient input, retrieved chunks and
# external agent replies. Reached through APIM with managed identity.
resource "azurerm_cognitive_account" "content_safety" {
  #checkov:skip=CKV_AZURE_236:local auth is off by default (var.disable_local_auth = true); checkov cannot resolve the variable
  #checkov:skip=CKV_AZURE_134:public access is off when enable_private_networking = true (default); checkov cannot resolve the variable
  count                         = var.enable_content_safety ? 1 : 0
  name                          = "cs-${local.base}-${local.suffix}"
  location                      = local.locations.content_safety
  resource_group_name           = azurerm_resource_group.main.name
  kind                          = "ContentSafety"
  sku_name                      = "S0"
  custom_subdomain_name         = "${var.name_prefix}-${var.environment}-cs-${local.suffix}"
  local_auth_enabled            = !var.disable_local_auth
  public_network_access_enabled = !local.private
  tags                          = local.tags

  identity {
    type = "SystemAssigned"
  }

  network_acls {
    default_action = local.private ? "Deny" : "Allow"
    bypass         = "AzureServices"
  }
}
