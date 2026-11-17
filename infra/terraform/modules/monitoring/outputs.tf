output "log_analytics_workspace_id" {
  description = "Log Analytics workspace ID."
  value       = azurerm_log_analytics_workspace.this.id
}

output "app_insights_id" {
  description = "Application Insights ID."
  value       = azurerm_application_insights.this.id
}

output "app_insights_connection_string" {
  description = "Application Insights connection string."
  value       = azurerm_application_insights.this.connection_string
  sensitive   = true
}

output "app_insights_instrumentation_key" {
  description = "Application Insights instrumentation key (Foundry AppInsights connection)."
  value       = azurerm_application_insights.this.instrumentation_key
  sensitive   = true
}

output "action_group_id" {
  description = "Action group ID for alerts and the budget."
  value       = azurerm_monitor_action_group.this.id
}
