# Cost guardrail, delete lock and (optional, subscription-wide) Defender for Cloud plans.

resource "azurerm_consumption_budget_resource_group" "this" {
  name              = "budget-${var.name}"
  resource_group_id = var.resource_group_id
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
      contact_emails = var.contact_emails
      contact_groups = [var.action_group_id]
    }
  }

  lifecycle {
    # start_date is computed once; don't move it on every plan.
    ignore_changes = [time_period]
  }
}

resource "azurerm_management_lock" "rg" {
  count      = var.enable_resource_lock ? 1 : 0
  name       = "lock-${var.name}"
  scope      = var.resource_group_id
  lock_level = "CanNotDelete"
  notes      = "Remove before terraform destroy."
}

# NOTE: subscription-wide; covers every resource of that type in the subscription, not only Rabt.
resource "azurerm_security_center_subscription_pricing" "plans" {
  for_each      = toset(var.defender_plans)
  tier          = "Standard"
  resource_type = each.value
  subplan       = each.value == "StorageAccounts" ? "DefenderForStorageV2" : null
}
