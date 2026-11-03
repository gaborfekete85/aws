variable "project" {
  description = "Project name, used as a prefix for resource names."
  type        = string
  default     = "meeton"
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

variable "github_subject_prefix" {
  description = <<-EOT
    Prefix of the `sub` claim GitHub puts in this repository's OIDC tokens. Newer
    repositories use immutable subjects (owner@id/repo@id) so a renamed or recreated
    repository cannot inherit the roles. Look it up with
      gh api repos/<owner>/<repo>/actions/oidc/customization/sub -q .sub_claim_prefix
    null = the classic name-based form "repo:<owner>/<repo>".
  EOT
  type        = string
  default     = "repo:gaborfekete85@12583202/aws@1443575295"
}

variable "create_github_oidc_provider" {
  description = "Create the GitHub OIDC provider. Set false when the account already has one (only one per URL is allowed)."
  type        = bool
  default     = false
}
