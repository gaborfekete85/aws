variable "name" {
  description = "Bus name, e.g. localbini-dev."
  type        = string
}

variable "archive_retention_days" {
  description = "Days to keep archived events for replay (0 disables the archive)."
  type        = number
  default     = 7
}

resource "aws_cloudwatch_event_bus" "this" {
  name = var.name
}

# Archive every domain event so consumers can be replayed after a bug fix.
resource "aws_cloudwatch_event_archive" "all" {
  count            = var.archive_retention_days > 0 ? 1 : 0
  name             = "${var.name}-all"
  event_source_arn = aws_cloudwatch_event_bus.this.arn
  retention_days   = var.archive_retention_days
}

output "bus_name" {
  description = "Event bus name."
  value       = aws_cloudwatch_event_bus.this.name
}

output "bus_arn" {
  description = "Event bus ARN."
  value       = aws_cloudwatch_event_bus.this.arn
}
