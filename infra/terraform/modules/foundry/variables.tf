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
  description = "Foundry account name (also the custom subdomain)."
  type        = string
}

variable "location" {
  description = "Region (use australiaeast when Content Safety must colocate)."
  type        = string
}

variable "sku_name" {
  description = "Cognitive account SKU for AIServices (S0)."
  type        = string
  default     = "S0"
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

variable "project_name" {
  description = "Optional Foundry project resource name (null = account only)."
  type        = string
  default     = "rabt-pilot"
}

variable "project_display_name" {
  description = "Foundry project display name."
  type        = string
  default     = "Rabt pilot"
}

variable "project_description" {
  description = "Foundry project description."
  type        = string
  default     = "Rabt care-loop pilot: Content Safety, Language PII, evals. Traffic via APIM AI gateway."
}
