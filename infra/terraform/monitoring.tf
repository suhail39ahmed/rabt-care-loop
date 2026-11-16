resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-${local.base}-${local.suffix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = var.log_retention_days
  tags                = local.tags
}

resource "azurerm_application_insights" "main" {
  name                = "appi-${local.base}-${local.suffix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"
  # No IP collection; telemetry carries no patient text (see README).
  ip_masking_enabled = true
  tags               = local.tags
}

resource "azurerm_monitor_action_group" "main" {
  name                = "ag-${local.base}"
  resource_group_name = azurerm_resource_group.main.name
  short_name          = substr("${var.name_prefix}alert", 0, 12)
  tags                = local.tags

  dynamic "email_receiver" {
    for_each = toset(var.budget_contact_emails)
    content {
      name                    = "email-${index(var.budget_contact_emails, email_receiver.value)}"
      email_address           = email_receiver.value
      use_common_alert_schema = true
    }
  }
}

resource "azurerm_consumption_budget_resource_group" "main" {
  name              = "budget-${local.base}"
  resource_group_id = azurerm_resource_group.main.id
  amount            = var.budget_amount
  time_grain        = "Monthly"

  time_period {
    start_date = coalesce(var.budget_start_date, formatdate("YYYY-MM-01'T'00:00:00Z", timestamp()))
  }

  dynamic "notification" {
    for_each = { actual50 = [50, "Actual"], actual80 = [80, "Actual"], actual100 = [100, "Actual"], forecast100 = [100, "Forecasted"] }
    content {
      enabled        = true
      threshold      = notification.value[0]
      threshold_type = notification.value[1]
      operator       = "GreaterThanOrEqualTo"
      contact_emails = var.budget_contact_emails
      contact_groups = [azurerm_monitor_action_group.main.id]
    }
  }

  lifecycle {
    # start_date is computed once; don't move it on every plan.
    ignore_changes = [time_period]
  }
}
