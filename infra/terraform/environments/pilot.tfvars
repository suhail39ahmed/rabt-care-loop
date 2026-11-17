# Pilot environment sizing. Committed on purpose: no secrets, no personal data.
# Personal values (subscription, emails, your IP) go in terraform.tfvars locally (git-ignored)
# or in GitHub repository secrets for the workflows (TF_VAR_*). See README.md, First-time bootstrap.

workload    = "rabt"
environment = "pilot"
location    = "southeastasia" # Singapore
name_suffix = ""              # set e.g. "01" only if a global name (APIM, Key Vault, Storage, ACR...) is taken

# Southeast Asia has no regional Standard deployment of gpt-4.1-mini / gpt-4o / text-embedding-3-small,
# and standalone Content Safety (text moderation, Prompt Shields) is not offered there. Both run in
# Australia East, so prompts are processed in Australia; everything else stays in Singapore.
# Evidence and the GlobalStandard trade-off: infra/terraform/README.md, Regions.
location_overrides = {
  openai         = "australiaeast"
  content_safety = "australiaeast"
  foundry        = "australiaeast"
}
# openai_secondary_location: leave unset. No second APAC region in the allowlist offers these models as regional Standard.

# Path B for demo: public endpoints, Entra-only (keys off). Path A needs VNet CIDR fix + ~US$45/mo. See #148.
enable_private_networking = false

# Foundry hub (AIServices + rabt-pilot project) for Content Safety / Language PII portal + App Insights. APIM stays the gateway.
enable_foundry       = true
foundry_project_name = "rabt-pilot"

openai_deployments = {
  chat-small  = { role = "small", model_name = "gpt-4.1-mini", model_version = "2025-04-14", sku_name = "Standard", capacity = 20 }
  chat-strong = { role = "strong", model_name = "gpt-4o", model_version = "2024-11-20", sku_name = "Standard", capacity = 10 }
  embed       = { role = "embedding", model_name = "text-embedding-3-small", model_version = "1", sku_name = "Standard", capacity = 20 }
}

search_sku             = "basic"
search_semantic_ranker = "free"

apim_sku_name       = "Developer_1"
apim_publisher_name = "Rabt"
apim_auth_mode      = "subscription_key"

enable_content_safety = true
enable_semantic_cache = false

# Kill switch for the deployed API: false = templates only (safe default for a public demo).
ai_enabled = false

registry_sku     = "Basic"
api_min_replicas = 1
web_min_replicas = 1

budget_amount         = 100
enable_defender_plans = false
enable_resource_lock  = false

tags = {
  owner = "suhail"
}
