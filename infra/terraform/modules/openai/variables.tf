variable "resource_group_name" {
  description = "Resource group."
  type        = string
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}

variable "accounts" {
  description = "Azure OpenAI accounts keyed by role in the APIM pool (primary, secondary). Each gets the same deployments."
  type = map(object({
    name     = string
    location = string
  }))

  validation {
    condition     = contains(keys(var.accounts), "primary")
    error_message = "accounts must contain a primary account."
  }
}

variable "deployments" {
  description = "Model deployments keyed by deployment name; role = small, strong or embedding (used by the LLM router)."
  type = map(object({
    role          = string
    model_name    = string
    model_version = string
    sku_name      = string
    capacity      = number
  }))
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
