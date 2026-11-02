variable "name" {
  description = "Name prefix, e.g. localbini-dev."
  type        = string
}

variable "cidr_block" {
  description = "VPC CIDR."
  type        = string
  default     = "10.20.0.0/16"
}

variable "az_count" {
  description = "Number of AZs for private subnets (RDS needs at least 2)."
  type        = number
  default     = 2
  validation {
    condition     = var.az_count >= 2 && var.az_count <= 3
    error_message = "az_count must be 2 or 3."
  }
}

variable "nat" {
  description = <<-EOT
    Egress for private subnets. "none": no internet egress (AWS traffic via endpoints only).
    "instance": a t4g.nano NAT instance (cheap, single-AZ, fine for dev).
    "gateway": a managed NAT Gateway (~USD 35/month + data, for prod).
  EOT
  type        = string
  default     = "instance"
  validation {
    condition     = contains(["none", "instance", "gateway"], var.nat)
    error_message = "nat must be one of none, instance, gateway."
  }
}

variable "interface_endpoints" {
  description = "AWS services reached privately from in-VPC Lambdas through interface endpoints."
  type        = list(string)
  default     = ["secretsmanager", "events"]
}

variable "interface_endpoint_az_count" {
  description = "How many AZs get an interface endpoint ENI (each costs ~USD 7/month)."
  type        = number
  default     = 1
}
