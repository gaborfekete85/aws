provider "aws" {
  region = var.region

  default_tags {
    tags = {
      project = "meeton"
      env     = "prod"
      owner   = var.owner
    }
  }
}
