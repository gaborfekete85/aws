data "aws_caller_identity" "current" {}

locals {
  account_id   = data.aws_caller_identity.current.account_id
  boundary_arn = "arn:aws:iam::${local.account_id}:policy/${var.project}-workload-boundary"

  common_env = {
    ENV             = var.env
    EVENT_BUS_NAME  = module.eventbridge.bus_name
    EVENTS_BUS_NAME = module.eventbridge.bus_name # name lbz reads
    LOG_LEVEL       = var.env == "prod" ? "INFO" : "DEBUG"
    CORS_ORIGINS    = join(",", local.web_origins)
  }
}

module "eventbridge" {
  source = "../eventbridge"
  name   = local.name
}

module "api" {
  source             = "../api"
  name               = "${local.name}-api"
  cors_allow_origins = local.web_origins
  log_retention_days = var.log_retention_days
  # Every route requires a valid Cognito ID token unless marked `public = true`.
  jwt_issuer   = module.cognito.issuer
  jwt_audience = [module.cognito.web_client_id]
}

locals {
  api = {
    api_id        = module.api.api_id
    execution_arn = module.api.execution_arn
    authorizer_id = module.api.authorizer_id
  }
}

module "health" {
  source                   = "../lambda-service"
  name                     = "${local.name}-health"
  description              = "GET /health: API Gateway -> Lambda -> lbz smoke endpoint"
  package_path             = "${var.lambda_packages_dir}/shared.zip"
  handler                  = "localbini_shared.health.handle"
  memory_size              = 128
  permissions_boundary_arn = local.boundary_arn
  log_retention_days       = var.log_retention_days
  environment              = local.common_env
  api                      = local.api
  routes                   = [{ route_key = "GET /health", public = true }]
}
