provider "aws" {
  region = var.region

  default_tags {
    tags = {
      project = "meeton"
      env     = "dev"
      owner   = var.owner
    }
  }
}
