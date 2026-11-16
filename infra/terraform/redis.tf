# Optional semantic cache backend for APIM (azure-openai-semantic-cache-*). RediSearch is required.
resource "azurerm_managed_redis" "cache" {
  count                     = var.enable_semantic_cache ? 1 : 0
  name                      = "redis-${local.base}-${local.suffix}"
  location                  = local.locations.redis
  resource_group_name       = azurerm_resource_group.main.name
  sku_name                  = var.redis_sku_name
  high_availability_enabled = false
  public_network_access     = local.private ? "Disabled" : "Enabled"
  tags                      = local.tags

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
