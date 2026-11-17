# Offline plan tests with mocked providers: no Azure credentials or subscription calls.
# Run: terraform init -backend=false && terraform test
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

run "naming_convention" {
  command = plan

  assert {
    condition     = azurerm_resource_group.main.name == "rg-rabt-pilot-sea"
    error_message = "Resource group must follow rg-<workload>-<env>-<region>."
  }
  assert {
    condition     = output.names.apim == "apim-rabt-pilot-sea" && output.names.key_vault == "kv-rabt-pilot-sea"
    error_message = "APIM / Key Vault names must follow the convention."
  }
  assert {
    condition     = output.names.storage_kb == "strabtpilotseakb" && output.names.registry == "crrabtpilotsea"
    error_message = "Hyphen-free names must follow the convention."
  }
  assert {
    condition     = output.names.foundry == "aif-rabt-pilot-aue"
    error_message = "Foundry overridden to Australia East must carry the aue code."
  }
  assert {
    condition     = module.hosting.insurer_app_name == "ca-rabt-insurer-pilot"
    error_message = "The demo insurer agent must be deployed by default and follow the naming convention."
  }
  assert {
    condition     = output.kb_ingest_job_name == "caj-rabt-ingest-pilot"
    error_message = "The KB ingestion job must exist by default and follow the naming convention."
  }
  assert {
    condition     = azurerm_resource_group.main.location == "southeastasia"
    error_message = "Primary region must be Southeast Asia."
  }
}

run "defaults_private" {
  command = plan

  assert {
    condition     = toset(output.security_summary.private_endpoints) == toset(["blob", "foundry", "search", "vault"])
    error_message = "Expected private endpoints for Foundry, Search, KV and Storage."
  }
  assert {
    condition     = output.security_summary.ai_local_auth_enabled == false
    error_message = "Foundry local auth must be disabled."
  }
  assert {
    condition     = output.security_summary.apim_log_body_bytes == 0
    error_message = "APIM must not log request bodies."
  }
  assert {
    condition     = output.security_summary.key_vault_secrets_written == false && length(module.secrets) == 0
    error_message = "Fully private without deployer IPs: Terraform must not try to write secrets."
  }
  assert {
    condition     = length(module.network) == 1
    error_message = "Private networking must create the network module."
  }
  assert {
    condition     = contains(output.security_summary.diagnostics_targets, "apim") && contains(output.security_summary.diagnostics_targets, "foundry")
    error_message = "APIM and Foundry must send diagnostics to Log Analytics."
  }
}

run "public_with_cache" {
  command = plan

  variables {
    enable_private_networking = false
    apim_sku_name             = "BasicV2_1"
    enable_semantic_cache     = true
    apim_auth_mode            = "both"
    apim_jwt_audience         = "api://rabt"
    name_suffix               = "01"
  }

  assert {
    condition     = length(module.network) == 0 && length(module.private_endpoints) == 0
    error_message = "No network resources expected when private networking is off."
  }
  assert {
    condition     = output.names.foundry == "aif-rabt-pilot-aue-01" && endswith(output.names.apim, "-sea-01")
    error_message = "Foundry suffix and APIM suffix must follow the convention."
  }
  assert {
    condition     = output.security_summary.key_vault_secrets_written == true
    error_message = "Public setup access: Terraform writes the Key Vault secrets."
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
    location_overrides = { foundry = "uaenorth" }
  }

  expect_failures = [terraform_data.guardrails]
}

run "rejects_foundry_disabled" {
  command = plan

  variables {
    enable_foundry = false
  }

  expect_failures = [terraform_data.guardrails]
}
