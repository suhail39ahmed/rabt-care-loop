# Pilot environment sizing. Committed on purpose: no secrets, no personal data.
# Personal values (subscription, emails, your IP) go in terraform.tfvars locally (git-ignored)
# or in GitHub variables for the workflows (TF_VAR_*). See README.md, First-time bootstrap.

workload    = "rabt"
environment = "pilot"
location    = "uaenorth"
name_suffix = "" # set e.g. "01" only if a global name (APIM, Key Vault, Storage, ACR...) is taken

# Services or models that are not offered (or have no quota) in UAE North go to an allowed fallback region.
# Check model/region availability before apply.
# location_overrides = {
#   openai         = "swedencentral"
#   content_safety = "swedencentral"
# }
# openai_secondary_location = "swedencentral" # optional failover account in the APIM backend pool

enable_private_networking = true

openai_deployments = {
  chat-small  = { role = "small", model_name = "gpt-4.1-mini", model_version = "2025-04-14", sku_name = "Standard", capacity = 20 }
  chat-strong = { role = "strong", model_name = "gpt-4.1", model_version = "2025-04-14", sku_name = "Standard", capacity = 10 }
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
