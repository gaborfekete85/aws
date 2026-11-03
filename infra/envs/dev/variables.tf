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
