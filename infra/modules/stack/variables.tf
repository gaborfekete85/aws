variable "project" {
  description = "Project name."
  type        = string
  default     = "localbini"
}

variable "env" {
  description = "Environment name (dev, prod)."
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR for this environment."
  type        = string
}

variable "nat" {
  description = "NAT mode: none, instance or gateway."
  type        = string
}

variable "interface_endpoint_az_count" {
  description = "AZs that get interface endpoint ENIs."
  type        = number
  default     = 1
}

variable "budget_usd" {
  description = "Monthly budget in USD."
  type        = number
}

variable "alert_emails" {
  description = "Budget / alarm notification emails."
  type        = list(string)
}

variable "lambda_packages_dir" {
  description = "Directory containing <service>.zip files from scripts/build_lambda.sh."
  type        = string
}

variable "log_retention_days" {
  description = "Log retention for Lambdas and API access logs."
  type        = number
  default     = 14
}

variable "cors_allow_origins" {
  description = "Origins allowed to call the API."
  type        = list(string)
  default     = ["*"]
}

variable "web_urls" {
  description = "Origins the web app is served from (OAuth callbacks are derived from these)."
  type        = list(string)
}

variable "enable_google_login" {
  description = "Create the Google identity provider."
  type        = bool
  default     = true
}

variable "hold_minutes" {
  description = "How long a Hold keeps Places for an Attendee in Checkout."
  type        = number
  default     = 15
}
