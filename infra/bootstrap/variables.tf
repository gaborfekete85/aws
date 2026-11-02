variable "project" {
  description = "Project name, used as a prefix for resource names."
  type        = string
  default     = "localbini"
}

variable "owner" {
  description = "Owner tag value."
  type        = string
  default     = "gaborfekete85"
}

variable "region" {
  description = "AWS region for the state bucket and all environments."
  type        = string
  default     = "eu-central-1"
}

variable "github_repository" {
  description = "GitHub repository (owner/name) allowed to assume the CI roles."
  type        = string
  default     = "gaborfekete85/aws"
}

variable "create_github_oidc_provider" {
  description = "Create the GitHub OIDC provider. Set false when the account already has one (only one per URL is allowed)."
  type        = bool
  default     = false
}
