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

output "user_pool_id" {
  description = "Cognito user pool id."
  value       = module.cognito.user_pool_id
}

output "web_client_id" {
  description = "Cognito app client id for the web app."
  value       = module.cognito.web_client_id
}

output "hosted_ui_domain" {
  description = "Cognito Hosted UI domain."
  value       = module.cognito.hosted_ui_domain
}

output "catalog_migrate_function" {
  description = "Lambda that runs Catalog migrations."
  value       = module.catalog_migrate.function_name
}

output "media_cdn_domain" {
  description = "CloudFront domain for Cover pictures."
  value       = module.media.cdn_domain
}
