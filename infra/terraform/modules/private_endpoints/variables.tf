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
  description = "Endpoints keyed by a static short name. Pass dns_zone_id or dns_zone_ids (Foundry needs both OpenAI + Cognitive zones)."
  type = map(object({
    resource_id   = string
    subresource   = string
    dns_zone_id   = optional(string)
    dns_zone_ids  = optional(list(string))
  }))
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
