variable "name" {
  description = "Naming base; endpoints are named pe-<name>-<key>."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group for the endpoints."
  type        = string
}

variable "location" {
  description = "Region of the endpoints (the VNet region)."
  type        = string
}

variable "subnet_id" {
  description = "Subnet the endpoints are placed in."
  type        = string
}

variable "endpoints" {
  description = "Endpoints keyed by a static short name. resource_id/dns_zone_id may be unknown until apply; keys must be static."
  type = map(object({
    resource_id = string
    subresource = string
    dns_zone_id = string
  }))
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
