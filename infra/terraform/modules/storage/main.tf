# Approved KB source documents for the ingestion pipeline. Private, Entra ID only (no shared keys).
resource "azurerm_storage_account" "this" {
  #checkov:skip=CKV_AZURE_59:public network access only when not private or for allowlisted deployer IPs; anonymous blob access is always off
  #checkov:skip=CKV_AZURE_43:name is built from validated parts in the root naming locals (lowercase alphanumerics, <= 24 chars)
  name                              = var.name
  location                          = var.location
  resource_group_name               = var.resource_group_name
  account_tier                      = "Standard"
  account_kind                      = "StorageV2"
  account_replication_type          = var.replication_type
  min_tls_version                   = "TLS1_2"
  https_traffic_only_enabled        = true
  shared_access_key_enabled         = false
  default_to_oauth_authentication   = true
  allow_nested_items_to_be_public   = false
  public_network_access_enabled     = var.public_network_access_enabled
  infrastructure_encryption_enabled = true
  cross_tenant_replication_enabled  = false
  local_user_enabled                = false
  sftp_enabled                      = false
  tags                              = var.tags

  blob_properties {
    versioning_enabled = true

    delete_retention_policy {
      days = 14
    }

    container_delete_retention_policy {
      days = 14
    }
  }

  network_rules {
    default_action = var.network_default_action
    bypass         = ["AzureServices"]
    ip_rules       = var.ip_rules
  }

  sas_policy {
    expiration_period = "00.01:00:00"
    expiration_action = "Log"
  }
}

resource "azurerm_storage_container" "kb" {
  #checkov:skip=CKV2_AZURE_21:blob read/write/delete logs go to Log Analytics via the diagnostic setting on blobServices/default
  name                  = var.container_name
  storage_account_id    = azurerm_storage_account.this.id
  container_access_type = "private"
}
