# terraform test with a mocked AWS provider: asserts the module's contract
# without touching AWS.
mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
  mock_data "aws_region" {
    defaults = { region = "eu-central-1" }
  }
  mock_data "aws_ssm_parameter" {
    defaults = { value = "google-value" }
  }
  mock_resource "aws_cognito_user_pool" {
    defaults = { id = "eu-central-1_TEST", arn = "arn:aws:cognito-idp:eu-central-1:123456789012:userpool/eu-central-1_TEST" }
  }
}

variables {
  name          = "localbini-dev"
  ssm_prefix    = "/localbini/dev"
  callback_urls = ["http://localhost:5173/auth/callback"]
  logout_urls   = ["http://localhost:5173/"]
}

run "password_signup_with_email_verification" {
  command = apply

  assert {
    condition     = aws_cognito_user_pool.this.auto_verified_attributes == toset(["email"])
    error_message = "email must be auto-verified"
  }
  assert {
    condition     = aws_cognito_user_pool.this.password_policy[0].minimum_length >= 12
    error_message = "password policy too weak"
  }
}

run "roles_are_groups" {
  command = apply

  assert {
    condition     = aws_cognito_user_group.admin.name == "admin" && aws_cognito_user_group.organizer.name == "organizer"
    error_message = "admin and organizer groups must exist"
  }
}

run "web_client_is_public_pkce_with_google" {
  command = apply

  assert {
    condition     = aws_cognito_user_pool_client.web.generate_secret == false
    error_message = "SPA client must not have a secret"
  }
  assert {
    condition     = contains(aws_cognito_user_pool_client.web.supported_identity_providers, "Google")
    error_message = "Google must be an identity provider for the web client"
  }
  assert {
    condition     = aws_cognito_user_pool_client.web.callback_urls == toset(["http://localhost:5173/auth/callback"])
    error_message = "callback URLs must come from the environment"
  }
  assert {
    condition     = output.issuer == "https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_TEST"
    error_message = "issuer must point at the pool"
  }
}

run "google_credentials_come_from_ssm" {
  command = apply

  assert {
    condition     = aws_ssm_parameter.google_client_secret.type == "SecureString"
    error_message = "client secret must be a SecureString"
  }
  assert {
    condition     = aws_cognito_identity_provider.google[0].provider_details["client_id"] == "google-value"
    error_message = "client id must be read from SSM"
  }
}

run "google_can_be_disabled" {
  command = apply
  variables {
    enable_google = false
  }

  assert {
    condition     = length(aws_cognito_identity_provider.google) == 0 && aws_cognito_user_pool_client.web.supported_identity_providers == toset(["COGNITO"])
    error_message = "without Google only COGNITO is supported"
  }
}
