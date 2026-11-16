data "azurerm_client_config" "current" {}

resource "random_string" "suffix" {
  length  = 5
  lower   = true
  upper   = false
  numeric = true
  special = false
}

resource "azurerm_resource_group" "main" {
  name     = "rg-${local.base}-${local.suffix}"
  location = var.location
  tags     = local.tags
}

# Cross-variable checks (kept here so Terraform >= 1.6 can evaluate them).
resource "terraform_data" "guardrails" {
  input = local.all_locations

  lifecycle {
    precondition {
      condition     = alltrue([for l in local.all_locations : contains(var.allowed_locations, l)])
      error_message = "All locations (location, location_overrides, openai_secondary_location) must be in allowed_locations."
    }
    precondition {
      condition     = !local.private || local.apim_classic_sku
      error_message = "enable_private_networking needs an APIM SKU with VNet injection (Developer_* or Premium_*) so the gateway can reach private endpoints."
    }
    precondition {
      condition     = !local.private || local.locations.apim == var.location
      error_message = "With enable_private_networking, APIM must be in var.location (same region as the VNet it is injected into)."
    }
    precondition {
      condition     = var.apim_auth_mode == "subscription_key" || length(var.apim_jwt_audience) > 0
      error_message = "apim_jwt_audience is required when apim_auth_mode is entra_jwt or both."
    }
    precondition {
      condition     = length(local.deployments_by_role.small) > 0 && length(local.deployments_by_role.strong) > 0
      error_message = "openai_deployments needs at least one small and one strong deployment for the router."
    }
  }
}

resource "azurerm_management_lock" "rg" {
  count      = var.enable_resource_lock ? 1 : 0
  name       = "lock-${local.base}"
  scope      = azurerm_resource_group.main.id
  lock_level = "CanNotDelete"
  notes      = "Remove before terraform destroy."
}
