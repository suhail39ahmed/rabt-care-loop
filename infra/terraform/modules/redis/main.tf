# Semantic cache backend for APIM (azure-openai-semantic-cache-*). RediSearch is required.
resource "azurerm_managed_redis" "this" {
  name                      = var.name
  location                  = var.location
  resource_group_name       = var.resource_group_name
  sku_name                  = var.sku_name
  high_availability_enabled = false
  public_network_access     = var.public_network_access_enabled ? "Enabled" : "Disabled"
  tags                      = var.tags

  default_database {
    # APIM's external cache connection uses an access key; it is stored only inside APIM.
    access_keys_authentication_enabled = true
    client_protocol                    = "Encrypted"
    clustering_policy                  = "EnterpriseCluster"
    eviction_policy                    = "NoEviction"

    module {
      name = "RediSearch"
    }
  }
}
