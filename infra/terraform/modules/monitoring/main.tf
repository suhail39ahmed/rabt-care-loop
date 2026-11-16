resource "azurerm_log_analytics_workspace" "this" {
  name                = var.names.log_analytics
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = var.retention_days
  tags                = var.tags
}

resource "azurerm_application_insights" "this" {
  name                = var.names.app_insights
  location            = var.location
  resource_group_name = var.resource_group_name
  workspace_id        = azurerm_log_analytics_workspace.this.id
  application_type    = "web"
  # No IP collection; telemetry carries no patient text.
  ip_masking_enabled = true
  tags               = var.tags
}

resource "azurerm_monitor_action_group" "this" {
  name                = var.names.action_group
  resource_group_name = var.resource_group_name
  short_name          = substr(var.action_group_short_name, 0, 12)
  tags                = var.tags

  dynamic "email_receiver" {
    for_each = toset(var.alert_emails)
    content {
      name                    = "email-${index(var.alert_emails, email_receiver.value)}"
      email_address           = email_receiver.value
      use_common_alert_schema = true
    }
  }
}
