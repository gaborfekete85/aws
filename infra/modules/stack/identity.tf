module "cognito" {
  source              = "../cognito"
  name                = local.name
  ssm_prefix          = "/${var.project}/${var.env}"
  callback_urls       = [for u in local.web_origins : "${u}/auth/callback"]
  logout_urls         = [for u in local.web_origins : "${u}/"]
  enable_google       = var.enable_google_login
  deletion_protection = var.env == "prod"
}

# Admin-only API over Cognito groups (assign / revoke the organizer role).
data "aws_iam_policy_document" "identity_admin" {
  statement {
    actions = [
      "cognito-idp:ListUsers",
      "cognito-idp:ListUsersInGroup",
      "cognito-idp:AdminGetUser",
      "cognito-idp:AdminAddUserToGroup",
      "cognito-idp:AdminRemoveUserFromGroup",
    ]
    resources = [module.cognito.user_pool_arn]
  }
}

module "identity_api" {
  source                   = "../lambda-service"
  name                     = "${local.name}-identity-api"
  description              = "Identity: Admins assign and revoke the organizer role"
  package_path             = "${var.lambda_packages_dir}/identity.zip"
  handler                  = "identity.api.handle"
  memory_size              = 256
  permissions_boundary_arn = local.boundary_arn
  log_retention_days       = var.log_retention_days
  environment              = merge(local.common_env, { USER_POOL_ID = module.cognito.user_pool_id })
  policy_json              = data.aws_iam_policy_document.identity_admin.json
  api                      = local.api
  routes = [
    { route_key = "GET /admin/users" },
    { route_key = "PUT /admin/users/{username}/roles/{role}" },
    { route_key = "DELETE /admin/users/{username}/roles/{role}" },
  ]
}
