variable "name" {
  description = "Function name; must start with meeton-<env>- (IAM boundary scoping)."
  type        = string
}

variable "description" {
  description = "Function description."
  type        = string
  default     = ""
}

variable "package_path" {
  description = "Path to the deployment zip built by scripts/build_lambda.sh."
  type        = string
}

variable "handler" {
  description = "Python handler, e.g. catalog.api.handle."
  type        = string
}

variable "runtime" {
  description = "Lambda runtime."
  type        = string
  default     = "python3.13"
}

variable "memory_size" {
  description = "Memory in MB (CPU scales with it)."
  type        = number
  default     = 256
}

variable "timeout" {
  description = "Timeout in seconds."
  type        = number
  default     = 10
}

variable "reserved_concurrency" {
  description = "Reserved concurrency; -1 for unreserved."
  type        = number
  default     = -1
}

variable "environment" {
  description = "Environment variables."
  type        = map(string)
  default     = {}
}

variable "log_retention_days" {
  description = "CloudWatch log retention."
  type        = number
  default     = 14
}

variable "permissions_boundary_arn" {
  description = "Permissions boundary for the execution role (required by the deploy role)."
  type        = string
}

variable "policy_json" {
  description = "Extra IAM policy document (JSON) for the execution role, or null."
  type        = string
  default     = null
}

variable "vpc" {
  description = "Run inside a VPC (needed to reach RDS)."
  type = object({
    subnet_ids         = list(string)
    security_group_ids = list(string)
  })
  default = null
}

variable "api" {
  description = "HTTP API to attach routes to, or null."
  type = object({
    api_id        = string
    execution_arn = string
    authorizer_id = optional(string)
  })
  default = null
}

variable "routes" {
  description = "Routes served by this function. public = no JWT required."
  type = list(object({
    route_key = string
    public    = optional(bool, false)
  }))
  default = []
}

variable "event_rules" {
  description = "EventBridge rules (name suffix => pattern) on bus_name that invoke this function."
  type        = map(string)
  default     = {}
}

variable "bus_name" {
  description = "Event bus for event_rules."
  type        = string
  default     = null
}

variable "schedule_expression" {
  description = "Optional schedule (e.g. rate(1 minute)) invoking this function."
  type        = string
  default     = null
}

variable "async_failure_queue_arn" {
  description = "SQS queue receiving events whose async invocation failed after retries (DLQ)."
  type        = string
  default     = null
}

variable "async_max_retries" {
  description = "Lambda retries for async (EventBridge) invocations."
  type        = number
  default     = 2
}

variable "sqs_source" {
  description = "Consume an SQS queue (partial-batch failures enabled)."
  type = object({
    queue_arn       = string
    batch_size      = optional(number, 10)
    max_concurrency = optional(number, 2)
  })
  default = null
}
