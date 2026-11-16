variable "log_analytics_workspace_id" {
  description = "Workspace receiving logs and metrics."
  type        = string
}

variable "targets" {
  description = "Resources to send diagnostics for, keyed by a static name. logs=false sends metrics only."
  type = map(object({
    resource_id     = string
    metric_category = optional(string, "AllMetrics")
    logs            = optional(bool, true)
  }))
}
