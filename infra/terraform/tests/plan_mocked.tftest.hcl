# Offline plan tests with mocked providers: no Azure credentials or subscription calls.
# Run: terraform test   (Terraform >= 1.7)
mock_provider "azurerm" {
  mock_data "azurerm_client_config" {
    defaults = {
      tenant_id       = "11111111-1111-1111-1111-111111111111"
      object_id       = "22222222-2222-2222-2222-222222222222"
      client_id       = "33333333-3333-3333-3333-333333333333"
      subscription_id = "00000000-0000-0000-0000-000000000000"
    }
  }
}
mock_provider "azapi" {}

variables {
  subscription_id       = "00000000-0000-0000-0000-000000000000"
  apim_publisher_email  = "ops@example.com"
  budget_contact_emails = ["ops@example.com"]
  budget_start_date     = "2026-12-01T00:00:00Z"
}

run "defaults_private" {
  command = plan

  assert {
    condition     = length(azurerm_private_endpoint.pe) == 5
    error_message = "Expected private endpoints for AOAI, Search, KV, Storage and Content Safety."
  }
  assert {
    condition     = azurerm_cognitive_account.openai["primary"].local_auth_enabled == false
    error_message = "Azure OpenAI local auth must be disabled."
  }
  assert {
    condition     = azurerm_api_management_diagnostic.appinsights.frontend_request[0].body_bytes == 0
    error_message = "APIM must not log request bodies."
  }
  assert {
    condition     = length(azurerm_key_vault_secret.apim_rabt_key) == 0
    error_message = "Fully private without deployer IPs: Terraform must not try to write secrets."
  }
}

run "public_with_cache_and_failover" {
  command = plan

  variables {
    enable_private_networking = false
    apim_sku_name             = "BasicV2_1"
    enable_semantic_cache     = true
    openai_secondary_location = "swedencentral"
    apim_auth_mode            = "both"
    apim_jwt_audience         = "api://rabt"
  }

  assert {
    condition     = length(azurerm_private_endpoint.pe) == 0 && length(azurerm_virtual_network.main) == 0
    error_message = "No network resources expected when private networking is off."
  }
  assert {
    condition     = length(azurerm_api_management_backend.openai) == 2
    error_message = "Expected two Azure OpenAI backends in the pool."
  }
  assert {
    condition     = strcontains(azurerm_api_management_api_policy.openai.xml_content, "azure-openai-semantic-cache-lookup") && strcontains(azurerm_api_management_api_policy.openai.xml_content, "validate-jwt")
    error_message = "Policy must include semantic cache and JWT validation."
  }
}

run "rejects_v2_sku_when_private" {
  command = plan

  variables {
    apim_sku_name = "BasicV2_1"
  }

  expect_failures = [terraform_data.guardrails]
}

run "rejects_region_outside_allowlist" {
  command = plan

  variables {
    location_overrides = { openai = "westus" }
  }

  expect_failures = [terraform_data.guardrails]
}
