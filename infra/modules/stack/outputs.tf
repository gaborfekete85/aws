output "vpc_id" {
  description = "VPC id."
  value       = module.network.vpc_id
}

output "api_endpoint" {
  description = "Base URL of the HTTP API."
  value       = module.api.api_endpoint
}

output "event_bus_name" {
  description = "Domain event bus."
  value       = module.eventbridge.bus_name
}
