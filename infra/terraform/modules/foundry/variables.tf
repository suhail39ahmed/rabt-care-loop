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
  description = "Region (australiaeast when Content Safety / model SKUs require it)."
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

variable "deployments" {
  description = "OpenAI model deployments on this Foundry account (chat + embeddings)."
  type = map(object({
    role          = string
    model_name    = string
    model_version = string
    sku_name      = string
    capacity      = number
  }))
  default = {}
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
  default     = "Rabt care-loop pilot: OpenAI, Content Safety, Language PII via APIM AI gateway; App Insights for tracing/evals."
}

variable "enable_application_insights_connection" {
  description = "Create the Foundry ↔ Application Insights account connection."
  type        = bool
  default     = true
}

variable "application_insights_id" {
  description = "Application Insights resource ID (required when enable_application_insights_connection)."
  type        = string
  default     = ""
}

variable "application_insights_connection_string" {
  description = "Application Insights connection string for the Foundry AppInsights connection (required by the API)."
  type        = string
  default     = ""
  sensitive   = true
}
