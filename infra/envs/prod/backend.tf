terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Bucket comes from infra/bootstrap; CI may override with -backend-config=bucket=...
  backend "s3" {
    bucket       = "localbini-tfstate-190016928273"
    key          = "envs/prod/terraform.tfstate"
    region       = "eu-central-1"
    encrypt      = true
    use_lockfile = true
  }
}
