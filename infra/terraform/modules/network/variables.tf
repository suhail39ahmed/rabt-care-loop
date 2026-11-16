variable "name" {
  description = "Naming base, e.g. rabt-pilot-uaen. Resources are named vnet-<name>, nsg-<name>-<subnet>."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group for the network resources."
  type        = string
}

variable "location" {
  description = "Region of the VNet."
  type        = string
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}

variable "address_space" {
  description = "VNet address space."
  type        = list(string)
}

variable "subnet_private_endpoints_cidr" {
  description = "Subnet for private endpoints."
  type        = string
}

variable "subnet_apim_cidr" {
  description = "Subnet for API Management VNet injection (/27 or larger)."
  type        = string
}

variable "subnet_apps_cidr" {
  description = "Subnet for the Container Apps environment (/27 or larger, delegated to Microsoft.App/environments)."
  type        = string
}

variable "private_dns_zones" {
  description = "Private DNS zones to create and link to the VNet, keyed by short name (openai, search, vault, blob, ...)."
  type        = map(string)
}

variable "apim_public_ip" {
  description = "Static public IP for APIM in External VNet mode (classic tiers need one). null = none."
  type = object({
    name              = string
    location          = string
    domain_name_label = string
  })
  default = null
}
