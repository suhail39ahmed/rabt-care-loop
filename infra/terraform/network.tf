# Private networking (enable_private_networking = true):
# VNet + private endpoints + private DNS zones; APIM is injected into the VNet (External mode)
# so the public gateway URL stays reachable from Render while backends stay private.

locals {
  private_dns_zones = local.private ? merge(
    {
      openai = "privatelink.openai.azure.com"
      search = "privatelink.search.windows.net"
      vault  = "privatelink.vaultcore.azure.net"
      blob   = "privatelink.blob.core.windows.net"
    },
    var.enable_content_safety ? { cognitive = "privatelink.cognitiveservices.azure.com" } : {},
    var.enable_semantic_cache ? { redis = "privatelink.redis.azure.net" } : {}
  ) : {}

  private_endpoints = local.private ? merge(
    {
      for k, a in azurerm_cognitive_account.openai : "openai-${k}" => {
        resource_id = a.id
        subresource = "account"
        zone        = "openai"
      }
    },
    {
      search = { resource_id = azurerm_search_service.main.id, subresource = "searchService", zone = "search" }
      vault  = { resource_id = azurerm_key_vault.main.id, subresource = "vault", zone = "vault" }
      blob   = { resource_id = azurerm_storage_account.kb.id, subresource = "blob", zone = "blob" }
    },
    var.enable_content_safety ? {
      contentsafety = { resource_id = azurerm_cognitive_account.content_safety[0].id, subresource = "account", zone = "cognitive" }
    } : {},
    var.enable_semantic_cache ? {
      redis = { resource_id = azurerm_managed_redis.cache[0].id, subresource = "redisEnterprise", zone = "redis" }
    } : {}
  ) : {}

  # Static key list for for_each (values may be unknown until apply).
  private_endpoint_keys = local.private ? concat(
    [for k in keys(local.openai_accounts) : "openai-${k}"],
    ["search", "vault", "blob"],
    var.enable_content_safety ? ["contentsafety"] : [],
    var.enable_semantic_cache ? ["redis"] : []
  ) : []
}

resource "azurerm_virtual_network" "main" {
  count               = local.private ? 1 : 0
  name                = "vnet-${local.base}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  address_space       = var.vnet_address_space
  tags                = local.tags
}

resource "azurerm_subnet" "private_endpoints" {
  count                             = local.private ? 1 : 0
  name                              = "snet-private-endpoints"
  resource_group_name               = azurerm_resource_group.main.name
  virtual_network_name              = azurerm_virtual_network.main[0].name
  address_prefixes                  = [var.subnet_private_endpoints_cidr]
  private_endpoint_network_policies = "Enabled"
}

resource "azurerm_subnet" "apim" {
  count                = local.private ? 1 : 0
  name                 = "snet-apim"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main[0].name
  address_prefixes     = [var.subnet_apim_cidr]
}

resource "azurerm_network_security_group" "private_endpoints" {
  count               = local.private ? 1 : 0
  name                = "nsg-${local.base}-pe"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags

  security_rule {
    name                       = "allow-vnet-https"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_ranges    = ["443", "10000"]
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "VirtualNetwork"
  }

  security_rule {
    name                       = "deny-all-inbound"
    priority                   = 4096
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

resource "azurerm_subnet_network_security_group_association" "private_endpoints" {
  count                     = local.private ? 1 : 0
  subnet_id                 = azurerm_subnet.private_endpoints[0].id
  network_security_group_id = azurerm_network_security_group.private_endpoints[0].id
}

# NSG rules required for APIM (classic tiers) in External VNet mode.
resource "azurerm_network_security_group" "apim" {
  count               = local.private ? 1 : 0
  name                = "nsg-${local.base}-apim"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags

  security_rule {
    name                       = "allow-client-https"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "Internet"
    destination_address_prefix = "VirtualNetwork"
  }

  security_rule {
    name                       = "allow-apim-management"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "3443"
    source_address_prefix      = "ApiManagement"
    destination_address_prefix = "VirtualNetwork"
  }

  security_rule {
    name                       = "allow-azure-lb"
    priority                   = 120
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "6390"
    source_address_prefix      = "AzureLoadBalancer"
    destination_address_prefix = "VirtualNetwork"
  }

  security_rule {
    name                       = "allow-storage-out"
    priority                   = 100
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "Storage"
  }

  security_rule {
    name                       = "allow-sql-out"
    priority                   = 110
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "1433"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "Sql"
  }

  security_rule {
    name                       = "allow-keyvault-out"
    priority                   = 120
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "AzureKeyVault"
  }

  security_rule {
    name                       = "allow-monitor-out"
    priority                   = 130
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_ranges    = ["443", "1886"]
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "AzureMonitor"
  }

  security_rule {
    name                       = "allow-entra-out"
    priority                   = 140
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "AzureActiveDirectory"
  }

  security_rule {
    name                       = "allow-vnet-out"
    priority                   = 150
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_ranges    = ["443", "10000"]
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "VirtualNetwork"
  }
}

resource "azurerm_subnet_network_security_group_association" "apim" {
  count                     = local.private ? 1 : 0
  subnet_id                 = azurerm_subnet.apim[0].id
  network_security_group_id = azurerm_network_security_group.apim[0].id
}

resource "azurerm_private_dns_zone" "zones" {
  for_each            = local.private_dns_zones
  name                = each.value
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "links" {
  for_each              = local.private_dns_zones
  name                  = "link-${each.key}"
  resource_group_name   = azurerm_resource_group.main.name
  private_dns_zone_name = azurerm_private_dns_zone.zones[each.key].name
  virtual_network_id    = azurerm_virtual_network.main[0].id
  registration_enabled  = false
  tags                  = local.tags
}

resource "azurerm_private_endpoint" "pe" {
  for_each            = toset(local.private_endpoint_keys)
  name                = "pe-${local.base}-${each.key}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = azurerm_subnet.private_endpoints[0].id
  tags                = local.tags

  private_service_connection {
    name                           = "psc-${each.key}"
    private_connection_resource_id = local.private_endpoints[each.key].resource_id
    subresource_names              = [local.private_endpoints[each.key].subresource]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [azurerm_private_dns_zone.zones[local.private_endpoints[each.key].zone].id]
  }
}

resource "azurerm_public_ip" "apim" {
  count               = local.private ? 1 : 0
  name                = "pip-${local.base}-apim"
  location            = local.locations.apim
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"
  domain_name_label   = "${var.name_prefix}-${var.environment}-apim-${local.suffix}"
  tags                = local.tags
}
