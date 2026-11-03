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

output "user_pool_id" {
  description = "Cognito user pool id."
  value       = module.stack.user_pool_id
}

output "web_client_id" {
  description = "Cognito web app client id."
  value       = module.stack.web_client_id
}

output "hosted_ui_domain" {
  description = "Cognito Hosted UI domain."
  value       = module.stack.hosted_ui_domain
}

output "catalog_migrate_function" {
  description = "Lambda that runs Catalog migrations."
  value       = module.stack.catalog_migrate_function
}

output "web_url" {
  description = "URL of the web app."
  value       = module.stack.web_url
}

output "amplify_app_id" {
  description = "Amplify app id."
  value       = module.stack.amplify_app_id
}
