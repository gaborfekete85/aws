module "stack" {
  source                      = "../../modules/stack"
  env                         = "dev"
  vpc_cidr                    = "10.20.0.0/16"
  nat                         = "instance"
  interface_endpoint_az_count = 1
  budget_usd                  = 40
  enable_test_harness         = true
  alert_emails                = var.alert_emails
  sender_email                = var.sender_email
  web_urls                    = ["http://localhost:5173"]
  lambda_packages_dir         = "${path.root}/../../../dist"
}
