# VNet with three subnets (private endpoints, APIM injection, Container Apps), NSGs on every subnet,
# private DNS zones linked to the VNet, and the static public IP APIM needs in External mode.

resource "azurerm_virtual_network" "this" {
  name                = "vnet-${var.name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  address_space       = var.address_space
  tags                = var.tags
}

resource "azurerm_subnet" "private_endpoints" {
  name                              = "snet-private-endpoints"
  resource_group_name               = var.resource_group_name
  virtual_network_name              = azurerm_virtual_network.this.name
  address_prefixes                  = [var.subnet_private_endpoints_cidr]
  private_endpoint_network_policies = "Enabled"
}

resource "azurerm_subnet" "apim" {
  name                 = "snet-apim"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = [var.subnet_apim_cidr]
}

resource "azurerm_subnet" "apps" {
  name                 = "snet-apps"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = [var.subnet_apps_cidr]

  delegation {
    name = "container-apps"
    service_delegation {
      name    = "Microsoft.App/environments"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

# --- Private endpoint subnet: HTTPS (and Redis 10000) from inside the VNet only ---
resource "azurerm_network_security_group" "private_endpoints" {
  name                = "nsg-${var.name}-pe"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags

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
  subnet_id                 = azurerm_subnet.private_endpoints.id
  network_security_group_id = azurerm_network_security_group.private_endpoints.id
}

# --- APIM subnet: rules required by APIM classic tiers in External VNet mode ---
locals {
  apim_rules = {
    allow-client-https    = { priority = 100, direction = "Inbound", ports = ["443"], source = "Internet", destination = "VirtualNetwork" }
    allow-apim-management = { priority = 110, direction = "Inbound", ports = ["3443"], source = "ApiManagement", destination = "VirtualNetwork" }
    allow-azure-lb        = { priority = 120, direction = "Inbound", ports = ["6390"], source = "AzureLoadBalancer", destination = "VirtualNetwork" }
    allow-storage-out     = { priority = 100, direction = "Outbound", ports = ["443"], source = "VirtualNetwork", destination = "Storage" }
    allow-sql-out         = { priority = 110, direction = "Outbound", ports = ["1433"], source = "VirtualNetwork", destination = "Sql" }
    allow-keyvault-out    = { priority = 120, direction = "Outbound", ports = ["443"], source = "VirtualNetwork", destination = "AzureKeyVault" }
    allow-monitor-out     = { priority = 130, direction = "Outbound", ports = ["443", "1886"], source = "VirtualNetwork", destination = "AzureMonitor" }
    allow-entra-out       = { priority = 140, direction = "Outbound", ports = ["443"], source = "VirtualNetwork", destination = "AzureActiveDirectory" }
    allow-vnet-out        = { priority = 150, direction = "Outbound", ports = ["443", "10000"], source = "VirtualNetwork", destination = "VirtualNetwork" }
  }
}

resource "azurerm_network_security_group" "apim" {
  name                = "nsg-${var.name}-apim"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags

  dynamic "security_rule" {
    for_each = local.apim_rules
    content {
      name                       = security_rule.key
      priority                   = security_rule.value.priority
      direction                  = security_rule.value.direction
      access                     = "Allow"
      protocol                   = "Tcp"
      source_port_range          = "*"
      destination_port_ranges    = security_rule.value.ports
      source_address_prefix      = security_rule.value.source
      destination_address_prefix = security_rule.value.destination
    }
  }
}

resource "azurerm_subnet_network_security_group_association" "apim" {
  subnet_id                 = azurerm_subnet.apim.id
  network_security_group_id = azurerm_network_security_group.apim.id
}

# --- Container Apps subnet: public HTTPS (443 only) to the environment load balancer ---
resource "azurerm_network_security_group" "apps" {
  name                = "nsg-${var.name}-apps"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags

  security_rule {
    name                       = "allow-https-ingress"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_ranges    = ["443"]
    source_address_prefix      = "Internet"
    destination_address_prefix = "VirtualNetwork"
  }
}

resource "azurerm_subnet_network_security_group_association" "apps" {
  subnet_id                 = azurerm_subnet.apps.id
  network_security_group_id = azurerm_network_security_group.apps.id
}

# --- Private DNS ---
resource "azurerm_private_dns_zone" "this" {
  for_each            = var.private_dns_zones
  name                = each.value
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "this" {
  for_each              = var.private_dns_zones
  name                  = "link-${each.key}"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.this[each.key].name
  virtual_network_id    = azurerm_virtual_network.this.id
  registration_enabled  = false
  tags                  = var.tags
}

resource "azurerm_public_ip" "apim" {
  count               = var.apim_public_ip == null ? 0 : 1
  name                = var.apim_public_ip.name
  location            = var.apim_public_ip.location
  resource_group_name = var.resource_group_name
  allocation_method   = "Static"
  sku                 = "Standard"
  domain_name_label   = var.apim_public_ip.domain_name_label
  tags                = var.tags
}
