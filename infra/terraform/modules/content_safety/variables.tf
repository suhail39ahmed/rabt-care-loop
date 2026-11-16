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
  description = "Account name (also the custom subdomain)."
  type        = string
}

variable "location" {
  description = "Region."
  type        = string
}

variable "local_auth_enabled" {
  description = "Allow API keys (false = Entra ID / managed identity only)."
  type        = bool
  default     = false
}

variable "public_network_access_enabled" {
  description = "Allow the public endpoint."
  type        = bool
}

variable "network_default_action" {
  description = "Firewall default action: Deny when private networking is on."
  type        = string
}
