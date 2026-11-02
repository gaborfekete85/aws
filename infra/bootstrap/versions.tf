terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Bootstrap is applied once by hand with local state; it creates the
  # bucket every other root uses as its backend.
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      project = var.project
      env     = "shared"
      owner   = var.owner
    }
  }
}
