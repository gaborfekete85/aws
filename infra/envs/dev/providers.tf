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

# Region of the existing database (#39); only its security group rule lives there.
provider "aws" {
  alias  = "external_db"
  region = var.external_db_region

  default_tags {
    tags = {
      project = "meeton"
      env     = "dev"
      owner   = var.owner
    }
  }
}
