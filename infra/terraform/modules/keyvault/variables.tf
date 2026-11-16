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

variable "tenant_id" {
  description = "Entra tenant ID."
  type        = string
}

variable "ip_rules" {
  description = "Public IPs/CIDRs allowed through the firewall (deployer IPs)."
  type        = list(string)
  default     = []
}
