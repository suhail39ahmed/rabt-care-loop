variable "names" {
  description = "Resource names: log_analytics, app_insights, action_group."
  type = object({
    log_analytics = string
    app_insights  = string
    action_group  = string
  })
}

variable "resource_group_name" {
  description = "Resource group."
  type        = string
}

variable "location" {
  description = "Region."
  type        = string
}

variable "retention_days" {
  description = "Log Analytics retention in days."
  type        = number
  default     = 30

  validation {
    condition     = var.retention_days >= 30 && var.retention_days <= 730
    error_message = "retention_days must be between 30 and 730."
  }
}

variable "alert_emails" {
  description = "Emails that receive alerts."
  type        = list(string)
}

variable "action_group_short_name" {
  description = "Action group short name (max 12 characters)."
  type        = string
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
