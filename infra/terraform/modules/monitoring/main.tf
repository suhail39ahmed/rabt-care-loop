resource "azurerm_log_analytics_workspace" "this" {
  name                = var.names.log_analytics
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = var.retention_days
  tags                = var.tags
}

resource "azurerm_application_insights" "this" {
  name                = var.names.app_insights
  location            = var.location
  resource_group_name = var.resource_group_name
  workspace_id        = azurerm_log_analytics_workspace.this.id
  application_type    = "web"
  # No IP collection; telemetry carries no patient text.
  ip_masking_enabled = true
  tags               = var.tags
}

resource "azurerm_monitor_action_group" "this" {
  name                = var.names.action_group
  resource_group_name = var.resource_group_name
  short_name          = substr(var.action_group_short_name, 0, 12)
  tags                = var.tags

  dynamic "email_receiver" {
    for_each = toset(var.alert_emails)
    content {
      name                    = "email-${index(var.alert_emails, email_receiver.value)}"
      email_address           = email_receiver.value
      use_common_alert_schema = true
    }
  }
}

# ---------------------------------------------------------------------------
# AI alerts. Sources: API log events (`rabt.ai` logger -> traces.customDimensions) and the APIM
# token metric (azure-openai-emit-token-metric -> customMetrics "Total Tokens").
# ---------------------------------------------------------------------------
locals {
  ai_alerts = var.ai_alerts_enabled ? {
    safety-blocks = {
      description = "Content Safety, Prompt Shields or injection blocks spiked (possible attack or bad prompt)."
      severity    = 2
      query       = <<-KQL
        traces
        | where tostring(customDimensions.ai_event) in ("content_safety_blocks", "prompt_shield_blocks", "injection_blocks")
        | summarize blocks = count()
      KQL
      threshold   = var.ai_alert_safety_blocks
    }
    llm-errors = {
      description = "LLM calls failing after gateway retries and tier failover."
      severity    = 2
      query       = <<-KQL
        traces
        | where tostring(customDimensions.ai_event) in ("llm_errors", "content_safety_errors")
        | summarize errors = count()
      KQL
      threshold   = var.ai_alert_llm_errors
    }
    budget-refusals = {
      description = "The API refused LLM calls because the daily token budget is used up."
      severity    = 3
      query       = <<-KQL
        traces
        | where tostring(customDimensions.ai_event) == "budget_refusals"
        | summarize refusals = count()
      KQL
      threshold   = 0
    }
    token-burn = {
      description = "Tokens through the APIM AI gateway in the last hour are above the expected pilot level."
      severity    = 3
      query       = <<-KQL
        customMetrics
        | where name == "Total Tokens"
        | summarize tokens = sum(valueSum)
      KQL
      threshold   = var.ai_alert_hourly_tokens
    }
  } : {}
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "ai" {
  for_each = local.ai_alerts

  name                    = "alert-${var.names.app_insights}-${each.key}"
  resource_group_name     = var.resource_group_name
  location                = var.location
  description             = each.value.description
  severity                = each.value.severity
  scopes                  = [azurerm_application_insights.this.id]
  evaluation_frequency    = each.key == "token-burn" ? "PT1H" : "PT15M"
  window_duration         = each.key == "token-burn" ? "PT1H" : "PT15M"
  enabled                 = true
  auto_mitigation_enabled = true

  criteria {
    query                   = each.value.query
    time_aggregation_method = "Maximum"
    metric_measure_column   = one([for c in ["blocks", "errors", "refusals", "tokens"] : c if strcontains(each.value.query, "${c} =")])
    operator                = "GreaterThan"
    threshold               = each.value.threshold

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.this.id]
  }

  tags = var.tags
}
