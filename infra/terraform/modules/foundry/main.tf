# Microsoft Foundry (kind AIServices): single multi-service AI backend behind APIM.
# OpenAI deployments, Content Safety and Language PII share this account endpoint.
# The pilot project is the portal boundary for evals; App Insights is connected at account level.
# APIM is registered as the project AI gateway in root (after APIM exists — avoids a cycle).
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
  project_management_enabled    = var.project_name != null
  tags                          = merge(var.tags, { role = "foundry" })

  identity {
    type = "SystemAssigned"
  }

  network_acls {
    default_action = var.network_default_action
    bypass         = "AzureServices"
  }
}

resource "azurerm_cognitive_deployment" "this" {
  for_each               = var.deployments
  name                   = each.key
  cognitive_account_id   = azurerm_cognitive_account.this.id
  rai_policy_name        = "Microsoft.DefaultV2"
  version_upgrade_option = "NoAutoUpgrade"

  model {
    format  = "OpenAI"
    name    = each.value.model_name
    version = each.value.model_version
  }

  sku {
    name     = each.value.sku_name
    capacity = each.value.capacity
  }
}

resource "azapi_resource" "project" {
  count     = var.project_name == null ? 0 : 1
  type      = "Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview"
  name      = var.project_name
  parent_id = azurerm_cognitive_account.this.id
  location  = var.location
  # Project itself needs SystemAssigned MI (account MI alone is not enough for this API).
  identity {
    type = "SystemAssigned"
  }
  body = {
    properties = {
      displayName = var.project_display_name
      description = var.project_description
    }
  }
  schema_validation_enabled = false
  locks                     = [azurerm_cognitive_account.this.id]
  depends_on                = [azurerm_cognitive_account.this]
}

# Account-level App Insights (Foundry portal tracing + evals → same Appi as APIM/API).
# API requires the full connection string (instrumentation key alone is rejected).
resource "azapi_resource" "app_insights_connection" {
  count     = var.enable_application_insights_connection ? 1 : 0
  type      = "Microsoft.CognitiveServices/accounts/connections@2025-06-01"
  name      = "${var.name}-appinsights"
  parent_id = azurerm_cognitive_account.this.id
  body = {
    properties = {
      authType                    = "ApiKey"
      category                    = "AppInsights"
      target                      = var.application_insights_id
      useWorkspaceManagedIdentity = false
      isSharedToAll               = true
      peRequirement               = "NotRequired"
      peStatus                    = "NotApplicable"
      metadata = {
        ApiType    = "Azure"
        ResourceId = var.application_insights_id
      }
      credentials = {
        key = var.application_insights_connection_string
      }
    }
  }
  schema_validation_enabled = false
  locks                     = [azurerm_cognitive_account.this.id]
}
