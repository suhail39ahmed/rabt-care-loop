# Adopt pilot resources that were created by hand in the portal before Terraform ran.
# Off by default, so plans, `terraform test` (mock providers) and fresh environments are unaffected.
# Turn it on once:  terraform plan -var-file=environments/pilot.tfvars -var import_existing=true
# (or run the infra workflow manually with "import_existing" ticked). After the first successful
# apply the resources are in state and the flag can stay off; leaving it on is a no-op.

variable "import_existing" {
  description = "Import the hand-created pilot resource group, APIM, Log Analytics workspace, VNet and ACR into state."
  type        = bool
  default     = false
}

locals {
  import_rg_id = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/resourceGroups/${local.names.resource_group}"
  do_import    = var.import_existing ? { pilot = true } : {}
  do_import_vn = var.import_existing && local.private ? { pilot = true } : {}
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
  for_each = local.do_import_vn
  to       = module.network[0].azurerm_virtual_network.this
  id       = "${local.import_rg_id}/providers/Microsoft.Network/virtualNetworks/vnet-${local.names.vnet}"
}

import {
  for_each = local.do_import
  to       = module.hosting.azurerm_container_registry.this
  id       = "${local.import_rg_id}/providers/Microsoft.ContainerRegistry/registries/${local.names.registry}"
}
