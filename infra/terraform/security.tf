# Microsoft Defender for Cloud plans. NOTE: these are subscription-wide (they cover every resource of
# that type in the subscription, not only Rabt) and are billed per resource / transaction.
resource "azurerm_security_center_subscription_pricing" "plans" {
  for_each      = var.enable_defender_plans ? toset(var.defender_plans) : toset([])
  tier          = "Standard"
  resource_type = each.value
  subplan       = each.value == "StorageAccounts" ? "DefenderForStorageV2" : null
}
