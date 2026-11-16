variable "name" {
  description = "Resource name."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group."
  type        = string
}

variable "location" {
  description = "Region."
  type        = string
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}

variable "public_network_access_enabled" {
  description = "Allow the public endpoint (firewalled when default_action is Deny)."
  type        = bool
}

variable "network_default_action" {
  description = "Firewall default action: Deny when private networking is on."
  type        = string

  validation {
    condition     = contains(["Allow", "Deny"], var.network_default_action)
    error_message = "network_default_action must be Allow or Deny."
  }
}

variable "replication_type" {
  description = "Replication: LRS, ZRS, GRS or GZRS."
  type        = string
  default     = "ZRS"

  validation {
    condition     = contains(["LRS", "ZRS", "GRS", "GZRS"], var.replication_type)
    error_message = "replication_type must be LRS, ZRS, GRS or GZRS."
  }
}

variable "container_name" {
  description = "Private blob container for approved KB source documents."
  type        = string
  default     = "kb-docs"
}

variable "ip_rules" {
  description = "Public IPs/CIDRs allowed through the firewall (deployer IPs)."
  type        = list(string)
  default     = []
}
