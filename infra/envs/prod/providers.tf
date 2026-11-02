provider "aws" {
  region = var.region

  default_tags {
    tags = {
      project = "localbini"
      env     = "prod"
      owner   = var.owner
    }
  }
}
