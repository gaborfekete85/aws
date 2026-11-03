module "stack" {
  source                      = "../../modules/stack"
  env                         = "dev"
  vpc_cidr                    = "10.20.0.0/16"
  nat                         = "instance"
  interface_endpoint_az_count = 1
  budget_usd                  = 40
  enable_test_harness         = true
  # Cost review (#38): dev already has egress through the NAT instance, so Secrets
  # Manager / EventBridge traffic can use it instead of ~USD 17.5/month of interface
  # endpoints; the free S3 and DynamoDB gateway endpoints stay.
  interface_endpoints   = []
  rds_office_hours_only = true
  alert_emails          = var.alert_emails
  sender_email          = var.sender_email
  web_urls              = ["http://localhost:5173"]
  lambda_packages_dir   = "${path.root}/../../../dist"
}
