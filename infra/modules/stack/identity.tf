module "cognito" {
  source              = "../cognito"
  name                = local.name
  ssm_prefix          = "/${var.project}/${var.env}"
  callback_urls       = [for u in var.web_urls : "${u}/auth/callback"]
  logout_urls         = [for u in var.web_urls : "${u}/"]
  enable_google       = var.enable_google_login
  deletion_protection = var.env == "prod"
}
