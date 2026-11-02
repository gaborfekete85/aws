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
  description = "Budget alert recipients."
  type        = list(string)
  default     = ["gabor.fekete85@gmail.com"]
}
