variable "key_vault_id" {
  description = "Key Vault to write into."
  type        = string
}

variable "secrets" {
  description = "Secrets keyed by a static name. Values stay sensitive; content_type documents what each is for."
  type = map(object({
    value        = string
    content_type = string
  }))
  sensitive = true
}

variable "secret_names" {
  description = "Static list of secret names (keys of var.secrets) so for_each works with sensitive values."
  type        = list(string)
}

variable "expiry_days" {
  description = "Expiry set on each secret (rotate before it)."
  type        = number
  default     = 180
}

variable "rbac_propagation_wait" {
  description = "Wait after role assignments before writing (Key Vault RBAC can take a minute to apply)."
  type        = string
  default     = "90s"
}

variable "tags" {
  description = "Tags applied to every secret."
  type        = map(string)
  default     = {}
}
