locals {
  name = "${var.project}-${var.env}"
}

module "network" {
  source                      = "../network"
  name                        = local.name
  cidr_block                  = var.vpc_cidr
  nat                         = var.nat
  interface_endpoint_az_count = var.interface_endpoint_az_count
}

module "budget" {
  source            = "../budget"
  name              = "${local.name}-monthly"
  env               = var.env
  monthly_limit_usd = var.budget_usd
  alert_emails      = var.alert_emails
}
