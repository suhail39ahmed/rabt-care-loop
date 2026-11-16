# Diagnostic settings: every resource sends logs and metrics to Log Analytics.
locals {
  diagnostic_targets = merge(
    { for k, a in azurerm_cognitive_account.openai : "openai-${k}" => a.id },
    {
      search       = azurerm_search_service.main.id
      keyvault     = azurerm_key_vault.main.id
      apim         = azurerm_api_management.main.id
      storage-blob = "${azurerm_storage_account.kb.id}/blobServices/default"
    },
    var.enable_content_safety ? { contentsafety = azurerm_cognitive_account.content_safety[0].id } : {}
  )

  diagnostic_keys = concat(
    [for k in keys(local.openai_accounts) : "openai-${k}"],
    ["search", "keyvault", "apim", "storage-blob"],
    var.enable_content_safety ? ["contentsafety"] : []
  )
}

resource "azurerm_monitor_diagnostic_setting" "all" {
  for_each                   = toset(local.diagnostic_keys)
  name                       = "diag-to-law"
  target_resource_id         = local.diagnostic_targets[each.key]
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  enabled_log {
    category_group = "allLogs"
  }

  enabled_metric {
    category = each.key == "storage-blob" ? "Transaction" : "AllMetrics"
  }
}

# Storage account-level metrics (logs live on the blob service above).
resource "azurerm_monitor_diagnostic_setting" "storage_account" {
  name                       = "diag-to-law"
  target_resource_id         = azurerm_storage_account.kb.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  enabled_metric {
    category = "Transaction"
  }
}
