provider "aws" {
  region = var.region

  default_tags {
    tags = {
      project = "localbini"
      env     = "dev"
      owner   = var.owner
    }
  }
}
