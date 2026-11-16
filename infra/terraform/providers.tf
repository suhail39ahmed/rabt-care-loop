provider "azurerm" {
  # Falls back to ARM_SUBSCRIPTION_ID / `az account show` when null.
  subscription_id = var.subscription_id

  # Storage has shared keys disabled, so data-plane calls use Entra ID.
  storage_use_azuread = true

  features {
    key_vault {
      # Purge protection is on; never purge on destroy.
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }
    cognitive_account {
      purge_soft_delete_on_destroy = false
    }
    resource_group {
      prevent_deletion_if_contains_resources = true
    }
    api_management {
      purge_soft_delete_on_destroy = false
      recover_soft_deleted         = true
    }
  }
}

provider "azapi" {
  subscription_id = var.subscription_id
}
