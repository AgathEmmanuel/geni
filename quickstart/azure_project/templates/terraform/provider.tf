terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.80"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  subscription_id = "${{ subscription_id }}"

  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
    key_vault {
      purge_soft_delete_on_destroy = true
    }
    virtual_machine {
      delete_os_disk_on_deletion = true
    }
  }

  default_tags {
    tags = {
      project     = "${{ project }}"
      environment = "${{ environment }}"
      managed_by  = "terraform"
      generated   = "geni"
    }
  }
}

provider "random" {}

provider "tls" {}
