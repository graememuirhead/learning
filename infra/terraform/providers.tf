terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.110"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Uncomment this block to store Terraform state in Azure Blob Storage
  # (recommended for team use / CI-CD)
  #
  # backend "azurerm" {
  #   resource_group_name  = "rye-tri-tfstate-rg"
  #   storage_account_name = "ryetritfstate"
  #   container_name       = "tfstate"
  #   key                  = "rye-tri.tfstate"
  # }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }
  }
}
