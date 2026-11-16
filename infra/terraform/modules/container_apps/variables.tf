variable "names" {
  description = "Resource names: registry (ACR, alphanumeric), environment, api_app, web_app."
  type = object({
    registry    = string
    environment = string
    api_app     = string
    web_app     = string
    ingest_job  = optional(string)
    insurer_app = optional(string)
  })
}

variable "resource_group_name" {
  description = "Resource group."
  type        = string
}

variable "location" {
  description = "Region."
  type        = string
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}

variable "log_analytics_workspace_id" {
  description = "Workspace for container logs."
  type        = string
}

variable "infrastructure_subnet_id" {
  description = "Delegated subnet for a VNet-integrated environment (/27+). null = Azure-managed network."
  type        = string
  default     = null
}

variable "app_identity_id" {
  description = "User-assigned identity the apps run as (AcrPull is granted here)."
  type        = string
}

variable "app_identity_principal_id" {
  description = "Principal ID of the app identity."
  type        = string
}

variable "app_identity_client_id" {
  description = "Client ID of the app identity (exported as AZURE_CLIENT_ID)."
  type        = string
}

variable "registry_sku" {
  description = "ACR SKU. Basic is enough for two images; Premium adds private endpoints and geo-replication."
  type        = string
  default     = "Basic"

  validation {
    condition     = contains(["Basic", "Standard", "Premium"], var.registry_sku)
    error_message = "registry_sku must be Basic, Standard or Premium."
  }
}

variable "api" {
  description = "API container settings. env holds plain settings; secret_env maps env var name => secret name in var.secrets."
  type = object({
    cpu          = optional(number, 0.5)
    memory       = optional(string, "1Gi")
    min_replicas = optional(number, 1)
    max_replicas = optional(number, 1)
    env          = optional(map(string), {})
    secret_env   = optional(map(string), {})
  })
  default = {}
}

variable "web" {
  description = "Web container settings."
  type = object({
    cpu          = optional(number, 0.25)
    memory       = optional(string, "0.5Gi")
    min_replicas = optional(number, 1)
    max_replicas = optional(number, 2)
  })
  default = {}
}

variable "secrets" {
  description = "Container App secrets for the API (name => value). Values live encrypted in Container Apps, never in images."
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "secret_names" {
  description = "Static list of the keys of var.secrets (for_each cannot use sensitive keys)."
  type        = list(string)
  default     = []
}

variable "bootstrap_image" {
  description = "Public placeholder image used until the deploy workflow pushes the real images (it listens on port 80)."
  type        = string
  default     = "mcr.microsoft.com/k8se/quickstart:latest"
}

variable "ingest_job" {
  description = <<-EOT
    Optional KB ingestion job (Container Apps Job, schedule trigger) that runs the API image with
    RABT_ROLE=ingest under the ingestion managed identity. null = no job.
  EOT
  type = object({
    identity_id           = string
    identity_principal_id = string
    identity_client_id    = string
    cron                  = optional(string, "15 * * * *")
    env                   = optional(map(string), {})
  })
  default = null
}

variable "job_bootstrap_image" {
  description = "Placeholder image for the ingestion job until the deploy workflow sets the real one (runs and exits)."
  type        = string
  default     = "mcr.microsoft.com/k8se/quickstart-jobs:latest"
}

variable "insurer" {
  description = <<-EOT
    Optional demo insurer A2A agent (synthetic payer). Runs the API image with RABT_ROLE=insurer;
    requests and replies are HMAC-signed with var.a2a_shared_secret. null = in-process insurer.
  EOT
  type = object({
    cpu    = optional(number, 0.25)
    memory = optional(string, "0.5Gi")
  })
  default = null
}

variable "a2a_shared_secret" {
  description = "Shared HMAC secret between the API and the demo insurer agent (required when var.insurer is set)."
  type        = string
  default     = ""
  sensitive   = true
}
