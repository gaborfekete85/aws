variable "name" {
  description = "Name prefix, e.g. meeton-dev."
  type        = string
}

variable "ssm_prefix" {
  description = "SSM prefix for this environment, e.g. /meeton/dev."
  type        = string
}

variable "callback_urls" {
  description = "OAuth callback URLs for the web app (per environment)."
  type        = list(string)
}

variable "logout_urls" {
  description = "Sign-out URLs for the web app."
  type        = list(string)
}

variable "enable_google" {
  description = "Create the Google identity provider (needs real credentials in SSM first)."
  type        = bool
  default     = true
}

variable "deletion_protection" {
  description = "Protect the user pool from deletion (on in prod)."
  type        = bool
  default     = false
}

variable "create_test_client" {
  description = "Dev only: an app client allowing USER_PASSWORD_AUTH for the integration suite."
  type        = bool
  default     = false
}
