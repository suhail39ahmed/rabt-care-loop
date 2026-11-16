locals {
  suffix = random_string.suffix.result
  base   = "${var.name_prefix}-${var.environment}"
  # Globally unique, hyphen-free names (Storage, Key Vault limits).
  compact = "${var.name_prefix}${var.environment}${local.suffix}"

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

  openai_account_deployments = {
    for pair in setproduct(keys(local.openai_accounts), keys(var.openai_deployments)) :
    "${pair[0]}/${pair[1]}" => {
      account    = pair[0]
      deployment = pair[1]
      config     = var.openai_deployments[pair[1]]
    }
  }

  embedding_deployment = one([for name, d in var.openai_deployments : name if d.role == "embedding"])
  deployments_by_role = {
    for role in ["small", "strong", "embedding"] :
    role => [for name, d in var.openai_deployments : name if d.role == role]
  }

  # Firewalled public access for setup from allowlisted IPs while private.
  setup_access_open = !local.private || length(var.deployer_ip_allowlist) > 0

  apim_classic_sku = can(regex("^(Developer|Premium)_", var.apim_sku_name))

  default_tags = {
    app         = "rabt"
    environment = var.environment
    managed_by  = "terraform"
    repo        = "suhail39ahmed/rabt-care-loop"
    data        = "synthetic"
  }
  tags = merge(local.default_tags, var.tags)
}
