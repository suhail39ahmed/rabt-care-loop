output "targets" {
  description = "Keys of the resources that have a diagnostic setting."
  value       = keys(azurerm_monitor_diagnostic_setting.this)
}
