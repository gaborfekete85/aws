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
  rds_office_hours_only = true # only applies when dev creates its own RDS
  # #39: reuse an existing PostgreSQL instead of a dev RDS (about USD 8/month).
  # Role, database, PostGIS and the secret come from scripts/setup_external_db.sh.
  external_catalog_db = var.external_db_host == null ? null : {
    host        = var.external_db_host
    db_name     = "meeton_dev"
    secret_name = "meeton-dev-catalog-db"
  }
  alert_emails        = var.alert_emails
  sender_email        = var.sender_email
  web_urls            = ["http://localhost:5173"]
  lambda_packages_dir = "${path.root}/../../../dist"
}

# Let the dev Lambdas (egress through the NAT instance's Elastic IP) reach the
# existing database, and nothing else; `terraform destroy` removes the rule again.
resource "aws_vpc_security_group_ingress_rule" "external_db_from_dev" {
  count             = var.external_db_security_group_id == null ? 0 : 1
  provider          = aws.external_db
  security_group_id = var.external_db_security_group_id
  description       = "meeton-dev Lambdas (NAT)"
  ip_protocol       = "tcp"
  from_port         = 5432
  to_port           = 5432
  cidr_ipv4         = "${module.stack.egress_public_ip}/32"
}
