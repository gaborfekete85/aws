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

variable "jwt_issuer" {
  description = "JWT issuer (Cognito user pool URL). When null, no authorizer is created."
  type        = string
  default     = null
}

variable "jwt_audience" {
  description = "Allowed JWT audiences (Cognito app client ids)."
  type        = list(string)
  default     = []
}
