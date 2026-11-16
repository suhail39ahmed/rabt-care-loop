# Hosting for the Rabt API (FastAPI) and web (Next.js): Azure Container Registry + a Container Apps
# environment with two apps. Terraform creates the apps with a placeholder image; the GitHub Actions
# deploy workflow builds, pushes and rolls out the real images (image and target port are ignored here).

resource "azurerm_container_registry" "this" {
  #checkov:skip=CKV_AZURE_139:Basic SKU has no private endpoints; pushes use Entra ID (OIDC) and pulls use managed identity, admin user is off
  #checkov:skip=CKV_AZURE_163:image vulnerability scanning comes from Defender for Containers (subscription plan), not a registry setting
  #checkov:skip=CKV_AZURE_164:content trust (signed images) is not used for a two-image pilot
  #checkov:skip=CKV_AZURE_165:geo-replication needs Premium; pilot is single-region
  #checkov:skip=CKV_AZURE_166:quarantine needs Premium
  #checkov:skip=CKV_AZURE_167:untagged manifest retention needs Premium
  #checkov:skip=CKV_AZURE_233:zone redundancy needs Premium
  #checkov:skip=CKV_AZURE_237:dedicated data endpoints need Premium
  name                          = var.names.registry
  resource_group_name           = var.resource_group_name
  location                      = var.location
  sku                           = var.registry_sku
  admin_enabled                 = false
  anonymous_pull_enabled        = false
  public_network_access_enabled = true
  tags                          = var.tags
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.this.id
  role_definition_name = "AcrPull"
  principal_id         = var.app_identity_principal_id
  principal_type       = "ServicePrincipal"
  description          = "rabt: container apps pull images"
}

resource "azurerm_container_app_environment" "this" {
  name                           = var.names.environment
  location                       = var.location
  resource_group_name            = var.resource_group_name
  log_analytics_workspace_id     = var.log_analytics_workspace_id
  infrastructure_subnet_id       = var.infrastructure_subnet_id
  internal_load_balancer_enabled = var.infrastructure_subnet_id == null ? null : false
  tags                           = var.tags

  dynamic "workload_profile" {
    for_each = var.infrastructure_subnet_id == null ? [] : [1]
    content {
      name                  = "Consumption"
      workload_profile_type = "Consumption"
    }
  }

  lifecycle {
    ignore_changes = [infrastructure_resource_group_name]
  }
}

resource "azurerm_container_app" "web" {
  name                         = var.names.web_app
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"
  workload_profile_name        = var.infrastructure_subnet_id == null ? null : "Consumption"
  tags                         = merge(var.tags, { component = "web" })

  identity {
    type         = "UserAssigned"
    identity_ids = [var.app_identity_id]
  }

  registry {
    server   = azurerm_container_registry.this.login_server
    identity = var.app_identity_id
  }

  ingress {
    external_enabled = true
    target_port      = 80
    transport        = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = var.web.min_replicas
    max_replicas = var.web.max_replicas

    container {
      name   = "web"
      image  = var.bootstrap_image
      cpu    = var.web.cpu
      memory = var.web.memory

      env {
        name  = "NEXT_TELEMETRY_DISABLED"
        value = "1"
      }
    }
  }

  lifecycle {
    # Image and port are owned by the deploy workflow after the first rollout.
    ignore_changes = [template[0].container[0].image, ingress[0].target_port]
  }

  depends_on = [azurerm_role_assignment.acr_pull]
}

resource "azurerm_container_app" "api" {
  name                         = var.names.api_app
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = var.resource_group_name
  # One replica: the demo ledger is SQLite inside the container and reseeds on start.
  revision_mode         = "Single"
  workload_profile_name = var.infrastructure_subnet_id == null ? null : "Consumption"
  tags                  = merge(var.tags, { component = "api" })

  identity {
    type         = "UserAssigned"
    identity_ids = [var.app_identity_id]
  }

  registry {
    server   = azurerm_container_registry.this.login_server
    identity = var.app_identity_id
  }

  dynamic "secret" {
    for_each = toset(var.secret_names)
    content {
      name  = secret.value
      value = var.secrets[secret.value]
    }
  }

  ingress {
    external_enabled = true
    target_port      = 80
    transport        = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = var.api.min_replicas
    max_replicas = var.api.max_replicas

    container {
      name   = "api"
      image  = var.bootstrap_image
      cpu    = var.api.cpu
      memory = var.api.memory

      env {
        name  = "AZURE_CLIENT_ID"
        value = var.app_identity_client_id
      }

      env {
        name  = "CORS_ORIGINS"
        value = "https://${azurerm_container_app.web.ingress[0].fqdn}"
      }

      dynamic "env" {
        for_each = var.api.env
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = var.api.secret_env
        content {
          name        = env.key
          secret_name = env.value
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].container[0].image, ingress[0].target_port]
  }

  depends_on = [azurerm_role_assignment.acr_pull]
}

# ---------------------------------------------------------------------------
# KB ingestion job: indexes approved KB docs from the blob container into AI Search, hourly by default.
# Start it on demand with: az containerapp job start -n <name> -g <rg>
# ---------------------------------------------------------------------------
resource "azurerm_role_assignment" "ingest_acr_pull" {
  count                = var.ingest_job == null ? 0 : 1
  scope                = azurerm_container_registry.this.id
  role_definition_name = "AcrPull"
  principal_id         = var.ingest_job.identity_principal_id
  principal_type       = "ServicePrincipal"
  description          = "rabt: ingestion job pulls the API image"
}

resource "azurerm_container_app_job" "ingest" {
  count                        = var.ingest_job == null ? 0 : 1
  name                         = var.names.ingest_job
  location                     = var.location
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.this.id
  workload_profile_name        = var.infrastructure_subnet_id == null ? null : "Consumption"
  replica_timeout_in_seconds   = 900
  replica_retry_limit          = 1
  tags                         = merge(var.tags, { component = "kb-ingest" })

  schedule_trigger_config {
    cron_expression          = var.ingest_job.cron
    parallelism              = 1
    replica_completion_count = 1
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [var.ingest_job.identity_id]
  }

  registry {
    server   = azurerm_container_registry.this.login_server
    identity = var.ingest_job.identity_id
  }

  template {
    container {
      name   = "ingest"
      image  = var.job_bootstrap_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "RABT_ROLE"
        value = "ingest"
      }

      env {
        name  = "AZURE_CLIENT_ID"
        value = var.ingest_job.identity_client_id
      }

      dynamic "env" {
        for_each = var.ingest_job.env
        content {
          name  = env.key
          value = env.value
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  depends_on = [azurerm_role_assignment.ingest_acr_pull]
}
