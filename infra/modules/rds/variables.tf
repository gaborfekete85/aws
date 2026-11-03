variable "name" {
  description = "Identifier prefix, e.g. localbini-dev."
  type        = string
}

variable "vpc_id" {
  description = "VPC id."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnet ids (at least two AZs)."
  type        = list(string)
}

variable "client_security_group_ids" {
  description = "Security groups allowed to connect on 5432 (in-VPC Lambdas)."
  type        = list(string)
}

variable "instance_class" {
  description = "Smallest Graviton class by default."
  type        = string
  default     = "db.t4g.micro"
}

variable "engine_version" {
  description = "PostgreSQL major version."
  type        = string
  default     = "16"
}

variable "allocated_storage" {
  description = "Initial storage in GB."
  type        = number
  default     = 20
}

variable "max_allocated_storage" {
  description = "Storage autoscaling ceiling in GB."
  type        = number
  default     = 50
}

variable "backup_retention_days" {
  description = "Automated backup retention."
  type        = number
  default     = 7
}

variable "multi_az" {
  description = "Standby in a second AZ (prod)."
  type        = bool
  default     = false
}

variable "deletion_protection" {
  description = "Protect from deletion (prod)."
  type        = bool
  default     = false
}

variable "db_name" {
  description = "Initial database name."
  type        = string
  default     = "catalog"
}
