variable "resource_group_name" {
  description = "Resource group."
  type        = string
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}

variable "name" {
  description = "Azure Managed Redis name."
  type        = string
}

variable "location" {
  description = "Region."
  type        = string
}

variable "sku_name" {
  description = "Azure Managed Redis SKU."
  type        = string
  default     = "Balanced_B0"
}

variable "public_network_access_enabled" {
  description = "Allow the public endpoint."
  type        = bool
}
