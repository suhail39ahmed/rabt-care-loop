terraform {
  required_version = ">= 1.9.0, < 2.0.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.70"
    }
    azapi = {
      source  = "Azure/azapi"
      version = "~> 2.5"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.12"
    }
  }

  # Remote state in an Azure Storage account (Entra ID auth, no account keys).
  # Local:  terraform init -backend-config=backend.hcl   (copy backend.hcl.example)
  # CI:     the infra workflow passes the same values from GitHub variables.
  backend "azurerm" {}
}
