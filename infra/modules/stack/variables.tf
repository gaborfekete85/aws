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
