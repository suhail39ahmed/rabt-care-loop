# Every resource sends logs (allLogs) and metrics to Log Analytics.
resource "azurerm_monitor_diagnostic_setting" "this" {
  for_each                   = var.targets
  name                       = "diag-to-law"
  target_resource_id         = each.value.resource_id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  dynamic "enabled_log" {
    for_each = each.value.logs ? [1] : []
    content {
      category_group = "allLogs"
    }
  }

  enabled_metric {
    category = each.value.metric_category
  }
}
