output "vpc_id" {
  description = "VPC id."
  value       = module.stack.vpc_id
}

output "api_endpoint" {
  description = "Base URL of the HTTP API."
  value       = module.stack.api_endpoint
}

output "event_bus_name" {
  description = "Domain event bus."
  value       = module.stack.event_bus_name
}
