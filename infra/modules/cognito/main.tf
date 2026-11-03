resource "aws_cognito_user_pool" "this" {
  name                     = "${var.name}-users"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  deletion_protection      = var.deletion_protection ? "ACTIVE" : "INACTIVE"
  mfa_configuration        = "OPTIONAL"

  software_token_mfa_configuration {
    enabled = true
  }

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = false
    temporary_password_validity_days = 3
  }

  username_configuration {
    case_sensitive = false
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
    email_subject        = "Your Localbini verification code"
    email_message        = "Your Localbini verification code is {####}"
  }

  admin_create_user_config {
    allow_admin_create_user_only = false
  }

  schema {
    name                = "email"
    attribute_data_type = "String"
    required            = true
    mutable             = true
    string_attribute_constraints {
      min_length = 3
      max_length = 254
    }
  }

  schema {
    name                = "name"
    attribute_data_type = "String"
    required            = false
    mutable             = true
    string_attribute_constraints {
      min_length = 0
      max_length = 128
    }
  }

  lifecycle {
    ignore_changes = [schema] # schema attributes cannot change after creation
  }
}

# Roles. Membership lands in the `cognito:groups` claim of both ID and access tokens.
resource "aws_cognito_user_group" "admin" {
  name         = "admin"
  user_pool_id = aws_cognito_user_pool.this.id
  description  = "Platform Admins: manage any Event and assign the organizer role"
  precedence   = 1
}

resource "aws_cognito_user_group" "organizer" {
  name         = "organizer"
  user_pool_id = aws_cognito_user_pool.this.id
  description  = "Organizers: create and manage their own Events"
  precedence   = 10
}

# --- Google social login ----------------------------------------------------
# Terraform creates placeholders; a human writes the real values (see README).
resource "aws_ssm_parameter" "google_client_id" {
  name  = "${var.ssm_prefix}/google/client_id"
  type  = "String"
  value = "CHANGE_ME"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "google_client_secret" {
  name             = "${var.ssm_prefix}/google/client_secret"
  type             = "SecureString"
  value_wo         = "CHANGE_ME" # write-only: never stored in state
  value_wo_version = 1
}

data "aws_ssm_parameter" "google_client_id" {
  count = var.enable_google ? 1 : 0
  name  = aws_ssm_parameter.google_client_id.name
}

data "aws_ssm_parameter" "google_client_secret" {
  count           = var.enable_google ? 1 : 0
  name            = aws_ssm_parameter.google_client_secret.name
  with_decryption = true
}

resource "aws_cognito_identity_provider" "google" {
  count         = var.enable_google ? 1 : 0
  user_pool_id  = aws_cognito_user_pool.this.id
  provider_name = "Google"
  provider_type = "Google"

  provider_details = {
    client_id        = data.aws_ssm_parameter.google_client_id[0].value
    client_secret    = data.aws_ssm_parameter.google_client_secret[0].value
    authorize_scopes = "openid email profile"
  }

  attribute_mapping = {
    email          = "email"
    email_verified = "email_verified"
    name           = "name"
    username       = "sub"
  }
}

# --- Hosted UI + web app client -------------------------------------------------
data "aws_caller_identity" "current" {}

resource "aws_cognito_user_pool_domain" "this" {
  # Prefix domains are global; a short account-derived suffix avoids collisions.
  domain       = "${var.name}-${substr(sha1(data.aws_caller_identity.current.account_id), 0, 6)}"
  user_pool_id = aws_cognito_user_pool.this.id
}

resource "aws_cognito_user_pool_client" "web" {
  name         = "${var.name}-web"
  user_pool_id = aws_cognito_user_pool.this.id

  generate_secret                      = false # public SPA client, PKCE
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  callback_urls                        = var.callback_urls
  logout_urls                          = var.logout_urls
  supported_identity_providers         = concat(["COGNITO"], var.enable_google ? ["Google"] : [])

  explicit_auth_flows           = ["ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  prevent_user_existence_errors = "ENABLED"
  enable_token_revocation       = true

  access_token_validity  = 60
  id_token_validity      = 60
  refresh_token_validity = 30
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }

  depends_on = [aws_cognito_identity_provider.google]
}

# Integration tests log in with USER_PASSWORD_AUTH (no SRP in pytest). Dev only;
# the web client above stays SRP-only.
resource "aws_cognito_user_pool_client" "test" {
  count                         = var.create_test_client ? 1 : 0
  name                          = "${var.name}-integration-tests"
  user_pool_id                  = aws_cognito_user_pool.this.id
  generate_secret               = false
  explicit_auth_flows           = ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  prevent_user_existence_errors = "ENABLED"
  id_token_validity             = 60
  access_token_validity         = 60
  refresh_token_validity        = 1
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}
