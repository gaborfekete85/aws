variable "region" {
  description = "AWS region."
  type        = string
  default     = "eu-central-1"
}

variable "owner" {
  description = "Owner tag."
  type        = string
  default     = "gaborfekete85"
}

variable "alert_emails" {
  description = "Budget alert recipients (set via TF_VAR_alert_emails or a gitignored terraform.tfvars)."
  type        = list(string)
}

variable "sender_email" {
  description = "Verified SES identity Meeton sends from (TF_VAR_sender_email)."
  type        = string
}

# --- existing database for the Catalog (#39) -----------------------------------
# Kept out of the (public) repo: set TF_VAR_external_db_host and
# TF_VAR_external_db_security_group_id, or put them in a gitignored terraform.tfvars.
# When the host is null, dev creates its own RDS instance as before.
variable "external_db_host" {
  description = "Endpoint of the existing PostgreSQL the dev Catalog uses (null: create RDS)."
  type        = string
  default     = null
}

variable "external_db_security_group_id" {
  description = "Security group of that database; dev adds one rule allowing its NAT IP on 5432."
  type        = string
  default     = null
}

variable "external_db_region" {
  description = "Region of that database."
  type        = string
  default     = "eu-north-1"
}
