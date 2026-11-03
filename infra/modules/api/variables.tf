variable "name" {
  description = "API name, e.g. meeton-dev-api."
  type        = string
}

variable "cors_allow_origins" {
  description = "Origins allowed by CORS."
  type        = list(string)
  default     = ["*"]
}

variable "log_retention_days" {
  description = "Access log retention."
  type        = number
  default     = 14
}

variable "throttling_burst_limit" {
  description = "Default route burst limit."
  type        = number
  default     = 100
}

variable "throttling_rate_limit" {
  description = "Default route steady-state requests per second."
  type        = number
  default     = 50
}

variable "jwt" {
  description = <<-EOT
    JWT authorizer: issuer (Cognito user pool URL) and allowed audiences (app client ids).
    When null, no authorizer is created. An object so that decision is known at plan
    time even though the issuer of a not-yet-created user pool is not.
  EOT
  type = object({
    issuer   = string
    audience = list(string)
  })
  default = null
}
