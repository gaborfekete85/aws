module "catalog_db" {
  source                    = "../rds"
  name                      = local.name
  vpc_id                    = module.network.vpc_id
  subnet_ids                = module.network.private_subnet_ids
  client_security_group_ids = [module.network.lambda_security_group_id]
  multi_az                  = var.env == "prod"
  deletion_protection       = var.env == "prod"
  log_retention_days        = var.log_retention_days
  office_hours_only         = var.rds_office_hours_only
  permissions_boundary_arn  = local.boundary_arn
}

locals {
  catalog_vpc = {
    subnet_ids         = module.network.private_subnet_ids
    security_group_ids = [module.network.lambda_security_group_id]
  }
  catalog_db_env = {
    DB_HOST       = module.catalog_db.address
    DB_PORT       = tostring(module.catalog_db.port)
    DB_NAME       = module.catalog_db.db_name
    DB_SECRET_ARN = module.catalog_db.secret_arn
  }
}

data "aws_iam_policy_document" "catalog_db_secret" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [module.catalog_db.secret_arn]
  }
}

# Runs `alembic upgrade head` from inside the VPC; CI invokes it after apply.
module "catalog_migrate" {
  source                   = "../lambda-service"
  name                     = "${local.name}-catalog-migrate"
  description              = "Catalog: Alembic migrations (invoked by CI after terraform apply)"
  package_path             = "${var.lambda_packages_dir}/catalog.zip"
  handler                  = "catalog.migrate.handle"
  timeout                  = 300
  memory_size              = 512 # runs a few times a month; faster migrations
  permissions_boundary_arn = local.boundary_arn
  log_retention_days       = var.log_retention_days
  environment              = merge(local.common_env, local.catalog_db_env)
  policy_json              = data.aws_iam_policy_document.catalog_db_secret.json
  vpc                      = local.catalog_vpc
}

module "media" {
  source             = "../media"
  name               = local.name
  cors_allow_origins = local.web_origins
}

data "aws_iam_policy_document" "catalog_api" {
  source_policy_documents = [data.aws_iam_policy_document.catalog_db_secret.json]
  statement {
    actions   = ["events:PutEvents"]
    resources = [module.eventbridge.bus_arn]
  }
  # Presigning a PUT needs PutObject; attaching checks the object with HeadObject (GetObject).
  statement {
    actions   = ["s3:PutObject", "s3:GetObject"]
    resources = ["${module.media.bucket_arn}/covers/*"]
  }
}

module "catalog_api" {
  source                   = "../lambda-service"
  name                     = "${local.name}-catalog-api"
  description              = "Catalog: Organizer Event management and public Event search"
  package_path             = "${var.lambda_packages_dir}/catalog.zip"
  handler                  = "catalog.api.handle"
  timeout                  = 15   # includes geocoding with retries
  memory_size              = 1024 # import-heavy cold start (SQLAlchemy, geoalchemy2, psycopg): CPU scales with memory; see docs/cost.md
  permissions_boundary_arn = local.boundary_arn
  log_retention_days       = var.log_retention_days
  environment = merge(local.common_env, local.catalog_db_env, {
    GEOCODER_URL     = "https://nominatim.openstreetmap.org/search"
    MEDIA_BUCKET     = module.media.bucket_name
    MEDIA_CDN_DOMAIN = module.media.cdn_domain
  })
  policy_json = data.aws_iam_policy_document.catalog_api.json
  vpc         = local.catalog_vpc
  api         = local.api
  routes = [
    { route_key = "POST /events" },
    { route_key = "PATCH /events/{event_id}" },
    { route_key = "POST /events/{event_id}/publish" },
    { route_key = "POST /events/{event_id}/cancel" },
    { route_key = "GET /organizer/events" },
    { route_key = "GET /organizer/events/{event_id}" },
    { route_key = "POST /events/{event_id}/cover-picture/upload-url" },
    { route_key = "PUT /events/{event_id}/cover-picture" },
    # Visitors search and read Events without logging in.
    { route_key = "GET /events", public = true },
    { route_key = "GET /events/{event_id}", public = true },
  ]
}
