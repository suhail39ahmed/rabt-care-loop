terraform {
  required_version = ">= 1.9.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.70"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.12"
    }
  }
}
