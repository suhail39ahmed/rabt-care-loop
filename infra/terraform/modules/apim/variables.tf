variable "name" {
  description = "APIM instance name (globally unique), e.g. apim-rabt-pilot-uaen."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group."
  type        = string
}

variable "location" {
  description = "Region (must be the VNet region when subnet_id is set)."
  type        = string
}

variable "tags" {
  description = "Tags applied to the APIM instance."
  type        = map(string)
  default     = {}
}

variable "tenant_id" {
  description = "Entra tenant ID (for validate-jwt when auth_mode uses Entra ID)."
  type        = string
}

variable "sku_name" {
  description = "APIM SKU, e.g. Developer_1, BasicV2_1, StandardV2_1, Premium_1."
  type        = string

  validation {
    condition     = can(regex("^(Developer|BasicV2|StandardV2|Premium|PremiumV2)_[0-9]+$", var.sku_name))
    error_message = "sku_name must look like Developer_1, BasicV2_1, StandardV2_1 or Premium_1."
  }
}

variable "publisher_name" {
  description = "Publisher name shown in APIM."
  type        = string
}

variable "publisher_email" {
  description = "Publisher / notification email."
  type        = string
}

variable "subnet_id" {
  description = "Subnet for External VNet injection (classic Developer/Premium tiers). null = no VNet."
  type        = string
  default     = null
}

variable "public_ip_id" {
  description = "Static public IP used with VNet injection. null = none."
  type        = string
  default     = null
}

variable "auth_mode" {
  description = "How callers authenticate: subscription_key, entra_jwt or both."
  type        = string
  default     = "subscription_key"

  validation {
    condition     = contains(["subscription_key", "entra_jwt", "both"], var.auth_mode)
    error_message = "auth_mode must be subscription_key, entra_jwt or both."
  }
}

variable "jwt_audience" {
  description = "Expected audience when auth_mode uses entra_jwt."
  type        = string
  default     = ""
}

variable "app_insights_id" {
  description = "Application Insights resource ID for the APIM logger."
  type        = string
}

variable "app_insights_connection_string" {
  description = "Application Insights connection string for the APIM logger."
  type        = string
  sensitive   = true
}

variable "openai_backends" {
  description = "Azure OpenAI accounts behind the pool, keyed primary/secondary (primary gets priority 1)."
  type = map(object({
    endpoint = string
    location = string
  }))
}

variable "openai_deployment_names" {
  description = "Allowed values for the {deployment-id} template parameter."
  type        = list(string)
}

variable "embedding_deployment" {
  description = "Embedding deployment used by the semantic cache lookup."
  type        = string
}

variable "tokens_per_minute" {
  description = "azure-openai-token-limit per subscription."
  type        = number
  default     = 20000
}

variable "search_service_name" {
  description = "AI Search service name (backend https://<name>.search.windows.net)."
  type        = string
}

variable "search_index_name" {
  description = "The only index the read-only search API may query."
  type        = string
}

variable "search_calls_per_minute" {
  description = "Rate limit for the AI Search API per subscription."
  type        = number
  default     = 120
}

variable "enable_content_safety" {
  description = "Expose the Content Safety API."
  type        = bool
  default     = true
}

variable "content_safety_endpoint" {
  description = "Content Safety endpoint (required when enable_content_safety)."
  type        = string
  default     = null
}

variable "enable_semantic_cache" {
  description = "Add the semantic cache (needs var.redis)."
  type        = bool
  default     = false
}

variable "redis" {
  description = "Azure Managed Redis used as the external cache (required when enable_semantic_cache)."
  type = object({
    id                 = string
    hostname           = string
    primary_access_key = string
  })
  default   = null
  sensitive = true
}

variable "semantic_cache_score_threshold" {
  description = "Semantic cache score threshold (lower = stricter)."
  type        = number
  default     = 0.05
}

variable "semantic_cache_ttl_seconds" {
  description = "Cached answer lifetime."
  type        = number
  default     = 604800
}
