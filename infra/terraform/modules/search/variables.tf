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
  description = "Allow the public endpoint (restricted to allowed_ips when private)."
  type        = bool
}

variable "allowed_ips" {
  description = "Public IPs allowed when the service is private (deployer IPs)."
  type        = list(string)
  default     = []
}

variable "sku" {
  description = "AI Search tier: basic or standard (S1)."
  type        = string
  default     = "basic"

  validation {
    condition     = contains(["basic", "standard"], var.sku)
    error_message = "sku must be basic or standard."
  }
}

variable "semantic_ranker" {
  description = "Semantic ranker plan: disabled, free or standard."
  type        = string
  default     = "free"

  validation {
    condition     = contains(["disabled", "free", "standard"], var.semantic_ranker)
    error_message = "semantic_ranker must be disabled, free or standard."
  }
}

variable "replica_count" {
  description = "Replicas (2+ for read SLA)."
  type        = number
  default     = 1
}

variable "partition_count" {
  description = "Partitions."
  type        = number
  default     = 1
}

variable "local_auth_enabled" {
  description = "Allow API keys (false = Entra ID / managed identity only)."
  type        = bool
  default     = false
}
