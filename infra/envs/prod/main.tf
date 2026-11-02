module "stack" {
  source                      = "../../modules/stack"
  env                         = "prod"
  vpc_cidr                    = "10.30.0.0/16"
  nat                         = "gateway"
  interface_endpoint_az_count = 2
  budget_usd                  = 120
  alert_emails                = var.alert_emails
  lambda_packages_dir         = "${path.root}/../../../dist"
}
