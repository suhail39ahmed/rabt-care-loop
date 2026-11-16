# ---------------------------------------------------------------------------
# Naming convention: <type>-<workload>-<environment>-<region code>[-<suffix>]
#   rg-rabt-pilot-sea, apim-rabt-pilot-sea, kv-rabt-pilot-sea, srch-rabt-pilot-sea ...
# Names without hyphens (Storage, ACR) drop them: strabtpilotseakb, crrabtpilotsea.
# Services placed in another region by location_overrides carry that region's code (oai-rabt-pilot-aue).
# Abbreviations follow the Microsoft Cloud Adoption Framework list.
# ---------------------------------------------------------------------------
locals {
  region_codes = {
    southeastasia = "sea"
    australiaeast = "aue"
  }

  region = local.region_codes[var.location]
  base   = "${var.workload}-${var.environment}-${local.region}"
  sfx    = var.name_suffix == "" ? "" : "-${var.name_suffix}"
  flat   = "${var.workload}${var.environment}${local.region}${var.name_suffix}"

  private = var.enable_private_networking

  locations = {
    primary        = var.location
    openai         = lookup(var.location_overrides, "openai", var.location)
    content_safety = lookup(var.location_overrides, "content_safety", var.location)
    apim           = lookup(var.location_overrides, "apim", var.location)
    redis          = lookup(var.location_overrides, "redis", var.location)
    search         = lookup(var.location_overrides, "search", var.location)
  }

  all_locations = distinct(compact(concat(values(local.locations), [var.openai_secondary_location])))

  openai_accounts = merge(
    { primary = local.locations.openai },
    var.openai_secondary_location == null ? {} : { secondary = var.openai_secondary_location }
  )

  names = {
    resource_group = "rg-${local.base}"
    vnet           = local.base
    apim           = "apim-${local.base}${local.sfx}"
    apim_pip_label = "apim-${local.base}${local.sfx}"
    key_vault      = "kv-${local.base}${local.sfx}"
    storage_kb     = "st${local.flat}kb"
    search         = "srch-${local.base}${local.sfx}"
    content_safety = "cs-${var.workload}-${var.environment}-${lookup(local.region_codes, local.locations.content_safety, "x")}${local.sfx}"
    redis          = "redis-${local.base}${local.sfx}"
    log_analytics  = "log-${local.base}"
    app_insights   = "appi-${local.base}"
    action_group   = "ag-${local.base}"
    registry       = "cr${local.flat}"
    cae            = "cae-${local.base}"
    api_app        = "ca-${var.workload}-api-${var.environment}"
    web_app        = "ca-${var.workload}-web-${var.environment}"
    ingest_job     = "caj-${var.workload}-ingest-${var.environment}"
    insurer_app    = "ca-${var.workload}-insurer-${var.environment}"
    id_app         = "id-${local.base}-app"
    id_ingest      = "id-${local.base}-ingest"
    openai = {
      for k, loc in local.openai_accounts :
      k => "oai-${var.workload}-${var.environment}-${lookup(local.region_codes, loc, "x")}${k == "primary" ? "" : "-2"}${local.sfx}"
    }
  }

  kb_container_url = "https://${local.names.storage_kb}.blob.core.windows.net/${var.kb_container_name}"

  embedding_deployment = one([for name, d in var.openai_deployments : name if d.role == "embedding"])
  deployments_by_role = {
    for role in ["small", "strong", "embedding"] :
    role => [for name, d in var.openai_deployments : name if d.role == role]
  }

  # Firewalled public access for setup from allowlisted IPs while private.
  setup_access_open = !local.private || length(var.deployer_ip_allowlist) > 0

  apim_classic_sku           = can(regex("^(Developer|Premium)_", var.apim_sku_name))
  apim_subscription_required = var.apim_auth_mode != "entra_jwt"

  # Terraform writes Key Vault secrets only when its runner can reach the vault data plane.
  write_secrets = local.setup_access_open && var.grant_deployer_data_roles && local.apim_subscription_required

  private_dns_zones = merge(
    {
      openai = "privatelink.openai.azure.com"
      search = "privatelink.search.windows.net"
      vault  = "privatelink.vaultcore.azure.net"
      blob   = "privatelink.blob.core.windows.net"
    },
    var.enable_content_safety ? { cognitive = "privatelink.cognitiveservices.azure.com" } : {},
    var.enable_semantic_cache ? { redis = "privatelink.redis.azure.net" } : {}
  )

  default_tags = {
    workload    = var.workload
    environment = var.environment
    managed_by  = "terraform"
    repo        = "suhail39ahmed/rabt-care-loop"
    data        = "synthetic"
  }
  tags = merge(local.default_tags, var.tags)
}
