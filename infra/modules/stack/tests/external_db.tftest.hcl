# #39: dev can use an existing PostgreSQL instead of creating RDS.
# Mocked AWS provider; run with `terraform init -backend=false && terraform test`.

mock_provider "aws" {
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
  mock_data "aws_region" {
    defaults = { name = "eu-central-1", region = "eu-central-1" }
  }
  mock_data "aws_availability_zones" {
    defaults = { names = ["eu-central-1a", "eu-central-1b"] }
  }
  mock_data "aws_secretsmanager_secret" {
    defaults = { arn = "arn:aws:secretsmanager:eu-central-1:123456789012:secret:meeton-dev-catalog-db-AbCdEf" }
  }
}

variables {
  env                 = "dev"
  vpc_cidr            = "10.20.0.0/16"
  nat                 = "instance"
  budget_usd          = 40
  alert_emails        = ["ops@example.com"]
  sender_email        = "no-reply@example.com"
  lambda_packages_dir = "tests/packages"
  interface_endpoints = []
  web_urls            = ["http://localhost:5173"]
}

run "external_database_replaces_rds" {
  command = plan

  variables {
    external_catalog_db = {
      host        = "db.example.eu-north-1.rds.amazonaws.com"
      db_name     = "meeton_dev"
      secret_name = "meeton-dev-catalog-db"
    }
  }

  assert {
    condition     = length(module.catalog_db) == 0
    error_message = "no RDS instance when an external database is configured"
  }
  assert {
    condition     = nonsensitive(local.catalog_db_env.DB_HOST) == "db.example.eu-north-1.rds.amazonaws.com"
    error_message = "Catalog Lambdas connect to the external host"
  }
  assert {
    condition     = local.catalog_db_env.DB_PORT == "5432" && local.catalog_db_env.DB_NAME == "meeton_dev"
    error_message = "port defaults to 5432 and the database name is passed through"
  }
  assert {
    condition     = local.catalog_db_env.DB_SECRET_ARN == data.aws_secretsmanager_secret.external_catalog_db[0].arn
    error_message = "credentials come from the externally created secret"
  }
  assert {
    condition     = issensitive(local.catalog_db_env.DB_HOST)
    error_message = "the host stays out of plan output (public CI logs)"
  }
}

run "own_rds_by_default" {
  command = plan

  assert {
    condition     = length(module.catalog_db) == 1
    error_message = "dev and prod create their own RDS unless told otherwise"
  }
  assert {
    condition     = length(data.aws_secretsmanager_secret.external_catalog_db) == 0
    error_message = "no external secret lookup without an external database"
  }
}

run "secret_outside_the_boundary_is_rejected" {
  command = plan

  variables {
    external_catalog_db = {
      host        = "db.example.com"
      db_name     = "meeton_dev"
      secret_name = "some-other-secret"
    }
  }

  expect_failures = [data.aws_secretsmanager_secret.external_catalog_db]
}

# The whole stack must plan before anything exists: every count/for_each has to be
# decidable while ARNs, ids and policy JSON are still unknown (prod shape).
run "prod_shape_plans_from_scratch" {
  command = plan

  variables {
    env                 = "prod"
    nat                 = "gateway"
    interface_endpoints = ["secretsmanager", "events"]
    enable_test_harness = false
  }

  assert {
    condition     = length(module.catalog_db) == 1
    error_message = "prod keeps its own RDS"
  }
}
