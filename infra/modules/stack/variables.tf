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


variable "web_urls" {
  description = "Extra web origins besides Amplify (e.g. http://localhost:5173 in dev); OAuth callbacks and CORS derive from these."
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

variable "sender_email" {
  description = "SES identity Localbini sends email from."
  type        = string
}

variable "ses_max_send_rate" {
  description = "Emails per second Notifications may send (SES sandbox: 1)."
  type        = number
  default     = 1
}

variable "enable_test_harness" {
  description = "Dev only: bus spy queue and a USER_PASSWORD_AUTH Cognito client for the integration suite."
  type        = bool
  default     = false
}

variable "interface_endpoints" {
  description = "Interface VPC endpoints for in-VPC Lambdas (each ~USD 8.8/month per AZ in eu-central-1)."
  type        = list(string)
  default     = ["secretsmanager", "events"]
}

variable "rds_office_hours_only" {
  description = "Stop the Catalog DB outside office hours (dev cost saver)."
  type        = bool
  default     = false
}
