# Adopt pilot resources that already exist in Azure (hand-created or left by a partial apply).
# Off by default so plans, `terraform test` and fresh environments are unaffected.
# Turn on once: terraform plan/apply -var import_existing=true (or infra workflow import_existing=true).
# After a successful apply the resources are in state; leaving the flag on is a no-op for already-imported IDs.

variable "import_existing" {
  description = "Import existing pilot resources (RG, APIM, LAW, ACR, identities, KV, storage, search, App Insights, CAE, container apps, etc.) into state."
  type        = bool
  default     = false
}

locals {
  import_rg_id = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/resourceGroups/${local.names.resource_group}"
  do_import    = var.import_existing ? { pilot = true } : {}
  do_import_vn = var.import_existing && local.private ? { pilot = true } : {}
  # Insurer app is optional (count); only import when that feature is on.
  do_import_insurer = var.import_existing && var.enable_insurer_demo ? { pilot = true } : {}
}

import {
  for_each = local.do_import
  to       = azurerm_resource_group.main
  id       = local.import_rg_id
}

import {
  for_each = local.do_import
  to       = module.apim.azurerm_api_management.main
  id       = "${local.import_rg_id}/providers/Microsoft.ApiManagement/service/${local.names.apim}"
}

import {
  for_each = local.do_import
  to       = module.monitoring.azurerm_log_analytics_workspace.this
  id       = "${local.import_rg_id}/providers/Microsoft.OperationalInsights/workspaces/${local.names.log_analytics}"
}

import {
  for_each = local.do_import
  to       = module.monitoring.azurerm_application_insights.this
  id       = "${local.import_rg_id}/providers/Microsoft.Insights/components/${local.names.app_insights}"
}

import {
  for_each = local.do_import
  to       = module.monitoring.azurerm_monitor_action_group.this
  id       = "${local.import_rg_id}/providers/Microsoft.Insights/actionGroups/${local.names.action_group}"
}

import {
  for_each = local.do_import_vn
  to       = module.network[0].azurerm_virtual_network.this
  id       = "${local.import_rg_id}/providers/Microsoft.Network/virtualNetworks/vnet-${local.names.vnet}"
}

import {
  for_each = local.do_import
  to       = module.hosting.azurerm_container_registry.this
  id       = "${local.import_rg_id}/providers/Microsoft.ContainerRegistry/registries/${local.names.registry}"
}

import {
  for_each = local.do_import
  to       = module.hosting.azurerm_container_app_environment.this
  id       = "${local.import_rg_id}/providers/Microsoft.App/managedEnvironments/${local.names.cae}"
}

import {
  for_each = local.do_import
  to       = module.hosting.azurerm_container_app.web
  id       = "${local.import_rg_id}/providers/Microsoft.App/containerApps/${local.names.web_app}"
}

import {
  for_each = local.do_import_insurer
  to       = module.hosting.azurerm_container_app.insurer[0]
  id       = "${local.import_rg_id}/providers/Microsoft.App/containerApps/${local.names.insurer_app}"
}

import {
  for_each = local.do_import
  to       = module.identity.azurerm_user_assigned_identity.this["app"]
  id       = "${local.import_rg_id}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/${local.names.id_app}"
}

import {
  for_each = local.do_import
  to       = module.identity.azurerm_user_assigned_identity.this["ingest"]
  id       = "${local.import_rg_id}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/${local.names.id_ingest}"
}

import {
  for_each = local.do_import
  to       = module.keyvault.azurerm_key_vault.this
  id       = "${local.import_rg_id}/providers/Microsoft.KeyVault/vaults/${local.names.key_vault}"
}

import {
  for_each = local.do_import
  to       = module.storage.azurerm_storage_account.this
  id       = "${local.import_rg_id}/providers/Microsoft.Storage/storageAccounts/${local.names.storage_kb}"
}

import {
  for_each = local.do_import
  to       = module.search.azurerm_search_service.this
  id       = "${local.import_rg_id}/providers/Microsoft.Search/searchServices/${local.names.search}"
}

# AI alerts created by the partial apply (keys match modules/monitoring local.ai_alerts).
import {
  for_each = var.import_existing ? toset(["safety-blocks", "llm-errors", "budget-refusals", "token-burn"]) : toset([])
  to       = module.monitoring.azurerm_monitor_scheduled_query_rules_alert_v2.ai[each.key]
  id       = "${local.import_rg_id}/providers/Microsoft.Insights/scheduledQueryRules/alert-${local.names.app_insights}-${each.key}"
}
